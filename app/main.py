"""Tkinter Launcher UI。"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from . import catalog, config, installer, launcher_run, python_env


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{config.APP_NAME} — 工具啟動器")
        self.geometry("900x620")
        self.minsize(700, 480)

        self._open_tabs: dict[str, ToolTabWrapper] = {}

        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.catalog_tab = CatalogTab(self.notebook, self)
        self.notebook.add(self.catalog_tab, text="  工具清單  ")

        self.status_var = tk.StringVar(value="就緒")
        statusbar = ttk.Frame(self, padding=(10, 3), relief="sunken")
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(statusbar, textvariable=self.status_var).pack(side=tk.LEFT)

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    def open_tool_tab(self, tool: dict) -> None:
        tool_id = tool["id"]
        if tool_id in self._open_tabs:
            self.notebook.select(self._open_tabs[tool_id])
            return
        wrapper = ToolTabWrapper(self.notebook, tool, self)
        self.notebook.add(wrapper, text=f"  {tool['name']}  ")
        self.notebook.select(wrapper)
        self._open_tabs[tool_id] = wrapper

    def close_tool_tab(self, tool_id: str, wrapper: "ToolTabWrapper | None" = None) -> None:
        if wrapper is None:
            wrapper = self._open_tabs.get(tool_id)
        if wrapper is None:
            return
        self.notebook.forget(wrapper)
        self._open_tabs.pop(tool_id, None)
        wrapper.destroy()


class CatalogTab(ttk.Frame):
    """工具清單分頁。"""

    def __init__(self, master: tk.Widget, app: LauncherApp) -> None:
        super().__init__(master)
        self.app = app
        self._catalog: dict = {"tools": []}
        self._installed: dict = {}
        self._cards: dict[str, ToolCard] = {}
        self._cancel_flags: dict[str, bool] = {}

        self._build_ui()
        self.after(100, self.refresh_catalog)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="刷新", command=self.refresh_catalog).pack(side=tk.LEFT)
        ttk.Label(toolbar, text="搜尋:").pack(side=tk.LEFT, padx=(12, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_list())
        ttk.Entry(toolbar, textvariable=self.search_var, width=24).pack(side=tk.LEFT)

        self.source_label = ttk.Label(toolbar, text="")
        self.source_label.pack(side=tk.RIGHT)

        container = ttk.Frame(self)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        self.canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.list_frame = ttk.Frame(self.canvas)
        self.list_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self.list_window, width=e.width),
        )
        # 只在滑鼠進入清單區時綁定滾輪，避免影響其他分頁的滾動元件
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, e: tk.Event) -> None:
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    # ---------- 資料 ----------

    def refresh_catalog(self) -> None:
        self.app.set_status("正在載入清單…")
        self.source_label.config(text="")

        def worker() -> None:
            try:
                data, source = catalog.fetch_catalog()
                self.after(0, self._on_catalog_loaded, data, source, None)
            except Exception as e:
                self.after(0, self._on_catalog_loaded, None, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_catalog_loaded(self, data: dict | None, source: str | None, err: str | None) -> None:
        if err:
            self.app.set_status("載入清單失敗")
            messagebox.showerror("錯誤", f"無法載入工具清單:\n{err}\n\nCatalog URL:\n{config.CATALOG_URL}")
            return
        self._catalog = data or {"tools": []}
        self._installed = installer.load_installed()
        n = len(self._catalog.get("tools", []))
        src_text = "線上" if source == "online" else "離線快取"
        self.source_label.config(text=f"來源:{src_text}")
        self.app.set_status(f"已載入 {n} 個工具")
        self._render_list()

    # ---------- 渲染 ----------

    def _render_list(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._cards.clear()

        keyword = self.search_var.get().strip().lower()
        tools = self._catalog.get("tools", [])
        if keyword:
            tools = [
                t for t in tools
                if keyword in t.get("name", "").lower()
                or keyword in t.get("description", "").lower()
                or keyword in t.get("id", "").lower()
            ]

        if not tools:
            ttk.Label(self.list_frame, text="(沒有符合的工具)", padding=20).pack()
            return

        for tool in tools:
            card = ToolCard(self.list_frame, tool, self)
            card.pack(side=tk.TOP, fill=tk.X, pady=4)
            self._cards[tool["id"]] = card

    # ---------- 動作 ----------

    def installed_version(self, tool_id: str) -> str | None:
        return self._installed.get(tool_id, {}).get("version")

    def do_install(self, tool: dict) -> None:
        tool_id = tool["id"]
        card = self._cards.get(tool_id)
        if not card:
            return
        self._cancel_flags[tool_id] = False
        card.set_busy(True)
        self.app.set_status(f"下載中:{tool['name']}…")

        def progress(d: int, t: int) -> None:
            self.after(0, card.set_progress, d, t)

        def cancel_check() -> bool:
            return self._cancel_flags.get(tool_id, False)

        def worker() -> None:
            try:
                installer.install(tool, on_progress=progress, cancel_flag=cancel_check)
                self.after(0, self._on_install_done, tool, None)
            except Exception as e:
                self.after(0, self._on_install_done, tool, e)

        threading.Thread(target=worker, daemon=True).start()

    def do_cancel(self, tool_id: str) -> None:
        self._cancel_flags[tool_id] = True

    def _on_install_done(self, tool: dict, err: Exception | None) -> None:
        tool_id = tool["id"]
        card = self._cards.get(tool_id)
        if card:
            card.set_busy(False)
        if err:
            if isinstance(err, InterruptedError):
                self.app.set_status("已取消")
            else:
                self.app.set_status("安裝失敗")
                messagebox.showerror("安裝失敗", str(err))
        else:
            self._installed = installer.load_installed()
            self.app.set_status(f"已安裝:{tool['name']} v{tool['version']}")
            self._render_list()

    def do_open(self, tool: dict) -> None:
        self.app.open_tool_tab(tool)

    def do_uninstall(self, tool: dict) -> None:
        if not messagebox.askyesno("移除", f"確定要移除「{tool['name']}」嗎?"):
            return
        tool_id = tool["id"]
        self.app.close_tool_tab(tool_id)
        try:
            installer.uninstall(tool_id)
            self._installed = installer.load_installed()
            self.app.set_status(f"已移除:{tool['name']}")
            self._render_list()
        except Exception as e:
            messagebox.showerror("移除失敗", str(e))


class ToolTabWrapper(ttk.Frame):
    """工具分頁的外層容器（含標題列與關閉按鈕）。"""

    def __init__(self, master: tk.Widget, tool: dict, app: LauncherApp) -> None:
        super().__init__(master)
        self.tool = tool
        self.app = app

        toolbar = ttk.Frame(self, padding=(8, 5))
        toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(toolbar, text=tool["name"], font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Label(toolbar, text=f"  v{tool['version']}", foreground="#666").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="關閉分頁", command=self._close).pack(side=tk.RIGHT)
        ttk.Separator(self, orient="horizontal").pack(fill=tk.X)

        try:
            content = launcher_run.load_frame(self, tool["id"])
            content.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            ttk.Label(
                self,
                text=f"載入失敗：\n\n{e}",
                foreground="red",
                padding=20,
                wraplength=700,
                justify=tk.LEFT,
            ).pack(fill=tk.BOTH, expand=True)

    def _close(self) -> None:
        self.app.close_tool_tab(self.tool["id"], self)


class ToolCard(ttk.Frame):
    """單一工具的卡片。"""

    def __init__(self, master: tk.Widget, tool: dict, catalog_tab: CatalogTab) -> None:
        super().__init__(master, padding=10, relief="groove", borderwidth=1)
        self.tool = tool
        self.catalog_tab = catalog_tab

        header = ttk.Frame(self)
        header.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(header, text=tool["name"], font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text=f"  v{tool['version']}", foreground="#666").pack(side=tk.LEFT)

        cat = tool.get("category")
        if cat:
            ttk.Label(header, text=f"  [{cat}]", foreground="#888").pack(side=tk.LEFT)

        self.status_label = ttk.Label(header, text="", foreground="#0a7")
        self.status_label.pack(side=tk.LEFT, padx=(12, 0))

        self.button_frame = ttk.Frame(header)
        self.button_frame.pack(side=tk.RIGHT)

        desc = tool.get("description", "")
        if desc:
            ttk.Label(self, text=desc, foreground="#444", wraplength=720, justify=tk.LEFT).pack(
                side=tk.TOP, fill=tk.X, pady=(4, 0)
            )

        size = tool.get("size_bytes")
        if size:
            ttk.Label(self, text=f"大小:{_fmt_size(size)}", foreground="#888").pack(
                side=tk.TOP, anchor=tk.W
            )

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(self, variable=self.progress_var, maximum=100)
        self.progress_text = ttk.Label(self, text="", foreground="#666")

        self._render_buttons()

    def _render_buttons(self) -> None:
        for w in self.button_frame.winfo_children():
            w.destroy()

        installed_ver = self.catalog_tab.installed_version(self.tool["id"])
        latest = self.tool["version"]

        if installed_ver is None:
            self.status_label.config(text="未安裝", foreground="#888")
            self._add_btn("安裝", lambda: self.catalog_tab.do_install(self.tool))
        elif installed_ver != latest:
            self.status_label.config(text=f"已安裝 v{installed_ver} → 有更新 v{latest}", foreground="#d80")
            self._add_btn("更新", lambda: self.catalog_tab.do_install(self.tool))
            self._add_btn("開啟", lambda: self.catalog_tab.do_open(self.tool))
            self._add_btn("移除", lambda: self.catalog_tab.do_uninstall(self.tool))
        else:
            self.status_label.config(text=f"已安裝 v{installed_ver}", foreground="#0a7")
            self._add_btn("開啟", lambda: self.catalog_tab.do_open(self.tool))
            self._add_btn("移除", lambda: self.catalog_tab.do_uninstall(self.tool))

    def _add_btn(self, text: str, cmd: Callable[[], None]) -> None:
        ttk.Button(self.button_frame, text=text, command=cmd, width=8).pack(side=tk.LEFT, padx=2)

    def set_busy(self, busy: bool) -> None:
        if busy:
            for w in self.button_frame.winfo_children():
                w.destroy()
            ttk.Button(
                self.button_frame, text="取消", width=8,
                command=lambda: self.catalog_tab.do_cancel(self.tool["id"]),
            ).pack(side=tk.LEFT, padx=2)
            self.progress.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))
            self.progress_text.pack(side=tk.TOP, anchor=tk.W)
            self.progress_var.set(0)
            self.progress_text.config(text="準備下載…")
        else:
            self.progress.pack_forget()
            self.progress_text.pack_forget()
            self._render_buttons()

    def set_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = downloaded / total * 100
            self.progress_var.set(pct)
            self.progress_text.config(
                text=f"{_fmt_size(downloaded)} / {_fmt_size(total)}  ({pct:.1f}%)"
            )
        else:
            self.progress_text.config(text=f"{_fmt_size(downloaded)} 已下載")


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> None:
    config.ensure_dirs()

    # 若內嵌 Python 尚未就緒，先跑安裝精靈
    if not python_env.is_ready():
        _run_python_setup()
        if not python_env.is_ready():
            return  # 使用者取消或失敗，不啟動主視窗

    app = LauncherApp()
    app.mainloop()


def _run_python_setup() -> None:
    """第一次執行時下載並設定內嵌 Python 的安裝視窗。"""
    win = tk.Tk()
    win.title("MyTools — 初始設定")
    win.geometry("460x220")
    win.resizable(False, False)
    try:
        win.iconbitmap(default="")
    except Exception:
        pass

    ttk.Label(win, text="首次執行需要下載 Python 執行環境（約 15 MB）",
              font=("Segoe UI", 11), padding=(20, 20, 20, 8)).pack()
    ttk.Label(win, text="下載完成後即可正常使用，之後不需重複下載。",
              foreground="#555", padding=(20, 0, 20, 16)).pack()

    msg_var = tk.StringVar(value="準備中…")
    ttk.Label(win, textvariable=msg_var, foreground="#1976d2",
              padding=(20, 0)).pack(anchor="w")

    pbar = ttk.Progressbar(win, maximum=100, length=420)
    pbar.pack(padx=20, pady=(6, 12))

    btn_frame = ttk.Frame(win)
    btn_frame.pack()
    start_btn = ttk.Button(btn_frame, text="開始下載", width=14)
    start_btn.pack(side=tk.LEFT, padx=6)
    cancel_btn = ttk.Button(btn_frame, text="取消", width=10,
                             command=win.destroy)
    cancel_btn.pack(side=tk.LEFT, padx=6)

    _cancelled = [False]

    def _on_progress(msg: str, pct: int) -> None:
        win.after(0, lambda: msg_var.set(msg))
        win.after(0, lambda: pbar.configure(value=pct))

    def _worker() -> None:
        try:
            python_env.setup(on_progress=_on_progress)
            win.after(0, win.destroy)
        except Exception as e:
            win.after(0, lambda: messagebox.showerror(
                "安裝失敗", f"Python 環境安裝失敗：\n{e}", parent=win))
            win.after(0, lambda: start_btn.configure(state="normal"))
            win.after(0, lambda: cancel_btn.configure(state="normal"))

    def _start() -> None:
        start_btn.configure(state="disabled")
        cancel_btn.configure(state="disabled")
        msg_var.set("連線中…")
        threading.Thread(target=_worker, daemon=True).start()

    start_btn.configure(command=_start)
    win.mainloop()


if __name__ == "__main__":
    main()
