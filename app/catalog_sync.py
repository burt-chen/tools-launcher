"""Catalog 維護面板:從各工具 GitHub Release 抓 tool_info.json 併進 tools.json。

只有解鎖後才會顯示在側欄。本面板只負責「編輯本機端的 tools.json」,
git 操作交給使用者(本機 cmd / GitHub Desktop / VS Code 都行)。
"""
from __future__ import annotations

import json
import shutil
import tkinter as tk
import urllib.request
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import settings

TOP_FIELDS = ("name", "description", "version", "size_bytes",
              "installed_size_bytes", "url",
              "sha256", "category", "homepage",
              "manual_video")
LATEST_URL = "https://github.com/{owner}/{repo}/releases/latest/download/tool_info.json"


# ---------------------------------------------------------------- 邏輯

def _vkey(v) -> tuple:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def merge_into_catalog(catalog: dict, info: dict) -> tuple[dict, list[str]]:
    tid = info.get("id")
    if not tid or "versions" not in info or "version" not in info:
        raise ValueError("tool_info.json 格式不對:需要 id / version / versions")

    tools = catalog.setdefault("tools", [])
    cur = next((t for t in tools if t.get("id") == tid), None)
    log: list[str] = []

    if cur is None:
        tools.append(json.loads(json.dumps(info)))
        log.append(f"➕ 新增工具「{tid}」 版本 "
                   f"{', '.join(v['version'] for v in info['versions'])}")
    else:
        log.append(f"✎ 更新「{tid}」")
        for f in TOP_FIELDS:
            if f in info and cur.get(f) != info.get(f):
                log.append(f"   {f}: {cur.get(f)!r} → {info.get(f)!r}")
                cur[f] = info[f]
        if info.get("hidden"):
            if not cur.get("hidden"):
                log.append("   設為隱藏工具")
            cur["hidden"] = True
            if info.get("unlock_hash"):
                cur["unlock_hash"] = info["unlock_hash"]
        else:
            if cur.pop("hidden", None) is not None:
                log.append("   改為開放工具")
            cur.pop("unlock_hash", None)
        cur_vers = cur.setdefault("versions", [])
        by_ver = {v.get("version"): v for v in cur_vers}
        for nv in info["versions"]:
            ev = by_ver.get(nv["version"])
            if ev is None:
                cur_vers.append(dict(nv))
                log.append(f"   + 新版本 v{nv['version']}")
            elif ev.get("url") != nv.get("url") or \
                    ev.get("size_bytes") != nv.get("size_bytes"):
                ev["url"] = nv.get("url", ev.get("url"))
                ev["size_bytes"] = nv.get("size_bytes", ev.get("size_bytes"))
                log.append(f"   ~ 更新 v{nv['version']}"
                           + ("(仍標記作廢)" if ev.get("yanked") else ""))

    catalog["updated_at"] = date.today().isoformat()
    return catalog, log


