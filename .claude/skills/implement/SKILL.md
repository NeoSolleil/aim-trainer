---
name: implement
description: SDD段階4（実装）。design.md・acceptance.feature・tasks.md を入力に、TDD（red→green→refactor）で実装する。Gherkin を pytest-bdd に変換してテストを先に作り、最小実装で通す。
argument-hint: [feature-folder]
disable-model-invocation: true
---

# implement — 実装（SDD 段階4・TDD）

tasks.md の順に、**テストを先に書いて**実装する。Gherkin 原本は参照・変換するだけ（新規作成しない）。

> **実行**: backend-engineer / frontend-engineer が担当。完了後にレビュアーを回す（末尾「完了後のレビュー」）。

## 最初に参照する

- `bdd`（Gherkin→pytest-bdd 変換）・`backend-architecture`・`frontend-architecture`・`e2e-testing`
- 該当レイヤの `.claude/rules/`（domain 純粋・API は Pydantic 検証・infra は ORM 経由 等）

## 前提（着手条件）

- `tasks.md` の `Status:` が **Approved**（tasks 完了・人間承認済み）であること。`Draft` なら implement に着手しない。

## 手順（tasks.md の各タスクを依存順に）

1. **Red**: そのタスクが対象とする acceptance.feature のシナリオを pytest-bdd のステップ定義（`backend/tests/step_defs/`）に変換し、`specs/<feature>/acceptance.feature` を参照してバインドする。実行して**失敗**を確認。
2. **Green**: 正しい CA レイヤに**最小限**のコードを書いて通す。依存方向（domain は何も import しない 等）を守る（import-linter／フックが強制）。
3. **Refactor**: green を保ったまま整理。品質ゲート（ruff／pyright／import-linter／xenon・eslint／prettier／tsc）を緑にする。
4. **frontend**: components／canvas／api を `frontend-architecture` に従って実装。E2E は playwright-bdd（`e2e-testing`）で acceptance を再利用し、`data-testid` を必須にする。
5. 仕様／シナリオに無い機能を足さない。**テストの無い実装をコミットしない**（pre-commit／CI が強制）。

## pytest-bdd のバインド

- ステップ定義は backend 側（`backend/tests/step_defs/`）に置くが、**Gherkin 原本は `specs/<feature>/acceptance.feature`**。backend から相対参照する（コピーを作らない）。
- シナリオの `@R-x` タグで、どの要件を検証しているか追える状態を保つ。

## 制約（ハーネス）

- Gherkin・要件の新規作成禁止（参照・変換のみ）。
- TDD 順（red → green → refactor）。最小実装に徹する。
- 全品質ゲートが緑になるまで「完了」としない。

## 完了後のレビュー（ループ）

実装が緑になったら、独立レビュアーを回す：

- **spec-compliance**（仕様適合・スコープ・CA）／**test-coverage**（要件→シナリオ→テストの網羅）／**code-reviewer**（バグ・可読性・重複・簡潔さ）。
- 指摘は engineer が修正 → 再レビュー。**全クリア＋人間承認**まで反復する。

## 完了の定義

対象シナリオが全て pass、品質ゲートが全て緑、レビュアー3体の指摘なし、人間レビュー承認。→ その機能は完成（必要なら次の機能へ）。
