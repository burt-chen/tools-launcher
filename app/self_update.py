"""Launcher 自我更新 — 偵測新版、下載、改名換版、重啟。

只在打包成 exe(frozen)時有作用;開發模式(python run.py)會略過。

換版機制:執行中的 exe 不能被覆蓋,但可以改名。
  1. 下載新 exe → MyToolsLauncher.new.exe
  2. 執行中的 MyToolsLauncher.exe 改名 → MyToolsLauncher.old.exe
  3. .new.exe 改名 → MyToolsLauncher.exe
  4. 啟動新 exe,舊程式關閉
  5. 新版下次啟動時清掉 .old.exe
"""
from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

from . import config


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _exe_paths() -> tuple[Path, Path, Path]:
    """回傳 (目前 exe, .new.exe, .old.exe) 路徑。"""
    exe = Path(sys.executable)
    new = exe.with_name(exe.stem + ".new" + exe.suffix)
    old = exe.with_name(exe.stem + ".old" + exe.suffix)
    return exe, new, old


def cleanup_old() -> None:
    """啟動時清掉上次更新殘留的 .old.exe(清不掉就下次再清)。"""
    if not is_frozen():
        return
    _, _, old = _exe_paths()
    if old.exists():
        try:
            old.unlink()
        except Exception:
            pass


def _ver_tuple(v: str) -> tuple:
    out = []
    for x in str(v).split("."):
        try:
            out.append(int(x))
        except ValueError:
            out.append(0)
    return tuple(out)


def available_update(catalog: dict) -> tuple[str, str] | None:
    """檢查 catalog 的 launcher 區塊有無比目前新的版本。

    回傳 (version, url);沒有或開發模式則回 None。
    """
    if not is_frozen():
        return None
    info = (catalog or {}).get("launcher") or {}
    version = str(info.get("version", "")).strip()
    url = str(info.get("url", "")).strip()
    if version and url and _ver_tuple(version) > _ver_tuple(config.APP_VERSION):
        return (version, url)
    return None


def _download(url: str, dest: Path, on_progress=None) -> None:
    req = urllib.request.Request(
        url, headers={"User-Agent": f"{config.APP_NAME}-Launcher"})
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as r, open(dest, "wb") as f:
        total = 0
        cl = r.headers.get("Content-Length")
        if cl and cl.isdigit():
            total = int(cl)
        downloaded = 0
        while True:
            chunk = r.read(config.DOWNLOAD_CHUNK)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if on_progress:
                on_progress(downloaded, total)


def do_update(url: str, on_progress=None) -> None:
    """下載新 exe → 改名換版 → 啟動新版。

    成功回傳後,呼叫端應立即關閉目前程式。
    """
    exe, new, old = _exe_paths()

    # 1. 下載新 exe 到 .new.exe
    if new.exists():
        new.unlink()
    _download(url, new, on_progress)

    # 2. 清掉殘留的 .old.exe(否則步驟 3 改名會撞名)
    if old.exists():
        old.unlink()

    # 3. 執行中的 exe 改名 → .old.exe(執行中可改名)
    exe.rename(old)

    # 4. 新 exe 改名 → 正式名稱;失敗則把舊的改回來
    try:
        new.rename(exe)
    except Exception:
        old.rename(exe)
        raise

    # 5. 啟動新版
    subprocess.Popen([str(exe)], cwd=str(exe.parent))
