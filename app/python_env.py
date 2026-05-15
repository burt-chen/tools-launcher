"""內嵌 Python 環境管理。

負責：
- 偵測 launcher 旁的 python/ 目錄是否就緒
- 第一次執行時自動下載 Python Embeddable Package 並安裝 pip
- 提供 embedded Python 執行檔路徑供 installer 使用
"""
from __future__ import annotations

import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

# Python 版本與下載 URL（amd64 / 64-bit Windows）
_PY_VERSION = "3.13.3"
_EMBED_URL = (
    f"https://www.python.org/ftp/python/{_PY_VERSION}/"
    f"python-{_PY_VERSION}-embed-amd64.zip"
)
_GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def launcher_dir() -> Path:
    """Launcher 所在目錄（frozen exe 旁，或 source 的 小工具管理/ 根目錄）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # 開發模式：此檔在 app/，往上一層是 小工具管理/
    return Path(__file__).parent.parent


def python_dir() -> Path:
    return launcher_dir() / "python"


def python_exe() -> Path:
    return python_dir() / "python.exe"


def pip_exe() -> Path:
    return python_dir() / "Scripts" / "pip.exe"


def is_ready() -> bool:
    """內嵌 Python 已下載且 pip 可用。"""
    return python_exe().exists() and pip_exe().exists()


# ── 安裝流程 ──────────────────────────────────────────────────────────────────

def setup(on_progress: Callable[[str, int], None] | None = None) -> None:
    """下載並設定內嵌 Python 環境。

    on_progress(message, percent) 供 UI 更新進度。
    """
    py_dir = python_dir()
    py_dir.mkdir(parents=True, exist_ok=True)

    # 1. 下載 embeddable zip
    zip_path = py_dir / "_python_embed.zip"
    _download(_EMBED_URL, zip_path, label="Python 核心", on_progress=on_progress, start=0, end=60)

    # 2. 解壓縮
    _progress(on_progress, "解壓縮 Python 核心…", 62)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(py_dir)
    zip_path.unlink(missing_ok=True)

    # 3. 啟用 site-packages（取消 ._pth 裡的 #import site）
    _progress(on_progress, "設定 Python 環境…", 65)
    for pth_file in py_dir.glob("*._pth"):
        text = pth_file.read_text(encoding="utf-8")
        text = text.replace("#import site", "import site")
        pth_file.write_text(text, encoding="utf-8")

    # 4. 下載 get-pip.py
    get_pip = py_dir / "_get-pip.py"
    _download(_GET_PIP_URL, get_pip, label="pip 安裝器", on_progress=on_progress, start=66, end=80)

    # 5. 執行 get-pip.py
    _progress(on_progress, "安裝 pip…", 82)
    result = subprocess.run(
        [str(python_exe()), str(get_pip)],
        capture_output=True, text=True,
    )
    get_pip.unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(f"pip 安裝失敗：\n{result.stderr}")

    _progress(on_progress, "完成", 100)


# ── 內部工具 ──────────────────────────────────────────────────────────────────

def _progress(cb: Callable | None, msg: str, pct: int) -> None:
    if cb:
        cb(msg, pct)


def _download(
    url: str,
    dest: Path,
    label: str,
    on_progress: Callable | None,
    start: int,
    end: int,
) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "MyTools-Setup"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        downloaded = 0
        chunk = 64 * 1024
        while True:
            data = r.read(chunk)
            if not data:
                break
            f.write(data)
            downloaded += len(data)
            if total and on_progress:
                ratio = downloaded / total
                pct = int(start + (end - start) * ratio)
                on_progress(f"下載 {label}… {downloaded // 1024} KB / {total // 1024} KB", pct)
