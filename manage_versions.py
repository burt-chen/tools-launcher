#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理 tools.json 的工具版本清單(多版本回滾用)。

用法:
  python manage_versions.py --list
  python manage_versions.py <tool_id> add <version> <url> [size_bytes]
  python manage_versions.py <tool_id> yank <version>      標記某版作廢(使用者選不到)
  python manage_versions.py <tool_id> unyank <version>    取消作廢

說明:
  - add:把版本加進 versions 清單,並設為最新版(同步更新 top-level version/url)。
  - yank:有問題的版本標記後,launcher 的版本選單不顯示它;記錄與 Release 都保留。
  - 改完 tools.json 要 git push 才會對使用者生效。
"""
import json
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent
TOOLS_JSON = _DIR / "tools.json"


def _load():
    return json.loads(TOOLS_JSON.read_text(encoding="utf-8"))


def _save(data):
    TOOLS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find(data, tool_id):
    for t in data.get("tools", []):
        if t.get("id") == tool_id:
            return t
    return None


def _find_ver(tool, version):
    for v in tool.get("versions", []):
        if v.get("version") == version:
            return v
    return None


def _print_list(data):
    for t in data.get("tools", []):
        latest = t.get("version", "")
        print(f"{t.get('id', '')}  ({t.get('name', '')})  最新:v{latest}")
        vers = t.get("versions", [])
        if not vers:
            print("    (無版本清單)")
        for v in vers:
            mark = "  <- 最新" if v.get("version") == latest else ""
            yk = "  [作廢]" if v.get("yanked") else ""
            print(f"    v{v.get('version', '')}{yk}{mark}")
        print()


def _push_hint():
    print()
    print("記得 push 才會對使用者生效:")
    print('  git add tools.json && git commit -m "更新版本清單" && git push')


def main(argv):
    if not TOOLS_JSON.exists():
        print(f"[錯誤] 找不到 tools.json: {TOOLS_JSON}")
        return 1
    data = _load()

    if len(argv) == 1 and argv[0] == "--list":
        _print_list(data)
        return 0

    if len(argv) < 3:
        print(__doc__)
        _print_list(data)
        return 1

    tool_id, action, version = argv[0], argv[1], argv[2]
    tool = _find(data, tool_id)
    if tool is None:
        print(f"[錯誤] 找不到工具 id: {tool_id}")
        return 1
    tool.setdefault("versions", [])

    if action == "add":
        if len(argv) < 4:
            print("[錯誤] add 需要 <version> <url> [size_bytes]")
            return 1
        url = argv[3]
        size = int(argv[4]) if len(argv) > 4 and argv[4].isdigit() else 0
        entry = _find_ver(tool, version)
        if entry is None:
            tool["versions"].append(
                {"version": version, "url": url, "size_bytes": size})
        else:
            entry["url"] = url
            entry["size_bytes"] = size
            entry.pop("yanked", None)
        tool["version"] = version
        tool["url"] = url
        tool["size_bytes"] = size
        _save(data)
        print(f"[完成] {tool_id} 已新增版本 v{version} 並設為最新。")
        _push_hint()
        return 0

    if action in ("yank", "unyank"):
        entry = _find_ver(tool, version)
        if entry is None:
            print(f"[錯誤] {tool_id} 沒有版本 v{version}")
            return 1
        if action == "yank":
            entry["yanked"] = True
            print(f"[完成] {tool_id} v{version} 已標記作廢。")
        else:
            entry.pop("yanked", None)
            print(f"[完成] {tool_id} v{version} 已取消作廢。")
        _save(data)
        _push_hint()
        return 0

    print(f"[錯誤] 未知動作: {action}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
