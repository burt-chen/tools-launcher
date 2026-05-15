"""從遠端 URL(或本地檔)載入 tools.json,並提供離線快取。"""
from __future__ import annotations

import json
import urllib.request
from typing import Literal

from . import config

Source = Literal["online", "cached"]


def fetch_catalog(force: bool = False) -> tuple[dict, Source]:
    """回傳 (catalog_dict, source)。source 為 'online' 或 'cached'。

    online 失敗會 fallback 到 catalog_cache.json;若連快取也沒有則 raise。
    """
    config.ensure_dirs()
    try:
        req = urllib.request.Request(
            config.CATALOG_URL,
            headers={"User-Agent": f"{config.APP_NAME}-Launcher"},
        )
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as r:
            raw = r.read()
        data = json.loads(raw)
        _validate(data)
        config.CATALOG_CACHE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return data, "online"
    except Exception as e:
        if config.CATALOG_CACHE.exists() and not force:
            cached = json.loads(config.CATALOG_CACHE.read_text(encoding="utf-8"))
            return cached, "cached"
        raise RuntimeError(f"無法載入 catalog:{e}") from e


def _validate(data: dict) -> None:
    if not isinstance(data, dict) or "tools" not in data:
        raise ValueError("catalog 缺少 'tools' 欄位")
    if not isinstance(data["tools"], list):
        raise ValueError("'tools' 必須是 list")
    for i, t in enumerate(data["tools"]):
        for key in ("id", "name", "version", "url"):
            if key not in t:
                raise ValueError(f"tool[{i}] 缺少必要欄位:{key}")
