"""pytest-bdd step definitions for the @backend Scoring scenarios that the
domain layer (T-01 + T-02) can satisfy on its own.

The Gherkin source of truth is the single original feature file under
``specs/0001-shooting-session/acceptance.feature`` (referenced relatively, never
copied). Only the scenarios that are *green-able with the domain alone* are
bound here via explicit ``@scenario(...)`` so that scenarios belonging to other
tasks (persistence: L152/L191 save paths, API: 422 mapping) are not collected
and do not fail on undefined steps in this increment.

Bound this increment (T-01 + T-02):
  * L132 @R-13 — Accuracy value object rejects an out-of-range value (1.5).
  * L119 @R-11 — accuracy computed as 0.625 from hits=5 / total_clicks=8.
  * L125 @R-12 — average reaction_time = 400ms from hits, misses excluded.
  * L138 @R-13 Scenario Outline — invariant-violating submissions are rejected
    (hits>total_clicks; reaction_time containing -1ms) and no score is produced.

NOT bound here (no repository/DB in T-02): the persistence scenarios L152
("score saved") and L191 ("score is saved") — those are completed in
T-05/T-07/T-08. The 0/0 domain capability behind L191 is covered by a plain
domain unit test in ``tests/unit`` instead.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from app.domain.exceptions import InvariantViolation
from app.domain.score import Score
from app.domain.value_objects import Accuracy

# Original feature file, referenced relatively (no copy) per the SDD rules.
FEATURE = str(
    (Path(__file__).parents[3] / "specs" / "0001-shooting-session" / "acceptance.feature").resolve()
)


# --- Scenario bindings (explicit by name; no whole-file autocollection) --------


@scenario(FEATURE, "Accuracy 値オブジェクトは範囲外の値を拒否する（異常）")
def test_accuracy_rejects_out_of_range() -> None:
    """L132 @R-13: Accuracy value object rejects 1.5 at construction."""


@scenario(FEATURE, "生データから命中率を hits ÷ total_clicks で算出する（正常）")
def test_accuracy_computed_from_counts() -> None:
    """L119 @R-11: accuracy = 0.625 from hits=5 / total_clicks=8."""


@scenario(FEATURE, "平均反応時間はヒットのみで算出する（正常）")
def test_average_reaction_time_hits_only() -> None:
    """L125 @R-12: average reaction_time = 400ms, misses excluded."""


@scenario(FEATURE, "不変条件に違反する申告を拒否する（異常）")
def test_invariant_violation_rejected() -> None:
    """L138 @R-13 Outline: hits>total / -1ms rejected; no score produced."""


# --- Shared context -----------------------------------------------------------


@pytest.fixture
def context() -> dict[str, Any]:
    """Mutable bag carrying state between Given/When/Then steps."""
    return {}


# === L132 @R-13: Accuracy value object rejects out-of-range ===================


@given(parsers.parse("accuracy の値として {value} が与えられる"))
def given_accuracy_value(context: dict[str, Any], value: str) -> None:
    # Precondition: record the raw value; construction (the trigger) is the When.
    context["raw_accuracy"] = Decimal(value)


@when("Accuracy 値オブジェクトを構築する")
def when_build_accuracy(context: dict[str, Any]) -> None:
    try:
        context["result"] = Accuracy(value=context["raw_accuracy"])
        context["error"] = None
    except InvariantViolation as exc:  # captured so Then can assert on it
        context["error"] = exc


@then("InvariantViolation が送出される")
def then_invariant_violation_raised(context: dict[str, Any]) -> None:
    assert isinstance(context["error"], InvariantViolation)


# === L119 @R-11 / L125 @R-12: submit raw data, domain computes ================


@given(
    parsers.parse(
        "hits={hits:d}・total_clicks={total_clicks:d}・"
        "ヒット{hit_count:d}件の reaction_time を持つ完了セッションのデータがある"
    )
)
def given_session_data_generic_hits(
    context: dict[str, Any], hits: int, total_clicks: int, hit_count: int
) -> None:
    # R-11 (L119): hits=5/total_clicks=8 with 5 hit reaction_times. The exact ms
    # values are irrelevant to accuracy; any non-negative values suffice.
    context["hits"] = hits
    context["total_clicks"] = total_clicks
    context["reaction_times"] = [100] * hit_count


@given(
    parsers.parse(
        "hits={hits:d}・total_clicks={total_clicks:d}・"
        "ヒットの reaction_time が {first:d}ms と {second:d}ms の完了セッションのデータがある"
    )
)
def given_session_data_two_reaction_times(
    context: dict[str, Any], hits: int, total_clicks: int, first: int, second: int
) -> None:
    # R-12 (L125): hits=2/total_clicks=5, reaction_times 300ms & 500ms.
    context["hits"] = hits
    context["total_clicks"] = total_clicks
    context["reaction_times"] = [first, second]


@when("そのデータが提出される")
def when_data_submitted(context: dict[str, Any]) -> None:
    # In this domain-only increment, "submission" is the aggregate factory.
    # Application/API wiring (gun_id resolution, persistence) arrives in T-03+.
    try:
        context["score"] = Score.create(
            hits=context["hits"],
            total_clicks=context["total_clicks"],
            reaction_times=context["reaction_times"],
            time_limit_ms=30000,
            gun_id=1,
        )
        context["error"] = None
    except InvariantViolation as exc:
        context["score"] = None
        context["error"] = exc


@then(parsers.parse("システムは accuracy を {expected} と算出する"))
def then_accuracy_equals(context: dict[str, Any], expected: str) -> None:
    score: Score | None = context["score"]
    assert score is not None
    assert score.accuracy.value == Decimal(expected)


@then(parsers.parse("システムは平均 reaction_time を {expected:d}ms と算出する"))
def then_average_equals(context: dict[str, Any], expected: int) -> None:
    score: Score | None = context["score"]
    assert score is not None
    assert score.avg_reaction_time.ms == Decimal(expected)


@then("ミスのクリックは平均の算出に含まれない")
def then_misses_excluded(context: dict[str, Any]) -> None:
    # hits=2 with 2 reaction_times averaged to 400ms proves the 3 misses
    # (total_clicks=5) did not enter the mean (they would have dragged it down).
    score: Score | None = context["score"]
    assert score is not None
    assert score.hits == 2
    assert score.total_clicks == 5
    assert score.avg_reaction_time.ms == Decimal(400)


# === L138 @R-13 Scenario Outline: invariant-violating submissions rejected =====


# Matched via regex (not parse) so the greedy ``{description}`` does not shadow
# the specific R-11/R-12 Given steps above. The Outline rows always end with a
# full-width parenthetical "（…）" right before "の完了セッションのデータがある",
# which the R-11/R-12 lines lack; the regex requires that "）" to disambiguate.
@given(parsers.re(r"(?P<description>.+）)\s*の完了セッションのデータがある"))
def given_violating_session_data(context: dict[str, Any], description: str) -> None:
    # The Outline carries the case in its free-text "<説明>" column. Map each
    # described case to concrete raw data that triggers the named invariant.
    if "hits が分母超過" in description:
        # hits=9・total_clicks=8: hits > total_clicks.
        context["hits"] = 9
        context["total_clicks"] = 8
        context["reaction_times"] = [100] * 9
    elif "負の反応時間" in description:
        # reaction_time に -1ms を含む: a negative reaction_time among the hits.
        context["hits"] = 2
        context["total_clicks"] = 5
        context["reaction_times"] = [100, -1]
    else:  # pragma: no cover - guards against an unmapped Examples row
        raise AssertionError(f"unmapped Scenario Outline case: {description!r}")


@then("システムは提出を拒否する")
def then_submission_rejected(context: dict[str, Any]) -> None:
    assert isinstance(context["error"], InvariantViolation)


@then("score は保存されない")
def then_score_not_saved(context: dict[str, Any]) -> None:
    # In the domain layer "not saved" means no aggregate was produced (there is
    # no DB here). The real persistence assertion lands in T-05/T-08.
    assert context["score"] is None
