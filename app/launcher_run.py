"""動態載入已安裝工具的 UI 框架。"""
from __future__ import annotations

import importlib.util
import sys
import tkinter as tk
from pathlib import Path

from . import installer


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

    # 將工具目錄加入 sys.path，讓工具可以 import 自己的套件與模組
    tool_dir_str = str(tool_dir)
    if tool_dir_str not in sys.path:
        sys.path.insert(0, tool_dir_str)

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
