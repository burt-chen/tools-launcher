"""把各工具 Release 上的 tool_info.json 一鍵併進 tools.json（GUI）。

只用標準庫（tkinter + urllib）。放在 tools-launcher repo（小工具管理）根目錄，
讀寫同資料夾的 tools.json —— 跟 manage_versions.py / set_unlock.py 一致。

流程：
- 維護一份工具清單（id / GitHub 帳號 / repo），存 watch_tools.json。
- 「檢查全部」：對每個工具抓
  https://github.com/<owner>/<repo>/releases/latest/download/tool_info.json
  比對 catalog 現有版本，標出 新工具 / 可更新 / 已最新 / 抓取失敗。
- 勾選要套用的 → 併進 tools.json（聯集保留 versions，含 sha256/hidden）。
寫檔前自動備份 tools.json.bak。改完要自行 git push 才生效。

同事只要把 zip 和 tool_info.json 上傳到自己帳號的 Release，不必傳檔給你。
前提：同事的 repo / Release 必須 public。
"""
from __future__ import annotations

import json
import shutil
import tkinter as tk
import urllib.request
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

_DIR = Path(__file__).resolve().parent
TOOLS_JSON = _DIR / "tools.json"
WATCH_JSON = _DIR / "watch_tools.json"

TOP_FIELDS = ("name", "description", "version", "size_bytes", "url",
              "sha256", "category", "homepage")
LATEST_URL = "https://github.com/{owner}/{repo}/releases/latest/download/tool_info.json"


def _vkey(v) -> tuple:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def merge_into_catalog(catalog: dict, info: dict) -> tuple[dict, list[str]]:
    """把 info（單一工具物件）併進 catalog，回傳 (catalog, 摘要訊息行)。"""
    tid = info.get("id")
    if not tid or "versions" not in info or "version" not in info:
        raise ValueError("tool_info.json 格式不對：需要 id / version / versions")

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
                           + ("（仍標記作廢）" if ev.get("yanked") else ""))

    catalog["updated_at"] = date.today().isoformat()
    return catalog, log


