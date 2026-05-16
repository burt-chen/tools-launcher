#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""設定工具的解鎖密碼 — 直接改 tools.json 的 hidden / unlock_hash。

用法:
  python set_unlock.py --list                  列出所有工具與目前狀態
  python set_unlock.py <tool_id> <password>    設定解鎖密碼(同時設為隱藏)
  python set_unlock.py <tool_id> --public      取消隱藏,變回公開

改完記得 push 才會對使用者生效:
  git add tools.json
  git commit -m "更新解鎖設定"
  git push

注意:更改密碼只對「還沒解鎖過的人」有效;已解鎖過的人不會被收回權限。
"""
import hashlib
import json
import sys
from pathlib import Path

TOOLS_JSON = Path(__file__).resolve().parent / "tools.json"


def _load() -> dict:
    return json.loads(TOOLS_JSON.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    TOOLS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _find(data: dict, tool_id: str) -> dict | None:
    for t in data.get("tools", []):
        if t.get("id") == tool_id:
            return t
    return None


def _print_list(data: dict) -> None:
    print("目前工具清單:")
    for t in data.get("tools", []):
        state = "隱藏" if t.get("hidden") else "公開"
        print(f"  {t.get('id', ''):26} [{state}]  {t.get('name', '')}")


def main(argv: list[str]) -> int:
    if not TOOLS_JSON.exists():
        print(f"[錯誤] 找不到 tools.json: {TOOLS_JSON}")
        return 1

    data = _load()

    if len(argv) == 1 and argv[0] == "--list":
        _print_list(data)
        return 0

    if len(argv) != 2:
        print(__doc__)
        _print_list(data)
        return 1

    tool_id, arg = argv
    tool = _find(data, tool_id)
    if tool is None:
        print(f"[錯誤] 找不到工具 id: {tool_id}\n")
        _print_list(data)
        return 1

    if arg == "--public":
        tool["hidden"] = False
        tool.pop("unlock_hash", None)
        _save(data)
        print(f"[完成] 已將「{tool.get('name', tool_id)}」設為公開。")
    else:
        password = arg
        digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
        tool["hidden"] = True
        tool["unlock_hash"] = digest
        _save(data)
        print(f"[完成] 已將「{tool.get('name', tool_id)}」設為隱藏。")
        print(f"  解鎖密碼  : {password}")
        print(f"  unlock_hash: {digest}")

    print()
    print("記得 push 才會對使用者生效:")
    print("  git add tools.json")
    print('  git commit -m "更新解鎖設定"')
    print("  git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
