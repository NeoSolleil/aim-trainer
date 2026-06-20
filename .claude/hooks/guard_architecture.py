#!/usr/bin/env python3
"""PreToolUse ガード（Write|Edit）: アーキテクチャ違反の編集をその場でブロックする。

- domain / application 配下に web/ORM フレームワークを import しない
  （fastapi / starlette / sqlalchemy / pydantic / pydantic_settings / uvicorn）
- backend/app 配下に直接SQL（text(...) / exec_driver_sql(...)）を書かない

違反時は PreToolUse の permissionDecision=deny を返してツール実行を止める。
ガード自身が壊れても作業を止めないよう、例外時は fail-open（許可）。
最終的な関門として import-linter / pre-commit / CI が残る。
"""

import json
import re
import sys

# 行頭の import/from 文のみを対象（コメントや docstring の散文・大文字表記は拾わない）
FORBIDDEN_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+"
    r"(fastapi|starlette|sqlalchemy|pydantic|pydantic_settings|uvicorn)\b",
    re.MULTILINE,
)
# SQLAlchemy の生SQL口（直前が識別子文字でない text( / exec_driver_sql(）
RAW_SQL = re.compile(r"(?:^|[^A-Za-z0-9_.])(text|exec_driver_sql)\s*\(", re.MULTILINE)


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input") or {}
    file_path = (tool_input.get("file_path") or "").replace("\\", "/")
    if not file_path:
        return
    # Write は content、Edit は new_string。書き込まれる本文を結合して検査する。
    pieces = [tool_input.get("content"), tool_input.get("new_string")]
    content = "\n".join(p for p in pieces if isinstance(p, str))
    if not content:
        return

    in_domain_or_app = (
        "/backend/app/domain/" in file_path
        or "/backend/app/application/" in file_path
        or file_path.startswith("backend/app/domain/")
        or file_path.startswith("backend/app/application/")
    )
    if in_domain_or_app:
        m = FORBIDDEN_IMPORT.search(content)
        if m:
            deny(
                "Clean Architecture 違反: domain/application は web/ORM フレームワーク"
                f"（{m.group(1)}）を import できません。"
                "入出力検証は adapters/schemas、永続化は infrastructure に置いてください。"
                "（.claude/rules/ 参照。import-linter でも強制）"
            )

    in_backend_app = "/backend/app/" in file_path or file_path.startswith("backend/app/")
    if in_backend_app and RAW_SQL.search(content):
        deny(
            "ORM必須・直接SQL禁止: text(...) / exec_driver_sql(...) は使用できません。"
            "SQLAlchemy 2.0 の ORM でアクセスしてください。"
            "（.claude/rules/backend-infrastructure.md 参照）"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # fail-open: ガードが壊れても編集をブロックしない（後段の関門が残る）
        sys.exit(0)