def fetch_tool_info(owner: str, repo: str, timeout: int = 15) -> dict:
    url = LATEST_URL.format(owner=owner.strip(), repo=repo.strip())
    req = urllib.request.Request(url, headers={"User-Agent": "tools-launcher-sync"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- UI

class _WatchDialog(tk.Toplevel):
    FIELDS = [
        ("id", "工具 id", "與 tools.json 的 id 相同"),
        ("owner", "GitHub 帳號", "owner,例:burt-chen"),
        ("repo", "GitHub repo", "repo 名,例:tools-releases-pack"),
    ]

    def __init__(self, parent, existing: dict | None = None):
        super().__init__(parent)
        self.title("編輯工具" if existing else "新增工具")
        self.resizable(False, False)
        self.transient(parent)
        self.result: dict | None = None
        self.vars = {k: tk.StringVar(value=(existing or {}).get(k, ""))
                     for k, _, _ in self.FIELDS}

        frm = ttk.Frame(self, padding=14)
        frm.grid(sticky="nsew")
        frm.columnconfigure(1, weight=1)
        r = 0
        for key, label, hint in self.FIELDS:
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", padx=6, pady=4)
            e = ttk.Entry(frm, textvariable=self.vars[key], width=36)
            e.grid(row=r, column=1, sticky="ew", padx=6, pady=4)
            if key == "id" and existing:
                e.configure(state="disabled")
            ttk.Label(frm, text=hint, foreground="#888").grid(
                row=r + 1, column=1, sticky="w", padx=6)
            r += 2

        bar = ttk.Frame(frm)
        bar.grid(row=r, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bar, text="取消", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(bar, text="確定", command=self._ok).pack(side="right", padx=4)

        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        vals = {k: self.vars[k].get().strip() for k, _, _ in self.FIELDS}
        for key, label, _ in self.FIELDS:
            if not vals[key]:
                messagebox.showwarning("缺少資訊", f"「{label}」必填。", parent=self)
                return
        self.result = vals
        self.destroy()


class CatalogSyncPanel(ttk.Frame):
    """嵌在 launcher 內的 catalog 維護面板。"""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.fetched: dict[str, dict] = {}

        saved = self.app.settings.get("catalog_sync_path", "")
        self.tools_json: Path | None = Path(saved) if (
            saved and Path(saved).exists()) else None

        self._build_ui()
        self._reload()

    # ---------------- UI ----------------

    def _build_ui(self):
        # 標題列
        bar0 = ttk.Frame(self, padding=(12, 8, 12, 0))
        bar0.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(bar0, text="Catalog 維護",
                  font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        ttk.Separator(self, orient="horizontal").pack(
            side=tk.TOP, fill=tk.X, pady=(8, 0))

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        frm.rowconfigure(2, weight=1)
        frm.columnconfigure(0, weight=1)

        # 路徑列
        path_row = ttk.Frame(frm)
        path_row.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(path_row, text="tools.json:").pack(side="left")
        self.path_lbl = ttk.Label(path_row, text="", foreground="#555")
        self.path_lbl.pack(side="left", padx=(4, 8))
        ttk.Button(path_row, text="設定…",
                   command=self._pick_repo).pack(side="right")

        ttk.Separator(frm, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(6, 6))

        cols = ("id", "gh", "cat_ver", "rel_ver", "status")
        tt = {"id": "工具 id", "gh": "GitHub 帳號/repo",
              "cat_ver": "catalog 版本", "rel_ver": "Release 最新",
              "status": "狀態"}
        w = {"id": 150, "gh": 230, "cat_ver": 110, "rel_ver": 110, "status": 170}
        self.tree = ttk.Treeview(frm, columns=cols, show="headings",
                                 selectmode="extended", height=12)
        for c in cols:
            self.tree.heading(c, text=tt[c])
            self.tree.column(c, width=w[c], anchor="w")
        self.tree.grid(row=2, column=0, sticky="nsew", pady=4)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        sb.grid(row=2, column=1, sticky="ns", pady=4)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("new", foreground="#1a6f1a")
        self.tree.tag_configure("upd", foreground="#b9770e")
        self.tree.tag_configure("err", foreground="#c0392b")
        self.tree.tag_configure("same", foreground="#888")

        bar1 = ttk.Frame(frm)
        bar1.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(bar1, text="新增工具", command=self._add).pack(side="left")
        ttk.Button(bar1, text="移除", command=self._remove).pack(side="left", padx=6)
        ttk.Button(bar1, text="檢查全部", command=self._check_all).pack(side="left", padx=6)
        ttk.Button(bar1, text="檢查選取",
                   command=self._check_selected).pack(side="left", padx=6)
        ttk.Button(bar1, text="更新tools",
                   command=self._apply_selected).pack(side="left", padx=6)
        ttk.Button(bar1, text="本機檔更新tools",
                   command=self._apply_file).pack(side="right")
        ttk.Button(bar1, text="匯入清單",
                   command=self._import_watch).pack(side="right", padx=6)
        ttk.Button(bar1, text="匯出清單",
                   command=self._export_watch).pack(side="right")

        ttk.Label(frm, text="勾選列後按「更新tools」;不選則更新全部「新/可更新」。"
                            "改完 tools.json 後請自行 git commit & push。",
                  foreground="#888").grid(row=4, column=0, columnspan=2,
                                          sticky="w", pady=(6, 0))

        self.txt = tk.Text(frm, height=8, wrap="word")
        self.txt.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=8)
        frm.rowconfigure(5, weight=1)
        self.txt.tag_config("ok", foreground="#1a6f1a")
        self.txt.tag_config("muted", foreground="#888")
        self.txt.configure(state="disabled")

        self._refresh_path_label()

    # ---------------- 路徑 ----------------

    def _refresh_path_label(self):
        if self.tools_json is None:
            self.path_lbl.configure(
                text="(尚未設定 — 點右上「設定…」選 tools-launcher repo 資料夾)",
                foreground="#c0392b")
        else:
            self.path_lbl.configure(text=str(self.tools_json), foreground="#555")

    def _pick_repo(self):
        d = filedialog.askdirectory(
            title="選擇 tools-launcher repo 資料夾(裡面要有 tools.json)",
            parent=self,
        )
        if not d:
            return
        p = Path(d) / "tools.json"
        if not p.exists():
            messagebox.showerror(
                "找不到 tools.json",
                f"{p}\n看起來不是 tools-launcher repo,請選正確的資料夾。",
                parent=self,
            )
            return
        self.app.settings["catalog_sync_path"] = str(p)
        settings.save(self.app.settings)
        self.tools_json = p
        self._refresh_path_label()
        self._reload()

    def _watch_json(self) -> Path | None:
        if self.tools_json is None:
            return None
        return self.tools_json.parent / "watch_tools.json"

    # ---------------- watch list ----------------

    def _load_watch(self) -> list:
        wp = self._watch_json()
        if wp is None or not wp.exists():
            return []
        try:
            return json.loads(wp.read_text(encoding="utf-8")).get("tools", [])
        except Exception:
            return []

    def _save_watch(self, tools: list):
        wp = self._watch_json()
        if wp is None:
            self._need_path()
            return
        wp.write_text(
            json.dumps({"tools": tools}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    def _need_path(self):
        messagebox.showerror("尚未設定路徑",
                             "請先點右上「設定…」選 tools-launcher repo。",
                             parent=self)

    def _export_watch(self):
        tools = self._load_watch()
        if not tools:
            messagebox.showinfo("沒有資料", "工具清單是空的,沒東西可匯出。",
                                parent=self)
            return
        dest = filedialog.asksaveasfilename(
            title="匯出工具清單", defaultextension=".json",
            initialfile="watch_tools_backup.json",
            filetypes=[("JSON", "*.json")], parent=self)
        if not dest:
            return
        try:
            Path(dest).write_text(
                json.dumps({"tools": tools}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e), parent=self)
            return
        messagebox.showinfo("匯出完成",
                            f"已匯出 {len(tools)} 個工具到:\n{dest}",
                            parent=self)

    def _import_watch(self):
        if self.tools_json is None:
            self._need_path()
            return
        src = filedialog.askopenfilename(
            title="匯入工具清單",
            filetypes=[("JSON", "*.json"), ("所有檔案", "*.*")], parent=self)
        if not src:
            return
        try:
            incoming = json.loads(Path(src).read_text(encoding="utf-8"))
            items = incoming.get("tools") if isinstance(incoming, dict) else None
            if not isinstance(items, list):
                raise ValueError("格式不對:應為 {\"tools\": [...]}")
        except Exception as e:
            messagebox.showerror("匯入失敗", str(e), parent=self)
            return
        replace = messagebox.askyesno(
            "匯入方式",
            "要「整份覆蓋」目前的工具清單嗎?\n\n"
            "是 = 整份取代\n否 = 合併(同 id 覆蓋、新 id 新增,其餘保留)",
            parent=self)
        cur = self._load_watch()
        if replace:
            merged = [t for t in items if t.get("id")]
            added, updated = len(merged), 0
        else:
            by_id = {t.get("id"): i for i, t in enumerate(cur)}
            added = updated = 0
            for e in items:
                tid = e.get("id")
                if not tid:
                    continue
                if tid in by_id:
                    cur[by_id[tid]] = {**cur[by_id[tid]], **e}
                    updated += 1
                else:
                    cur.append(e)
                    by_id[tid] = len(cur) - 1
                    added += 1
            merged = cur
        self._save_watch(merged)
        self._reload()
        messagebox.showinfo(
            "匯入完成",
            f"新增 {added} 筆、更新 {updated} 筆,目前共 {len(merged)} 筆。",
            parent=self)

    # ---------------- catalog ----------------

    def _catalog(self) -> dict:
        return json.loads(self.tools_json.read_text(encoding="utf-8"))

    def _reload(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        if self.tools_json is None:
            return
        try:
            cat = self._catalog()
        except Exception as e:
            messagebox.showerror("tools.json 讀取失敗", str(e), parent=self)
            return
        self.watch = self._load_watch()
        self.cat_ver = {t.get("id"): t.get("version", "")
                        for t in cat.get("tools", [])}
        for w in self.watch:
            tid = w.get("id", "")
            self.tree.insert("", "end", iid=tid, values=(
                tid, f'{w.get("owner","")}/{w.get("repo","")}',
                self.cat_ver.get(tid, "(不在 catalog)"), "", "未檢查"))

    def _add(self):
        if self.tools_json is None:
            self._need_path()
            return
        dlg = _WatchDialog(self)
        if not dlg.result:
            return
        v = dlg.result
        self.watch = [w for w in self._load_watch() if w.get("id") != v["id"]]
        self.watch.append({"id": v["id"], "owner": v["owner"], "repo": v["repo"]})
        self._save_watch(self.watch)
        self._reload()

    def _remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        ids = set(sel)
        self._save_watch([w for w in self._load_watch() if w.get("id") not in ids])
        self._reload()

    # ---------------- check / apply ----------------

    def _set_status(self, tid, rel_ver, status, tag):
        v = list(self.tree.item(tid, "values"))
        v[3], v[4] = rel_ver, status
        self.tree.item(tid, values=v, tags=(tag,))

    def _check_all(self):
        self._check_tools([w["id"] for w in self.watch])

    def _check_selected(self):
        sel = list(self.tree.selection())
        if not sel:
            messagebox.showinfo("沒有選擇",
                                "請先在表格中選一行以上,再按「檢查選取」。",
                                parent=self)
            return
        self._check_tools(sel)

    def _check_tools(self, tids: list[str]):
        """檢查指定的工具(reload catalog 版本 → 抓 release → 更新狀態)。

        檢查選取與檢查全部共用此邏輯。fetched 只移除被重檢的項目,
        其他先前檢查結果保留(讓「更新tools」仍能套用)。
        """
        if self.tools_json is None:
            self._need_path()
            return
        if not tids:
            return
        try:
            cat = self._catalog()
        except Exception as e:
            messagebox.showerror(
                "tools.json 讀取失敗",
                f"{e}\n\n(tools.json 可能手動編輯後格式不正確,請先修好)",
                parent=self)
            return
        self.cat_ver = {t.get("id"): t.get("version", "")
                        for t in cat.get("tools", [])}
        # 同步「catalog 版本」欄(只動被檢的列)
        for tid in tids:
            if self.tree.exists(tid):
                vv = list(self.tree.item(tid, "values"))
                vv[2] = self.cat_ver.get(tid, "(不在 catalog)")
                self.tree.item(tid, values=vv)

        watch_by_id = {w["id"]: w for w in self.watch}
        for tid in tids:
            self.fetched.pop(tid, None)
            w = watch_by_id.get(tid)
            if w is None:
                continue
            self._set_status(tid, "", "檢查中…", "")
            self.update_idletasks()
            try:
                info = fetch_tool_info(w["owner"], w["repo"])
            except Exception as e:
                self._set_status(tid, "", f"抓取失敗:{type(e).__name__}", "err")
                continue
            if info.get("id") and info["id"] != tid:
                self._set_status(tid, info.get("version", ""),
                                 f"id 不符(檔內為 {info['id']})", "err")
                continue
            self.fetched[tid] = info
            rv = info.get("version", "")
            cv = self.cat_ver.get(tid)
            if cv is None:
                self._set_status(tid, rv, "新工具(可新增)", "new")
            elif _vkey(rv) > _vkey(cv):
                self._set_status(tid, rv, f"可更新({cv}→{rv})", "upd")
            elif _vkey(rv) == _vkey(cv):
                self._set_status(tid, rv, "已最新", "same")
            else:
                self._set_status(tid, rv, f"遠端較舊({rv}<{cv})", "err")

    def _targets(self) -> list[str]:
        sel = [i for i in self.tree.selection() if i in self.fetched]
        if sel:
            return sel
        out = []
        for tid, info in self.fetched.items():
            cv = self.cat_ver.get(tid)
            if cv is None or _vkey(info.get("version", "")) > _vkey(cv):
                out.append(tid)
        return out

    def _apply_selected(self):
        if self.tools_json is None:
            self._need_path()
            return
        targets = self._targets()
        if not targets:
            messagebox.showinfo("沒有可套用的",
                                "先「檢查全部」,再選列或讓它自動挑「新/可更新」。",
                                parent=self)
            return
        if not messagebox.askyesno(
                "確認",
                f"要把這 {len(targets)} 個工具套進 tools.json?\n"
                + "、".join(targets), parent=self):
            return
        try:
            shutil.copy2(self.tools_json, self.tools_json.with_suffix(".json.bak"))
            cat = self._catalog()
            alllog = []
            for tid in targets:
                _, log = merge_into_catalog(cat, self.fetched[tid])
                alllog += log
            self.tools_json.write_text(
                json.dumps(cat, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        except Exception as e:
            messagebox.showerror("寫入失敗", str(e), parent=self)
            return
        self._show(["✓ 已寫入 tools.json(備份 tools.json.bak)", ""] + alllog
                   + ["", "記得 push 才生效:",
                      '  git add tools.json && git commit -m "更新工具" && git push'])
        self._reload()
        messagebox.showinfo("完成",
                            "tools.json 已更新,記得 git commit & push。",
                            parent=self)

    def _apply_file(self):
        if self.tools_json is None:
            self._need_path()
            return
        p = filedialog.askopenfilename(
            title="選擇 tool_info.json",
            filetypes=[("tool_info / JSON", "*.json"), ("所有檔案", "*.*")],
            parent=self)
        if not p:
            return
        try:
            info = json.loads(Path(p).read_text(encoding="utf-8"))
            shutil.copy2(self.tools_json, self.tools_json.with_suffix(".json.bak"))
            cat = self._catalog()
            _, log = merge_into_catalog(cat, info)
            self.tools_json.write_text(
                json.dumps(cat, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        except Exception as e:
            messagebox.showerror("失敗", str(e), parent=self)
            return
        self._show(["✓ 已從本機檔寫入(備份 tools.json.bak)", ""] + log
                   + ["", "記得 git commit & push。"])
        self._reload()

    def _show(self, lines):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        for s in lines:
            self.txt.insert("end", s + "\n",
                            "ok" if s.startswith(("✓", "➕", "✎")) else
                            ("muted" if s.startswith(" ") or not s else ""))
        self.txt.configure(state="disabled")
