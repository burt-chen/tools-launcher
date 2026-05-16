"""Tkinter Launcher UI — 左右分割版面,含我的最愛與自訂分組。

左側「作業清單」:工具清單 + 已安裝工具(依最愛/群組分區) + 設定。
右側:顯示當前選取項目的內容。
"""
from __future__ import annotations

import hashlib
import threading
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Callable

from . import catalog, config, installer, launcher_run, python_env, settings

SIDEBAR_W = 222
SIDEBAR_BG = "#eef1f5"
SIDEBAR_LINE = "#d4d9e0"
NAV_HOVER = "#e0e6ee"
NAV_SEL = "#cfe2ff"
NAV_FONT = ("Segoe UI", 10)


class NavItem(tk.Frame):
    """左側作業清單的一個可點項目。"""

    def __init__(self, parent: tk.Widget, key: str, text: str,
                 on_click: Callable[[str], None], indent: int = 18,
                 on_menu: Callable[[tk.Event, str], None] | None = None) -> None:
        super().__init__(parent, bg=SIDEBAR_BG, cursor="hand2")
        self.key = key
        self._on_click = on_click
        self._selected = False
        self.lbl = tk.Label(
            self, text=text, bg=SIDEBAR_BG, anchor="w",
            padx=indent, pady=7, font=NAV_FONT,
        )
        self.lbl.pack(fill=tk.X)
        for w in (self, self.lbl):
            w.bind("<Button-1>", lambda _e: self._on_click(self.key))
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            if on_menu is not None:
                w.bind("<Button-3>", lambda e: on_menu(e, self.key))

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


