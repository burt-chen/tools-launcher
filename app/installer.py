"""下載 / 驗 hash / 解壓 zip / 安裝 pip 依賴 / 移除 / 維護 installed.json。"""
from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import config

ProgressCb = Callable[[int, int], None]  # (downloaded_bytes, total_bytes)


# ----- installed.json 讀寫 -----

def load_installed() -> dict:
    if not config.INSTALLED_JSON.exists():
        return {}
    try:
        return json.loads(config.INSTALLED_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_installed(data: dict) -> None:
    config.ensure_dirs()
    config.INSTALLED_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def installed_version(tool_id: str) -> str | None:
    return load_installed().get(tool_id, {}).get("version")


# ----- 下載 / 安裝 -----

def install(
    tool: dict,
    on_progress: ProgressCb | None = None,
    cancel_flag: Callable[[], bool] | None = None,
) -> Path:
    """下載 tool 的 zip → 驗 SHA256 → 解壓到 tools/{id}/ → pip install → 更新 installed.json。

    回傳安裝目錄路徑。
    """
    config.ensure_dirs()
    tool_id = tool["id"]
    dest_dir = config.TOOLS_DIR / tool_id
    staging = config.TOOLS_DIR / f"_{tool_id}_new"
    tmp_zip = config.TOOLS_DIR / f"_{tool_id}_download.zip"

    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    tmp_zip.unlink(missing_ok=True)
    staging.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256()
    total = int(tool.get("size_bytes") or 0)
    downloaded = 0

    req = urllib.request.Request(
        tool["url"],
        headers={"User-Agent": f"{config.APP_NAME}-Launcher"},
    )
    try:
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as r, open(tmp_zip, "wb") as f:
            if not total:
                cl = r.headers.get("Content-Length")
                if cl and cl.isdigit():
                    total = int(cl)
            while True:
                if cancel_flag and cancel_flag():
                    raise InterruptedError("使用者取消下載")
                chunk = r.read(config.DOWNLOAD_CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        tmp_zip.unlink(missing_ok=True)
        raise

    expected = tool.get("sha256")
    if expected:
        actual = sha.hexdigest()
        if actual.lower() != expected.lower():
            shutil.rmtree(staging, ignore_errors=True)
            tmp_zip.unlink(missing_ok=True)
            raise ValueError(f"SHA256 不符:預期 {expected},實際 {actual}")

    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            shipped = {
                n.replace("\\", "/").rstrip("/")
                for n in zf.namelist() if not n.endswith("/")
            }
            zf.extractall(staging)
    except zipfile.BadZipFile:
        shutil.rmtree(staging, ignore_errors=True)
        tmp_zip.unlink(missing_ok=True)
        raise ValueError("下載的檔案不是有效的 zip 檔")
    finally:
        tmp_zip.unlink(missing_ok=True)

    # 保留使用者資料:舊安裝目錄裡「新版 zip 沒有的檔」(工具自己產生的
    # 設定 / 新增資料)搬進新版,避免更新 / 切換版本 / 降版時被清掉。
    if dest_dir.exists():
        for old in dest_dir.rglob("*"):
            if not old.is_file():
                continue
            rel = old.relative_to(dest_dir).as_posix()
            if rel in shipped or rel == "_download.zip":
                continue
            target = staging / rel
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, target)
        shutil.rmtree(dest_dir, ignore_errors=True)

    shutil.move(str(staging), str(dest_dir))

    _pip_install_if_needed(dest_dir)

    installed_at = datetime.now().isoformat(timespec="seconds")
    installed = load_installed()
    installed[tool_id] = {
        "name": tool.get("name", tool_id),
        "version": tool["version"],
        "path": str(dest_dir),
        "installed_at": installed_at,
    }
    save_installed(installed)
    return dest_dir


def _pip_install_if_needed(dest_dir: Path) -> None:
    """如果工具包含 requirements.txt，用 pip 安裝到工具目錄內。

    重要：強制 pip 抓「launcher 自己 Python 版本」的 wheel，而不是
    讓內嵌/系統 pip 用自己的 Python 版本決定。

    背景:launcher.exe (frozen by PyInstaller) 的 Python 版本由 build.bat
    打包當下的 Python 決定;但 _find_python() 回傳的 pip 直譯器可能是
    版本不同的內嵌 Python 或系統 Python。兩者不一致時,pip 會抓到
    錯版 wheel (例如裝了 cp313 .pyd 給 cp314 launcher 載入會炸)。
    """
    req_file = dest_dir / "requirements.txt"
    if not req_file.exists():
        return

    python = _find_python()
    if python is None:
        raise RuntimeError(
            "此工具需要額外的 Python 套件，但找不到 Python 直譯器。\n"
            "請先安裝 Python：https://www.python.org/downloads/\n"
            "（安裝時請勾選「Add Python to PATH」）"
        )

    # launcher 自己的 Python 版本（cp314 / cp313 等）—— 工具未來會在
    # launcher 內被載入，所以 wheel 一定要對應這個版本
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    abi_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"

    cmd = [
        python, "-m", "pip", "install",
        "-r", str(req_file),
        "--target", str(dest_dir),
        # 強制鎖 wheel tag 為 launcher 自己的 Python 版本
        "--python-version", py_ver,
        "--implementation", "cp",
        "--abi", abi_tag,
        "--platform", "win_amd64",
        # cross-version 安裝必須只用 wheel（pip 無法跨版本編譯 sdist）
        "--only-binary", ":all:",
        "--quiet",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"pip install 失敗 (target Python {py_ver}, abi {abi_tag}):\n"
            f"{result.stderr}"
        )


def _find_python() -> str | None:
    """找到可用的 Python 執行檔路徑。優先使用內嵌 Python。"""
    # 1. 優先：launcher 旁的內嵌 Python
    if config.PYTHON_EXE.exists() and _check_python(str(config.PYTHON_EXE)):
        return str(config.PYTHON_EXE)

    # 2. 開發模式 fallback：目前執行的 Python（非 frozen exe）
    if not getattr(sys, "frozen", False):
        if _check_python(sys.executable):
            return sys.executable

    # 3. 系統 PATH
    for candidate in ("python", "python3", "py"):
        if _check_python(candidate):
            return candidate
    return None


def _check_python(cmd: str) -> bool:
    try:
        result = subprocess.run(
            [cmd, "-c", "import sys; print(sys.version)"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# ----- 移除 -----

def uninstall(tool_id: str) -> None:
    dest_dir = config.TOOLS_DIR / tool_id
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)
    installed = load_installed()
    if tool_id in installed:
        del installed[tool_id]
        save_installed(installed)
