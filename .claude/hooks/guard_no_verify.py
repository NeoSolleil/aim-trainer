#!/usr/bin/env python3
"""PreToolUse ガード（Bash）: pre-commit を迂回する操作を禁止する。

git commit / git push に --no-verify が付いた場合は拒否する。
pre-commit（層③a）はローカルの関門であり、フック失敗を迂回させない。
例外時は fail-open（許可）。
"""

import json
import re
import sys

# 1コマンド内（パイプ/連結の手前まで）で git commit|push に --no-verify が付く
NO_VERIFY = re.compile(r"\bgit\b[^\n|;&]*\b(?:commit|push)\b[^\n|;&]*--no-verify\b")


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
    if data.get("tool_name") != "Bash":
        return
    command = (data.get("tool_input") or {}).get("command") or ""
    if NO_VERIFY.search(command):
        deny(
            "pre-commit を迂回する --no-verify は禁止です。"
            "フックが失敗したら迂回せず原因を修正してください（層③a）。"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
