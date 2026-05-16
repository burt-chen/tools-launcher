"""Launcher 使用者設定的讀寫,含我的最愛與自訂分組。"""
from __future__ import annotations

import json

from . import config

DEFAULTS = {
    # 切換工具時是否保留已載入的工具畫面與狀態
    "keep_tools_loaded": True,
    # 我的最愛:工具 id 清單
    "favorites": [],
    # 自訂分組:[{"name": str, "tools": [tool_id, ...]}]
    "groups": [],
    # 使用者自訂的工具顯示名稱:{tool_id: name}
    "tool_names": {},
    # 已解鎖的隱藏工具 id 清單
    "unlocked": [],
}


def load() -> dict:
    s = {"keep_tools_loaded": True, "favorites": [], "groups": [],
         "tool_names": {}, "unlocked": []}
    if config.SETTINGS_JSON.exists():
        try:
            data = json.loads(config.SETTINGS_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                s.update(data)
        except Exception:
            pass
    s.setdefault("favorites", [])
    s.setdefault("groups", [])
    s.setdefault("tool_names", {})
    s.setdefault("unlocked", [])
    return s


def save(s: dict) -> None:
    config.ensure_dirs()
    config.SETTINGS_JSON.write_text(
        json.dumps(s, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ----- 我的最愛 -----

def is_favorite(s: dict, tool_id: str) -> bool:
    return tool_id in s.get("favorites", [])


def toggle_favorite(s: dict, tool_id: str) -> None:
    favs = s.setdefault("favorites", [])
    if tool_id in favs:
        favs.remove(tool_id)
    else:
        favs.append(tool_id)


# ----- 自訂工具名稱 -----

def tool_display_name(s: dict, tool_id: str, default: str) -> str:
    """回傳工具顯示名稱:有自訂用自訂,否則用 default。"""
    custom = s.get("tool_names", {}).get(tool_id)
    return custom if custom else default


def set_tool_name(s: dict, tool_id: str, name: str) -> None:
    """設定自訂名稱;name 為空字串代表還原預設。"""
    names = s.setdefault("tool_names", {})
    if name:
        names[tool_id] = name
    else:
        names.pop(tool_id, None)


def has_custom_name(s: dict, tool_id: str) -> bool:
    return bool(s.get("tool_names", {}).get(tool_id))


# ----- 分組 -----

def group_of(s: dict, tool_id: str) -> str | None:
    for g in s.get("groups", []):
        if tool_id in g.get("tools", []):
            return g["name"]
    return None


def assign_group(s: dict, tool_id: str, group_name: str | None) -> None:
    """把工具指派到某群組;group_name 為 None / '' 代表移出所有群組(未分組)。"""
    for g in s.get("groups", []):
        if tool_id in g.get("tools", []):
            g["tools"].remove(tool_id)
    if group_name:
        for g in s.get("groups", []):
            if g["name"] == group_name:
                g.setdefault("tools", []).append(tool_id)
                return


def add_group(s: dict, name: str) -> bool:
    """新增群組,名稱重複回傳 False。"""
    groups = s.setdefault("groups", [])
    if any(g["name"] == name for g in groups):
        return False
    groups.append({"name": name, "tools": []})
    return True


def rename_group(s: dict, old: str, new: str) -> None:
    for g in s.get("groups", []):
        if g["name"] == old:
            g["name"] = new
            return


def remove_group(s: dict, name: str) -> None:
    """刪除群組;裡面的工具自動變回未分組。"""
    s["groups"] = [g for g in s.get("groups", []) if g["name"] != name]


def grouped_sections(tool_ids: list[str], s: dict) -> list[tuple[str, str, list[str]]]:
    """把工具 id 依 未分組 → 我的最愛 → 各自訂群組 排序分區。

    回傳 [(title, kind, [tool_id, ...])];kind 為 ungrouped / favorites / group。

    規則:
    - 我的最愛是獨立分區。工具可同時出現在「我的最愛」與某個自訂群組。
    - 在我的最愛 = 視為已分組,所以不會出現在未分組。
    - 未分組 = 不在我的最愛、也不在任何自訂群組。
    - 自訂群組即使是空的也會列出(方便管理)。
    """
    fav_set = set(s.get("favorites", []))
    favs: list[str] = []
    by_group: dict[str, list[str]] = {}
    ungrouped: list[str] = []

    for tid in tool_ids:
        in_fav = tid in fav_set
        grp = group_of(s, tid)
        if in_fav:
            favs.append(tid)
        if grp:
            by_group.setdefault(grp, []).append(tid)
        if not in_fav and not grp:
            ungrouped.append(tid)

    sections: list[tuple[str, str, list[str]]] = []
    if ungrouped:
        sections.append(("未分組", "ungrouped", ungrouped))
    if favs:
        sections.append(("我的最愛", "favorites", favs))
    for grp in s.get("groups", []):
        sections.append((grp["name"], "group", by_group.get(grp["name"], [])))
    return sections
