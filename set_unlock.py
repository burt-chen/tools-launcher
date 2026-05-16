#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""設定工具的解鎖密碼 — 改 tools.json,並在本機保留明碼記錄。

用法:
  python set_unlock.py --list                  列出所有工具狀態與已設定的密碼
  python set_unlock.py <tool_id> <password>    設定工具的個別解鎖密碼(設為隱藏)
  python set_unlock.py <tool_id> --public       取消隱藏,變回公開
  python set_unlock.py --master <password>      設定共用密碼(可解鎖全部隱藏工具)
  python set_unlock.py --master --remove        移除共用密碼

說明:
  - tools.json 只存密碼的 sha256(公開);明碼記錄存在本機 unlock_records.json
    (已列入 .gitignore,不會上傳)。
  - 共用密碼:使用者輸入它即可一次解鎖所有隱藏工具。
  - 改完 tools.json 後要 git push 才會對使用者生效。
"""
import hashlib
import json
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent
TOOLS_JSON = _DIR / "tools.json"
RECORDS_JSON = _DIR / "unlock_records.json"


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_records() -> dict:
    rec = _load_json(RECORDS_JSON, {})
    if not isinstance(rec, dict):
        rec = {}
    rec.setdefault("master", "")
    rec.setdefault("tools", {})
    return rec


def _find_tool(data: dict, tool_id: str):
    for t in data.get("tools", []):
        if t.get("id") == tool_id:
            return t
    return None


def _print_list(data: dict, rec: dict) -> None:
    master = rec.get("master", "")
    print(f"共用密碼: {master if master else '(未設定)'}")
    print()
    print("工具清單:")
    for t in data.get("tools", []):
        tid = t.get("id", "")
        state = "隱藏" if t.get("hidden") else "公開"
        pw = rec.get("tools", {}).get(tid, "")
        pw_text = f"   密碼:{pw}" if (t.get("hidden") and pw) else ""
        print(f"  {tid:24} [{state}]  {t.get('name', '')}{pw_text}")


def _push_hint() -> None:
    print()
    print("記得 push 才會對使用者生效:")
    print("  git add tools.json")
    print('  git commit -m "更新解鎖設定"')
    print("  git push")


def main(argv: list[str]) -> int:
    if not TOOLS_JSON.exists():
        print(f"[錯誤] 找不到 tools.json: {TOOLS_JSON}")
        return 1

    data = _load_json(TOOLS_JSON, {})
    rec = _load_records()

    # --list
    if len(argv) == 1 and argv[0] == "--list":
        _print_list(data, rec)
        return 0

    # --master <password> / --master --remove
    if argv and argv[0] == "--master":
        if len(argv) == 2 and argv[1] == "--remove":
            data.pop("master_unlock_hash", None)
            rec["master"] = ""
            _save_json(TOOLS_JSON, data)
            _save_json(RECORDS_JSON, rec)
            print("[完成] 已移除共用密碼。")
            _push_hint()
            return 0
        if len(argv) == 2:
            password = argv[1]
            data["master_unlock_hash"] = _sha256(password)
            rec["master"] = password
            _save_json(TOOLS_JSON, data)
            _save_json(RECORDS_JSON, rec)
            print(f"[完成] 已設定共用密碼: {password}")
            _push_hint()
            return 0
        print(__doc__)
        return 1

    # <tool_id> <password> / <tool_id> --public
    if len(argv) == 2:
        tool_id, arg = argv
        tool = _find_tool(data, tool_id)
        if tool is None:
            print(f"[錯誤] 找不到工具 id: {tool_id}\n")
            _print_list(data, rec)
            return 1
        if arg == "--public":
            tool["hidden"] = False
            tool.pop("unlock_hash", None)
            rec["tools"].pop(tool_id, None)
            _save_json(TOOLS_JSON, data)
            _save_json(RECORDS_JSON, rec)
            print(f"[完成] 已將「{tool.get('name', tool_id)}」設為公開。")
        else:
            password = arg
            tool["hidden"] = True
            tool["unlock_hash"] = _sha256(password)
            rec["tools"][tool_id] = password
            _save_json(TOOLS_JSON, data)
            _save_json(RECORDS_JSON, rec)
            print(f"[完成] 已將「{tool.get('name', tool_id)}」設為隱藏。")
            print(f"  解鎖密碼: {password}")
        _push_hint()
        return 0

    print(__doc__)
    _print_list(data, rec)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
