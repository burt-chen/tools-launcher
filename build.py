"""打包 Launcher 為單一 exe（取代 build.bat）。

設計重點：launcher.exe 是「動態載入第三方工具」的宿主，工具可能 import
任何 Python 標準庫。為了讓 PyInstaller frozen 後 launcher 也能滿足這些
import，本腳本從 sys.stdlib_module_names 自動把所有 stdlib 頂層模組都
登記為 hidden-import，避免「跑到才發現某個 stdlib 沒打包」的坑。

使用：
    py build.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
NAME = "MyToolsLauncher"
ENTRY = "run.py"


# 大宗套件用 --collect-submodules 確保子模組完整（避免「import xxx.yyy 失敗」）
COLLECT_SUBMODULES = [
    "unittest", "doctest", "logging",
    "urllib", "http", "email", "html", "xml", "xmlrpc",
    "concurrent", "asyncio", "multiprocessing",
    "tkinter", "ctypes", "importlib",
    "collections", "encodings",
]


def main() -> None:
    os.chdir(HERE)

    # 清掉舊產物
    for path in ("build", "dist", f"{NAME}.spec"):
        p = HERE / path
        if p.is_dir():
            shutil.rmtree(p)
        elif p.is_file():
            p.unlink()

    # 取 python3.dll 位置（穩定 ABI 轉發 DLL，動態載入的工具帶 stable-ABI .pyd 時要它）
    py3dll = Path(sys.executable).parent / "python3.dll"
    if not py3dll.is_file():
        raise FileNotFoundError(f"找不到 {py3dll}")

    # 全部 stdlib 頂層模組（Python 3.10+ 內建集合）
    stdlib = sorted(sys.stdlib_module_names)

    cmd: list[str] = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NAME,
        "--add-binary", f"{py3dll};.",
    ]

    # 全部 stdlib 一次納入
    for mod in stdlib:
        cmd.extend(["--hidden-import", mod])

    # 大宗套件再用 --collect-submodules 補齊子模組
    for mod in COLLECT_SUBMODULES:
        cmd.extend(["--collect-submodules", mod])

    cmd.append(ENTRY)

    print(f"=== PyInstaller 打包 {NAME}.exe ===")
    print(f"納入 {len(stdlib)} 個 stdlib 頂層模組 + {len(COLLECT_SUBMODULES)} 個 collect-submodules")
    print()

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[錯誤] PyInstaller 打包失敗 (exit {result.returncode})")
        sys.exit(result.returncode)

    out = HERE / "dist" / f"{NAME}.exe"
    if out.is_file():
        size_mb = out.stat().st_size / 1024 / 1024
        print(f"\n[完成] {out}")
        print(f"       大小: {size_mb:.2f} MB")
    else:
        print("\n[警告] PyInstaller 回傳成功但找不到產出檔")
        sys.exit(1)


if __name__ == "__main__":
    main()
