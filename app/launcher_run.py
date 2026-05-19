"""動態載入已安裝工具的 UI 框架。"""
from __future__ import annotations

import importlib.util
import os
import sys
import tkinter as tk
from pathlib import Path

from . import installer

# 保留 os.add_dll_directory 回傳的 handle,行程存活期間目錄才持續有效
_DLL_DIR_HANDLES: list = []


def _purge_tool_modules(tool_dir: Path, tool_id: str) -> None:
    """清掉上次載入此工具殘留在 sys.modules 的模組。

    工具更新(重新下載解壓)後,若不清快取,main_frame 內
    `import pack_gui` 等仍會命中舊模組 → 畫面還是舊版。
    這裡移除 `_tool_{id}` 及所有檔案位於此工具目錄內的模組,
    下次載入就會重新 import 到新碼。
    """
    prefix = os.path.normcase(str(tool_dir)) + os.sep
    for name in list(sys.modules):
        if name == f"_tool_{tool_id}":
            del sys.modules[name]
            continue
        mod = sys.modules.get(name)
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        try:
            if os.path.normcase(str(Path(f).resolve())).startswith(prefix):
                del sys.modules[name]
        except Exception:
            pass


def load_frame(parent: tk.Widget, tool_id: str) -> tk.Widget:
    """動態載入工具的 create_frame，回傳 Tkinter Frame。

    工具 zip 解壓後必須在根目錄提供 main_frame.py，
    其中包含 create_frame(parent: tk.Widget) -> ttk.Frame。
    """
    info = installer.load_installed().get(tool_id)
    if not info:
        raise RuntimeError(f"工具尚未安裝:{tool_id}")

    tool_dir = Path(info["path"])
    main_frame_path = tool_dir / "main_frame.py"

    if not main_frame_path.exists():
        raise FileNotFoundError(
            f"找不到 main_frame.py\n"
            f"路徑:{main_frame_path}\n\n"
            "工具 zip 必須在根目錄提供 main_frame.py，\n"
            "並實作 create_frame(parent) -> ttk.Frame 函數。"
        )

    # 更新工具後要吃到新碼:先清掉上次殘留的模組快取
    _purge_tool_modules(tool_dir.resolve(), tool_id)

    # 將工具目錄放到 sys.path 最前,讓它 import 到自己(且優先於別的工具)
    tool_dir_str = str(tool_dir)
    if tool_dir_str in sys.path:
        sys.path.remove(tool_dir_str)
    sys.path.insert(0, tool_dir_str)

    # 把工具目錄(及常見的 bin/)加入 DLL 搜尋路徑。
    # Python 3.8+ 不再用 PATH 找相依 DLL;含原生套件的工具(如
    # PyMuPDF/fitz)在凍結的 launcher 行程內會「DLL load failed /
    # 找不到指定的模組」。獨立跑 python 沒事,就是差這個。
    if hasattr(os, "add_dll_directory"):
        for d in (tool_dir, tool_dir / "bin"):
            try:
                if d.is_dir():
                    _DLL_DIR_HANDLES.append(os.add_dll_directory(str(d)))
            except OSError:
                pass

    spec = importlib.util.spec_from_file_location(f"_tool_{tool_id}", main_frame_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "create_frame"):
        raise AttributeError(
            f"main_frame.py 缺少 create_frame(parent) 函數\n"
            f"請在工具的 main_frame.py 中定義:\n\n"
            "def create_frame(parent: tk.Widget) -> ttk.Frame:\n"
            "    ..."
        )

    return mod.create_frame(parent)
