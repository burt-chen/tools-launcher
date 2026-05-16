"""Launcher 使用者設定的讀寫。"""
from __future__ import annotations

import json

from . import config

DEFAULTS = {
    # 切換工具時是否保留已載入的工具畫面與狀態
    "keep_tools_loaded": True,
}


def load() -> dict:
    s = dict(DEFAULTS)
    if config.SETTINGS_JSON.exists():
        try:
            data = json.loads(config.SETTINGS_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                s.update(data)
        except Exception:
            pass
    return s


def save(s: dict) -> None:
    config.ensure_dirs()
    config.SETTINGS_JSON.write_text(
        json.dumps(s, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