def fetch_tool_info(owner: str, repo: str, timeout: int = 15) -> dict:
    url = LATEST_URL.format(owner=owner.strip(), repo=repo.strip())
    req = urllib.request.Request(url, headers={"User-Agent": "tools-launcher-sync"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class WatchDialog(tk.Toplevel):
    """新增 / 編輯一筆工具（id / GitHub 帳號 / repo），所有欄位一次顯示。"""

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


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("更新 tools.json（從各工具 Release）")
        root.geometry("860x600")
        root.minsize(760, 520)
        self.fetched: dict[str, dict] = {}   # id -> tool_info

        frm = ttk.Frame(root, padding=10)
        frm.pack(fill="both", expand=True)
        frm.rowconfigure(1, weight=1)
        frm.columnconfigure(0, weight=1)

        ttk.Label(frm, text=f"目標 catalog：{TOOLS_JSON}",
                  foreground="#888").grid(row=0, column=0, columnspan=2, sticky="w")

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
        self.tree.grid(row=1, column=0, sticky="nsew", pady=8)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns", pady=8)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("new", foreground="#1a6f1a")
        self.tree.tag_configure("upd", foreground="#b9770e")
        self.tree.tag_configure("err", foreground="#c0392b")
        self.tree.tag_configure("same", foreground="#888")

        bar1 = ttk.Frame(frm)
        bar1.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Button(bar1, text="新增工具", command=self._add).pack(side="left")
        ttk.Button(bar1, text="移除", command=self._remove).pack(side="left", padx=6)
        ttk.Button(bar1, text="檢查全部", command=self._check_all).pack(side="left", padx=6)
        # 主要動作緊鄰「檢查全部」,永遠看得到(不會被文字區擠出視窗)
        ttk.Button(bar1, text="更新tools",
                   command=self._apply_selected).pack(side="left", padx=6)
        ttk.Button(bar1, text="本機檔更新tools",
                   command=self._apply_file).pack(side="right")

        ttk.Label(frm, text="勾選(可多選)列後按「更新tools」;不選則更新全部「新/可更新」",
                  foreground="#888").grid(row=3, column=0, columnspan=2,
                                          sticky="w", pady=(6, 0))

        self.txt = tk.Text(frm, height=8, wrap="word")
        self.txt.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=8)
        frm.rowconfigure(4, weight=1)
        self.txt.tag_config("ok", foreground="#1a6f1a")
        self.txt.tag_config("muted", foreground="#888")
        self.txt.configure(state="disabled")

        if not TOOLS_JSON.exists():
            messagebox.showerror("找不到 tools.json",
                                 f"{TOOLS_JSON}\n請把此程式放在 tools-launcher repo 根目錄。")
        self._reload()

    # ---- watch list ----

    def _load_watch(self) -> list:
        if WATCH_JSON.exists():
            try:
                return json.loads(WATCH_JSON.read_text(encoding="utf-8")).get("tools", [])
            except Exception:
                return []
        return []

    def _save_watch(self, tools: list):
        WATCH_JSON.write_text(
            json.dumps({"tools": tools}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    def _catalog(self) -> dict:
        return json.loads(TOOLS_JSON.read_text(encoding="utf-8"))

    def _reload(self):
        self.watch = self._load_watch()
        cat = self._catalog()
        self.cat_ver = {t.get("id"): t.get("version", "") for t in cat.get("tools", [])}
        for i in self.tree.get_children():
            self.tree.delete(i)
        for w in self.watch:
            tid = w.get("id", "")
            self.tree.insert("", "end", iid=tid, values=(
                tid, f'{w.get("owner","")}/{w.get("repo","")}',
                self.cat_ver.get(tid, "（不在 catalog）"), "", "未檢查"))

    def _add(self):
        dlg = WatchDialog(self.root)
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

    # ---- check / apply ----

    def _set_status(self, tid, rel_ver, status, tag):
        v = list(self.tree.item(tid, "values"))
        v[3], v[4] = rel_ver, status
        self.tree.item(tid, values=v, tags=(tag,))

    def _check_all(self):
        # 每次都重讀磁碟上的 tools.json,反映外部手動編輯(刪除/改版本)
        try:
            cat = self._catalog()
        except Exception as e:
            messagebox.showerror(
                "tools.json 讀取失敗",
                f"{e}\n\n（tools.json 可能手動編輯後格式不正確,請先修好）")
            return
        self.cat_ver = {t.get("id"): t.get("version", "")
                        for t in cat.get("tools", [])}
        for w in self.watch:  # 同步更新「catalog 版本」欄
            tid = w.get("id", "")
            if self.tree.exists(tid):
                vv = list(self.tree.item(tid, "values"))
                vv[2] = self.cat_ver.get(tid, "（不在 catalog）")
                self.tree.item(tid, values=vv)

        self.fetched.clear()
        for w in self.watch:
            tid = w["id"]
            self._set_status(tid, "", "檢查中…", "")
            self.root.update_idletasks()
            try:
                info = fetch_tool_info(w["owner"], w["repo"])
            except Exception as e:
                self._set_status(tid, "", f"抓取失敗：{type(e).__name__}", "err")
                continue
            if info.get("id") and info["id"] != tid:
                self._set_status(tid, info.get("version", ""),
                                 f"id 不符（檔內為 {info['id']}）", "err")
                continue
            self.fetched[tid] = info
            rv = info.get("version", "")
            cv = self.cat_ver.get(tid)
            if cv is None:
                self._set_status(tid, rv, "新工具(可新增)", "new")
            elif _vkey(rv) > _vkey(cv):
                self._set_status(tid, rv, f"可更新（{cv}→{rv}）", "upd")
            elif _vkey(rv) == _vkey(cv):
                self._set_status(tid, rv, "已最新", "same")
            else:
                self._set_status(tid, rv, f"遠端較舊（{rv}<{cv}）", "err")

    def _targets(self) -> list[str]:
        sel = [i for i in self.tree.selection() if i in self.fetched]
        if sel:
            return sel
        # 沒選 → 全部「新工具 / 可更新」
        out = []
        for tid, info in self.fetched.items():
            cv = self.cat_ver.get(tid)
            if cv is None or _vkey(info.get("version", "")) > _vkey(cv):
                out.append(tid)
        return out

    def _apply_selected(self):
        targets = self._targets()
        if not targets:
            messagebox.showinfo("沒有可套用的",
                                "先「檢查全部」,再選列或讓它自動挑「新/可更新」。")
            return
        if not messagebox.askyesno(
                "確認", f"要把這 {len(targets)} 個工具套進 tools.json?\n"
                        + "、".join(targets)):
            return
        try:
            shutil.copy2(TOOLS_JSON, TOOLS_JSON.with_suffix(".json.bak"))
            cat = self._catalog()
            alllog = []
            for tid in targets:
                _, log = merge_into_catalog(cat, self.fetched[tid])
                alllog += log
            TOOLS_JSON.write_text(
                json.dumps(cat, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        except Exception as e:
            messagebox.showerror("寫入失敗", str(e))
            return
        self._show(["✓ 已寫入 tools.json（備份 tools.json.bak）", ""] + alllog
                   + ["", "記得 push 才生效：",
                      '  git add tools.json && git commit -m "更新工具" && git push'])
        self._reload()
        messagebox.showinfo("完成", "tools.json 已更新,記得 git commit & push。")

    def _apply_file(self):
        p = filedialog.askopenfilename(
            title="選擇 tool_info.json",
            filetypes=[("tool_info / JSON", "*.json"), ("所有檔案", "*.*")])
        if not p:
            return
        try:
            info = json.loads(Path(p).read_text(encoding="utf-8"))
            shutil.copy2(TOOLS_JSON, TOOLS_JSON.with_suffix(".json.bak"))
            cat = self._catalog()
            _, log = merge_into_catalog(cat, info)
            TOOLS_JSON.write_text(
                json.dumps(cat, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        except Exception as e:
            messagebox.showerror("失敗", str(e))
            return
        self._show(["✓ 已從本機檔寫入（備份 tools.json.bak）", ""] + log
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


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