class GroupSection(tk.Frame):
    """左側清單的一個可折疊分區(我的最愛 / 自訂群組 / 未分組)。"""

    def __init__(self, parent: tk.Widget, title: str, kind: str,
                 app: "LauncherApp", collapsed: bool) -> None:
        super().__init__(parent, bg=SIDEBAR_BG)
        self.title = title
        self.kind = kind
        self.app = app
        self._collapsed = collapsed

        self.header = tk.Frame(self, bg=SIDEBAR_BG, cursor="hand2")
        self.header.pack(fill=tk.X)
        self.tri = tk.Label(
            self.header, text=("▸" if collapsed else "▾"),
            bg=SIDEBAR_BG, font=("Segoe UI", 8), width=2,
        )
        self.tri.pack(side=tk.LEFT, padx=(8, 0))
        self.title_lbl = tk.Label(
            self.header, text=title, bg=SIDEBAR_BG, anchor="w", pady=5,
            font=("Segoe UI", 9, "bold"), fg="#5a6472",
        )
        self.title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.body = tk.Frame(self, bg=SIDEBAR_BG)
        if not collapsed:
            self.body.pack(fill=tk.X)

        for w in (self.header, self.tri, self.title_lbl):
            w.bind("<Button-1>", self._toggle)
            if kind == "group":
                w.bind("<Button-3>", self._menu)

    def _toggle(self, _e: tk.Event | None = None) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.body.pack_forget()
            self.tri.configure(text="▸")
            self.app.collapsed.add(self.title)
        else:
            self.body.pack(fill=tk.X)
            self.tri.configure(text="▾")
            self.app.collapsed.discard(self.title)

    def _menu(self, event: tk.Event) -> None:
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="重新命名群組",
                      command=lambda: self.app.rename_group_dialog(self.title))
        m.add_command(label="刪除群組",
                      command=lambda: self.app.delete_group_dialog(self.title))
        m.tk_popup(event.x_root, event.y_root)


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{config.APP_NAME} — 工具啟動器")
        self.geometry("1020x660")
        self.minsize(800, 500)

        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        self.settings = settings.load()
        self.collapsed: set[str] = set()        # 折疊中的分區標題
        self._catalog: dict = {"tools": []}
        self._installed: dict = installer.load_installed()
        self._panels: dict[str, tk.Widget] = {}
        self._nav_items: list[NavItem] = []
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

        self.content = ttk.Frame(body)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    # ---------- 左側清單 ----------

    def _rebuild_nav(self) -> None:
        for w in self.nav_frame.winfo_children():
            w.destroy()
        self._nav_items = []

        # 設定 — 釘最下方
        item = NavItem(self.nav_frame, "settings", "設定", self._show)
        item.pack(side=tk.BOTTOM, fill=tk.X)
        self._nav_items.append(item)
        tk.Frame(self.nav_frame, height=1, bg=SIDEBAR_LINE).pack(
            side=tk.BOTTOM, fill=tk.X, padx=8, pady=4)

        # 工具清單 — 釘最上方
        item = NavItem(self.nav_frame, "catalog", "工具清單", self._show)
        item.pack(side=tk.TOP, fill=tk.X)
        self._nav_items.append(item)
        tk.Frame(self.nav_frame, height=1, bg=SIDEBAR_LINE).pack(
            side=tk.TOP, fill=tk.X, padx=8, pady=4)

        installed_ids = [tid for tid in self._installed
                         if self._installed_visible(tid)]
        if not installed_ids:
            tk.Label(
                self.nav_frame, text="(尚無已安裝工具)", bg=SIDEBAR_BG,
                fg="#9aa0a8", anchor="w", padx=18, pady=6, font=("Segoe UI", 9),
            ).pack(side=tk.TOP, fill=tk.X)
            self._update_nav_selection()
            return

        for title, kind, ids in settings.grouped_sections(installed_ids, self.settings):
            sec = GroupSection(self.nav_frame, title, kind, self, title in self.collapsed)
            sec.pack(side=tk.TOP, fill=tk.X)
            for tid in ids:
                nav = NavItem(
                    sec.body, tid, self._tool_name(tid), self._show,
                    indent=34, on_menu=self.show_tool_menu,
                )
                nav.pack(fill=tk.X)
                self._nav_items.append(nav)
            if not ids:
                tk.Label(
                    sec.body, text="(空)", bg=SIDEBAR_BG, fg="#9aa0a8",
                    anchor="w", padx=34, pady=3, font=("Segoe UI", 9),
                ).pack(fill=tk.X)

        self._update_nav_selection()

    def _update_nav_selection(self) -> None:
        for item in self._nav_items:
            item.set_selected(item.key == self._current_key)

    # ---------- 右側內容切換 ----------

    def _show(self, key: str) -> None:
        if key == self._current_key:
            return
        old_key = self._current_key
        old_panel = self._panels.get(old_key) if old_key else None
        if old_panel is not None:
            old_panel.pack_forget()
            is_tool = old_key not in ("catalog", "settings")
            if is_tool and not self.settings.get("keep_tools_loaded", True):
                old_panel.destroy()
                self._panels.pop(old_key, None)

        panel = self._get_panel(key)
        if panel is None:
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
        name = self._tool_name(tool_id)
        version = info.get("version") or tool.get("version") or ""

        wrapper = ttk.Frame(self.content)
        bar = ttk.Frame(wrapper, padding=(12, 7))
        bar.pack(side=tk.TOP, fill=tk.X)
        title_lbl = ttk.Label(bar, text=name, font=("Segoe UI", 12, "bold"))
        title_lbl.pack(side=tk.LEFT)
        wrapper._tool_title = title_lbl  # type: ignore[attr-defined]
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
        self._catalog = data or {"tools": []}
        self._installed = installer.load_installed()
        self._rebuild_nav()

    def on_installed_changed(self) -> None:
        self._installed = installer.load_installed()
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

    def _tool_name(self, tool_id: str) -> str:
        info = self._installed.get(tool_id, {})
        cat = self._tool_by_id(tool_id) or {}
        default = info.get("name") or cat.get("name") or tool_id
        return settings.tool_display_name(self.settings, tool_id, default)

    # ---------- 隱藏工具 / 解鎖 ----------

    def _is_visible(self, tool: dict) -> bool:
        """catalog 工具是否可見:隱藏且未解鎖 → 不可見。"""
        if tool.get("hidden") and tool.get("id") not in self.settings.get("unlocked", []):
            return False
        return True

    def _installed_visible(self, tool_id: str) -> bool:
        """已安裝工具是否該顯示在左側清單。"""
        t = self._tool_by_id(tool_id)
        if t is None:
            return True  # 不在 catalog,無法判斷,仍顯示
        return self._is_visible(t)

    def try_unlock(self, code: str) -> list[str]:
        """以解鎖碼比對隱藏工具的 unlock_hash;回傳這次新解鎖的工具名稱清單。"""
        code = (code or "").strip()
        if not code:
            return []
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest().lower()
        unlocked = self.settings.setdefault("unlocked", [])
        newly: list[str] = []
        for t in self._catalog.get("tools", []):
            if not t.get("hidden"):
                continue
            if str(t.get("unlock_hash", "")).lower() != digest:
                continue
            if t["id"] not in unlocked:
                unlocked.append(t["id"])
                newly.append(t.get("name", t["id"]))
        if newly:
            settings.save(self.settings)
            self._refresh_views()
        return newly

    # ---------- 最愛 / 群組 操作 ----------

    def _refresh_views(self) -> None:
        """設定變動後重建左側清單、重繪 catalog 與設定頁。"""
        self._rebuild_nav()
        cat = self._panels.get("catalog")
        if isinstance(cat, CatalogPanel):
            cat.render()
        sp = self._panels.get("settings")
        if isinstance(sp, SettingsPanel):
            sp.refresh_groups()

    def show_tool_menu(self, event: tk.Event, tool_id: str) -> None:
        """工具項目 / 卡片的右鍵選單。"""
        menu = tk.Menu(self, tearoff=False)
        if settings.is_favorite(self.settings, tool_id):
            menu.add_command(label="從我的最愛移除",
                             command=lambda: self._toggle_fav(tool_id))
        else:
            menu.add_command(label="加入我的最愛",
                             command=lambda: self._toggle_fav(tool_id))
        menu.add_separator()

        grp_menu = tk.Menu(menu, tearoff=False)
        cur = settings.group_of(self.settings, tool_id)
        grp_menu.add_command(
            label=("✓ 未分組" if cur is None else "未分組"),
            command=lambda: self._move_group(tool_id, None))
        for g in self.settings.get("groups", []):
            nm = g["name"]
            grp_menu.add_command(
                label=(f"✓ {nm}" if cur == nm else nm),
                command=lambda n=nm: self._move_group(tool_id, n))
        grp_menu.add_separator()
        grp_menu.add_command(label="新增群組…",
                             command=lambda: self._new_group_for(tool_id))
        menu.add_cascade(label="移到群組", menu=grp_menu)

        menu.add_separator()
        menu.add_command(label="重新命名…",
                         command=lambda: self._rename_tool(tool_id))
        if settings.has_custom_name(self.settings, tool_id):
            menu.add_command(label="還原預設名稱",
                             command=lambda: self._reset_tool_name(tool_id))

        menu.tk_popup(event.x_root, event.y_root)

    def _rename_tool(self, tool_id: str) -> None:
        new = simpledialog.askstring(
            "重新命名工具", "工具顯示名稱(清空則還原預設):",
            initialvalue=self._tool_name(tool_id), parent=self)
        if new is None:
            return
        settings.set_tool_name(self.settings, tool_id, new.strip())
        settings.save(self.settings)
        self._apply_tool_title(tool_id)
        self._refresh_views()

    def _reset_tool_name(self, tool_id: str) -> None:
        settings.set_tool_name(self.settings, tool_id, "")
        settings.save(self.settings)
        self._apply_tool_title(tool_id)
        self._refresh_views()

    def _apply_tool_title(self, tool_id: str) -> None:
        """若該工具的分頁已開啟,更新標題列文字。"""
        panel = self._panels.get(tool_id)
        title = getattr(panel, "_tool_title", None)
        if title is not None:
            try:
                title.configure(text=self._tool_name(tool_id))
            except tk.TclError:
                pass

    def _toggle_fav(self, tool_id: str) -> None:
        settings.toggle_favorite(self.settings, tool_id)
        settings.save(self.settings)
        self._refresh_views()

    def _move_group(self, tool_id: str, group_name: str | None) -> None:
        settings.assign_group(self.settings, tool_id, group_name)
        settings.save(self.settings)
        self._refresh_views()

    def _new_group_for(self, tool_id: str) -> None:
        name = simpledialog.askstring("新增群組", "群組名稱:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if not settings.add_group(self.settings, name):
            messagebox.showinfo("提示", f"群組「{name}」已存在,將直接移入。")
        settings.assign_group(self.settings, tool_id, name)
        settings.save(self.settings)
        self._refresh_views()

    def add_group_dialog(self) -> None:
        name = simpledialog.askstring("新增群組", "群組名稱:", parent=self)
        if not name or not name.strip():
            return
        if settings.add_group(self.settings, name.strip()):
            settings.save(self.settings)
            self._refresh_views()
        else:
            messagebox.showinfo("提示", "群組名稱已存在")

    def rename_group_dialog(self, old: str) -> None:
        new = simpledialog.askstring("重新命名群組", "新名稱:",
                                     initialvalue=old, parent=self)
        if not new or not new.strip():
            return
        new = new.strip()
        if new == old:
            return
        if any(g["name"] == new for g in self.settings.get("groups", [])):
            messagebox.showinfo("提示", "群組名稱重複")
            return
        settings.rename_group(self.settings, old, new)
        if old in self.collapsed:
            self.collapsed.discard(old)
            self.collapsed.add(new)
        settings.save(self.settings)
        self._refresh_views()

    def delete_group_dialog(self, name: str) -> None:
        if not messagebox.askyesno(
                "刪除群組", f"確定刪除群組「{name}」?\n(裡面的工具會變成未分組)"):
            return
        settings.remove_group(self.settings, name)
        self.collapsed.discard(name)
        settings.save(self.settings)
        self._refresh_views()


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
        self.search_var.trace_add("write", lambda *_: self.render())
        ttk.Entry(toolbar, textvariable=self.search_var, width=24).pack(side=tk.LEFT)
        self.source_label = ttk.Label(toolbar, text="")
        self.source_label.pack(side=tk.RIGHT)

        # 依安裝狀態篩選
        filter_row = ttk.Frame(self, padding=(12, 0, 12, 8))
        filter_row.pack(side=tk.TOP, fill=tk.X)
        self.filter_var = tk.StringVar(value="all")
        self._filter_btns: dict[str, tuple[ttk.Radiobutton, str]] = {}
        for key, label in (("all", "全部"), ("installed", "已安裝"),
                           ("not_installed", "未安裝"), ("updatable", "可更新")):
            rb = ttk.Radiobutton(
                filter_row, text=label, value=key, variable=self.filter_var,
                style="Toolbutton", command=self.render,
            )
            rb.pack(side=tk.LEFT, padx=(0, 4))
            self._filter_btns[key] = (rb, label)

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
        self.render()
        self.app.set_catalog(self._catalog)

    # ---------- 渲染 ----------

    def render(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._cards.clear()

        all_tools = [t for t in self._catalog.get("tools", [])
                     if self.app._is_visible(t)]

        # 計算各狀態數量,更新篩選鈕文字
        counts = {"all": 0, "installed": 0, "not_installed": 0, "updatable": 0}
        for t in all_tools:
            iv = self.installed_version(t["id"])
            counts["all"] += 1
            if iv is None:
                counts["not_installed"] += 1
            else:
                counts["installed"] += 1
                if iv != t.get("version"):
                    counts["updatable"] += 1
        for key, (rb, label) in self._filter_btns.items():
            rb.configure(text=f"{label} ({counts[key]})")

        flt = self.filter_var.get()

        def keep(t: dict) -> bool:
            iv = self.installed_version(t["id"])
            if flt == "installed":
                return iv is not None
            if flt == "not_installed":
                return iv is None
            if flt == "updatable":
                return iv is not None and iv != t.get("version")
            return True

        tools = [t for t in all_tools if keep(t)]
        keyword = self.search_var.get().strip().lower()
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
            self._make_card(tool)

    def _make_card(self, tool: dict) -> None:
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
            self.render()
            self.app.on_installed_changed()

    def do_uninstall(self, tool: dict) -> None:
        if not messagebox.askyesno("移除", f"確定要移除「{tool['name']}」嗎?"):
            return
        try:
            installer.uninstall(tool["id"])
            self._installed = installer.load_installed()
            self.app.set_status(f"已移除:{tool['name']}")
            self.render()
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
        if tool.get("hidden"):
            ttk.Label(header, text="  [需解鎖工具]",
                      foreground="#d80").pack(side=tk.LEFT)
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
            general, text="切換工具時保留工具畫面與狀態",
            variable=self.keep_var, command=self._on_keep_changed,
        ).pack(anchor="w")
        ttk.Label(
            general,
            text="開啟:切到別的工具再切回來,已選的檔案與設定都還在(較耗記憶體)。\n"
                 "關閉:每次切回工具都重新載入,回到初始狀態。",
            foreground="#666", justify=tk.LEFT,
        ).pack(anchor="w", padx=(22, 0), pady=(2, 0))

        groups_box = ttk.LabelFrame(self, text="工具分組", padding=14)
        groups_box.pack(fill=tk.X, anchor="w", pady=(14, 0))
        ttk.Label(
            groups_box,
            text="在左側作業清單的工具項目上按右鍵,可加入我的最愛或移到群組。",
            foreground="#666",
        ).pack(anchor="w", pady=(0, 8))
        self.groups_inner = ttk.Frame(groups_box)
        self.groups_inner.pack(fill=tk.X)
        ttk.Button(groups_box, text="新增群組",
                   command=self.app.add_group_dialog).pack(anchor="w", pady=(8, 0))
        self.refresh_groups()

        # 解鎖隱藏工具
        unlock_box = ttk.LabelFrame(self, text="解鎖工具", padding=14)
        unlock_box.pack(fill=tk.X, anchor="w", pady=(14, 0))
        ttk.Label(
            unlock_box,
            text="部分工具預設隱藏,輸入解鎖碼後才會顯示在工具清單。",
            foreground="#666",
        ).pack(anchor="w", pady=(0, 8))
        row = ttk.Frame(unlock_box)
        row.pack(anchor="w")
        self.unlock_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.unlock_var, width=28, show="*")
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", lambda _e: self._do_unlock())
        ttk.Button(row, text="解鎖", command=self._do_unlock).pack(side=tk.LEFT, padx=(6, 0))
        self.unlock_status = ttk.Label(unlock_box, text="")
        self.unlock_status.pack(anchor="w", pady=(6, 0))

    def _do_unlock(self) -> None:
        newly = self.app.try_unlock(self.unlock_var.get())
        if newly:
            self.unlock_status.configure(
                text=f"已解鎖:{', '.join(newly)}", foreground="#0a7")
            self.unlock_var.set("")
        else:
            self.unlock_status.configure(
                text="解鎖碼不正確,或沒有對應的隱藏工具", foreground="#c0392b")

    def _on_keep_changed(self) -> None:
        self.app.settings["keep_tools_loaded"] = self.keep_var.get()
        settings.save(self.app.settings)
        state = "保留" if self.keep_var.get() else "每次重新載入"
        self.app.set_status(f"設定已儲存:切換工具時{state}")

    def refresh_groups(self) -> None:
        for w in self.groups_inner.winfo_children():
            w.destroy()
        groups = self.app.settings.get("groups", [])
        if not groups:
            ttk.Label(self.groups_inner, text="(尚無群組)", foreground="#9aa0a8").pack(anchor="w")
            return
        for g in groups:
            row = ttk.Frame(self.groups_inner)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=g["name"], width=18, anchor="w").pack(side=tk.LEFT)
            ttk.Label(row, text=f"{len(g.get('tools', []))} 個工具",
                      foreground="#888").pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(row, text="刪除", width=6,
                       command=lambda nm=g["name"]: self.app.delete_group_dialog(nm)
                       ).pack(side=tk.RIGHT, padx=2)
            ttk.Button(row, text="重新命名", width=9,
                       command=lambda nm=g["name"]: self.app.rename_group_dialog(nm)
                       ).pack(side=tk.RIGHT, padx=2)


def _fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> None:
    config.ensure_dirs()

    if not python_env.is_ready():
        _run_python_setup()
        if not python_env.is_ready():
            return

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
