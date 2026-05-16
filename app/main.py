"""Tkinter Launcher UI — 左右分割版面。

左側「作業清單」:工具清單 + 已安裝工具 + 設定。
右側:顯示當前選取項目的內容。
"""
from __future__ import annotations

import threading
import traceback
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from . import catalog, config, installer, launcher_run, python_env, settings

SIDEBAR_W = 210
SIDEBAR_BG = "#eef1f5"
SIDEBAR_LINE = "#d4d9e0"
NAV_HOVER = "#e0e6ee"
NAV_SEL = "#cfe2ff"
NAV_FONT = ("Segoe UI", 10)


class NavItem(tk.Frame):
    """左側作業清單的一個可點項目。"""

    def __init__(self, parent: tk.Widget, key: str, text: str,
                 on_click: Callable[[str], None]) -> None:
        super().__init__(parent, bg=SIDEBAR_BG, cursor="hand2")
        self.key = key
        self._on_click = on_click
        self._selected = False
        self.lbl = tk.Label(
            self, text=text, bg=SIDEBAR_BG, anchor="w",
            padx=18, pady=9, font=NAV_FONT,
        )
        self.lbl.pack(fill=tk.X)
        for w in (self, self.lbl):
            w.bind("<Button-1>", lambda _e: self._on_click(self.key))
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)

    def _enter(self, _e: tk.Event) -> None:
        if not self._selected:
            self._paint(NAV_HOVER)

    def _leave(self, _e: tk.Event) -> None:
        if not self._selected:
            self._paint(SIDEBAR_BG)

    def _paint(self, bg: str) -> None:
        self.configure(bg=bg)
        self.lbl.configure(bg=bg)

    def set_selected(self, sel: bool) -> None:
        self._selected = sel
        self._paint(NAV_SEL if sel else SIDEBAR_BG)


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{config.APP_NAME} — 工具啟動器")
        self.geometry("1020x660")
        self.minsize(780, 500)

        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        self.settings = settings.load()
        self._catalog: dict = {"tools": []}
        self._installed: dict = installer.load_installed()
        self._panels: dict[str, tk.Widget] = {}      # key -> 內容面板
        self._nav_items: dict[str, NavItem] = {}
        self._current_key: str | None = None

        self._build_layout()
        self._rebuild_nav()
        self._show("catalog")

    # ---------- 版面 ----------

    def _build_layout(self) -> None:
        self.status_var = tk.StringVar(value="就緒")
        statusbar = ttk.Frame(self, padding=(10, 3), relief="sunken")
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(statusbar, textvariable=self.status_var).pack(side=tk.LEFT)

        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 左側
        self.sidebar = tk.Frame(body, bg=SIDEBAR_BG, width=SIDEBAR_W)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        tk.Label(
            self.sidebar, text="作業清單", bg=SIDEBAR_BG, anchor="w",
            padx=14, pady=11, font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.TOP, fill=tk.X)
        tk.Frame(self.sidebar, height=1, bg=SIDEBAR_LINE).pack(side=tk.TOP, fill=tk.X)
        self.nav_frame = tk.Frame(self.sidebar, bg=SIDEBAR_BG)
        self.nav_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 右側
        self.content = ttk.Frame(body)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    # ---------- 左側清單 ----------

    def _rebuild_nav(self) -> None:
        for w in self.nav_frame.winfo_children():
            w.destroy()
        self._nav_items.clear()

        # 設定 — 釘在最下方
        self._add_nav("settings", "設定", side=tk.BOTTOM)
        tk.Frame(self.nav_frame, height=1, bg=SIDEBAR_LINE).pack(
            side=tk.BOTTOM, fill=tk.X, padx=8, pady=4)

        # 工具清單 — 釘在最上方
        self._add_nav("catalog", "工具清單", side=tk.TOP)
        tk.Frame(self.nav_frame, height=1, bg=SIDEBAR_LINE).pack(
            side=tk.TOP, fill=tk.X, padx=8, pady=4)

        # 已安裝工具
        if self._installed:
            for tool_id, info in self._installed.items():
                name = info.get("name") or self._catalog_name(tool_id) or tool_id
                self._add_nav(tool_id, name, side=tk.TOP)
        else:
            tk.Label(
                self.nav_frame, text="(尚無已安裝工具)", bg=SIDEBAR_BG,
                fg="#9aa0a8", anchor="w", padx=18, pady=6, font=("Segoe UI", 9),
            ).pack(side=tk.TOP, fill=tk.X)

        self._update_nav_selection()

    def _add_nav(self, key: str, text: str, side: str) -> None:
        item = NavItem(self.nav_frame, key, text, self._show)
        item.pack(side=side, fill=tk.X)
        self._nav_items[key] = item

    def _update_nav_selection(self) -> None:
        for key, item in self._nav_items.items():
            item.set_selected(key == self._current_key)

    # ---------- 右側內容切換 ----------

    def _show(self, key: str) -> None:
        if key == self._current_key:
            return

        old_key = self._current_key
        old_panel = self._panels.get(old_key) if old_key else None
        if old_panel is not None:
            old_panel.pack_forget()
            # 工具面板且設定為不保留 → 切走時銷毀
            is_tool = old_key not in ("catalog", "settings")
            if is_tool and not self.settings.get("keep_tools_loaded", True):
                old_panel.destroy()
                self._panels.pop(old_key, None)

        panel = self._get_panel(key)
        if panel is None:
            # 載入失敗 → 留在原畫面
            if old_panel is not None and self._panels.get(old_key) is old_panel:
                old_panel.pack(fill=tk.BOTH, expand=True)
            return
        panel.pack(fill=tk.BOTH, expand=True)
        self._current_key = key
        self._update_nav_selection()

    def _get_panel(self, key: str) -> tk.Widget | None:
        if key in self._panels:
            return self._panels[key]
        if key == "catalog":
            panel: tk.Widget = CatalogPanel(self.content, self)
        elif key == "settings":
            panel = SettingsPanel(self.content, self)
        else:
            panel = self._build_tool_panel(key)
        self._panels[key] = panel
        return panel

    def _build_tool_panel(self, tool_id: str) -> tk.Widget:
        info = self._installed.get(tool_id, {})
        tool = self._tool_by_id(tool_id) or {}
        name = info.get("name") or tool.get("name") or tool_id
        version = info.get("version") or tool.get("version") or ""

        wrapper = ttk.Frame(self.content)
        bar = ttk.Frame(wrapper, padding=(12, 7))
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(bar, text=name, font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        if version:
            ttk.Label(bar, text=f"  v{version}", foreground="#888").pack(side=tk.LEFT)
        ttk.Separator(wrapper, orient="horizontal").pack(fill=tk.X)

        try:
            inner = launcher_run.load_frame(wrapper, tool_id)
            inner.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            ttk.Label(
                wrapper,
                text=f"載入失敗：\n\n{e}\n\n{traceback.format_exc()}",
                foreground="red", padding=20, wraplength=760, justify=tk.LEFT,
            ).pack(fill=tk.BOTH, expand=True)
        return wrapper

    # ---------- catalog / installed 狀態 ----------

    def set_catalog(self, data: dict) -> None:
        """由 CatalogPanel 在抓到清單後回呼。"""
        self._catalog = data or {"tools": []}
        self._installed = installer.load_installed()
        self._rebuild_nav()

    def on_installed_changed(self) -> None:
        """工具安裝 / 移除後重建左側清單。"""
        self._installed = installer.load_installed()
        # 清掉已移除工具的快取面板
        for tid in list(self._panels.keys()):
            if tid in ("catalog", "settings"):
                continue
            if tid not in self._installed:
                panel = self._panels.pop(tid)
                if self._current_key == tid:
                    panel.pack_forget()
                    self._current_key = None
                panel.destroy()
        self._rebuild_nav()
        if self._current_key is None:
            self._show("catalog")

    def _tool_by_id(self, tool_id: str) -> dict | None:
        for t in self._catalog.get("tools", []):
            if t.get("id") == tool_id:
                return t
        return None

    def _catalog_name(self, tool_id: str) -> str | None:
        t = self._tool_by_id(tool_id)
        return t.get("name") if t else None


class CatalogPanel(ttk.Frame):
    """右側「工具清單」內容面板。"""

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
        toolbar = ttk.Frame(self, padding=(12, 10))
        toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(toolbar, text="刷新", command=self.refresh_catalog).pack(side=tk.LEFT)
        ttk.Label(toolbar, text="搜尋:").pack(side=tk.LEFT, padx=(12, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_list())
        ttk.Entry(toolbar, textvariable=self.search_var, width=24).pack(side=tk.LEFT)
        self.source_label = ttk.Label(toolbar, text="")
        self.source_label.pack(side=tk.RIGHT)

        container = ttk.Frame(self)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
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
        self.app.set_catalog(self._catalog)

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
            self.app.on_installed_changed()

    def do_uninstall(self, tool: dict) -> None:
        if not messagebox.askyesno("移除", f"確定要移除「{tool['name']}」嗎?"):
            return
        try:
            installer.uninstall(tool["id"])
            self._installed = installer.load_installed()
            self.app.set_status(f"已移除:{tool['name']}")
            self._render_list()
            self.app.on_installed_changed()
        except Exception as e:
            messagebox.showerror("移除失敗", str(e))


class ToolCard(ttk.Frame):
    """單一工具的卡片。"""

    def __init__(self, master: tk.Widget, tool: dict, panel: CatalogPanel) -> None:
        super().__init__(master, padding=10, relief="groove", borderwidth=1)
        self.tool = tool
        self.panel = panel

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
                side=tk.TOP, fill=tk.X, pady=(4, 0))

        size = tool.get("size_bytes")
        if size:
            ttk.Label(self, text=f"大小:{_fmt_size(size)}", foreground="#888").pack(
                side=tk.TOP, anchor=tk.W)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(self, variable=self.progress_var, maximum=100)
        self.progress_text = ttk.Label(self, text="", foreground="#666")

        self._render_buttons()

    def _render_buttons(self) -> None:
        for w in self.button_frame.winfo_children():
            w.destroy()

        installed_ver = self.panel.installed_version(self.tool["id"])
        latest = self.tool["version"]

        if installed_ver is None:
            self.status_label.config(text="未安裝", foreground="#888")
            self._add_btn("安裝", lambda: self.panel.do_install(self.tool))
        elif installed_ver != latest:
            self.status_label.config(
                text=f"已安裝 v{installed_ver} → 有更新 v{latest}", foreground="#d80")
            self._add_btn("更新", lambda: self.panel.do_install(self.tool))
            self._add_btn("移除", lambda: self.panel.do_uninstall(self.tool))
        else:
            self.status_label.config(
                text=f"已安裝 v{installed_ver}(左側作業清單開啟)", foreground="#0a7")
            self._add_btn("移除", lambda: self.panel.do_uninstall(self.tool))

    def _add_btn(self, text: str, cmd: Callable[[], None]) -> None:
        ttk.Button(self.button_frame, text=text, command=cmd, width=8).pack(side=tk.LEFT, padx=2)

    def set_busy(self, busy: bool) -> None:
        if busy:
            for w in self.button_frame.winfo_children():
                w.destroy()
            ttk.Button(
                self.button_frame, text="取消", width=8,
                command=lambda: self.panel.do_cancel(self.tool["id"]),
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
                text=f"{_fmt_size(downloaded)} / {_fmt_size(total)}  ({pct:.1f}%)")
        else:
            self.progress_text.config(text=f"{_fmt_size(downloaded)} 已下載")


class SettingsPanel(ttk.Frame):
    """右側「設定」內容面板。"""

    def __init__(self, master: tk.Widget, app: LauncherApp) -> None:
        super().__init__(master, padding=20)
        self.app = app

        ttk.Label(self, text="設定", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", pady=(0, 14))

        general = ttk.LabelFrame(self, text="一般", padding=14)
        general.pack(fill=tk.X, anchor="w")

        self.keep_var = tk.BooleanVar(
            value=self.app.settings.get("keep_tools_loaded", True))
        ttk.Checkbutton(
            general,
            text="切換工具時保留工具畫面與狀態",
            variable=self.keep_var,
            command=self._on_keep_changed,
        ).pack(anchor="w")
        ttk.Label(
            general,
            text="開啟:切到別的工具再切回來,已選的檔案與設定都還在(較耗記憶體)。\n"
                 "關閉:每次切回工具都重新載入,回到初始狀態。",
            foreground="#666", justify=tk.LEFT,
        ).pack(anchor="w", padx=(22, 0), pady=(2, 0))

    def _on_keep_changed(self) -> None:
        self.app.settings["keep_tools_loaded"] = self.keep_var.get()
        settings.save(self.app.settings)
        state = "保留" if self.keep_var.get() else "每次重新載入"
        self.app.set_status(f"設定已儲存:切換工具時{state}")


def _fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> None:
    config.ensure_dirs()

    # 若內嵌 Python 尚未就緒,先跑安裝精靈
    if not python_env.is_ready():
        _run_python_setup()
        if not python_env.is_ready():
            return  # 使用者取消或失敗,不啟動主視窗

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
