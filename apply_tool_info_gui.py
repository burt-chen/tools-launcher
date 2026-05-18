"""把打包工具產生的 tool_info.json 套用進 tools.json（GUI）。

只用標準庫（tkinter）。放在 tools-launcher repo（小工具管理）根目錄，
讀寫同資料夾的 tools.json —— 跟 manage_versions.py / set_unlock.py 一致。

合併規則（聯集保留）：
- 該工具已存在：更新 top-level（name/description/version/size_bytes/url/
  sha256/category/homepage，及 hidden/unlock_hash 依 tool_info 為準）；
  versions 做聯集 —— 既有版本與其 yanked 標記保留，同版本更新 url/size，
  tool_info 的新版本沒有的才追加。
- 該工具不存在：整筆新增。
寫檔前先備份 tools.json → tools.json.bak。改完要自行 git push 才生效。
"""
from __future__ import annotations

import json
import shutil
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

TOOLS_JSON = Path(__file__).resolve().parent / "tools.json"

# tool_info 內代表「最新版」的 top-level 欄位
TOP_FIELDS = ("name", "description", "version", "size_bytes", "url",
              "sha256", "category", "homepage")


def merge_into_catalog(catalog: dict, info: dict) -> tuple[dict, list[str]]:
    """把 info（單一工具物件）併進 catalog，回傳 (catalog, 摘要訊息行)。"""
    tid = info.get("id")
    if not tid or "versions" not in info or "version" not in info:
        raise ValueError("tool_info.json 格式不對：需要 id / version / versions")

    tools = catalog.setdefault("tools", [])
    cur = next((t for t in tools if t.get("id") == tid), None)
    log: list[str] = []

    if cur is None:
        tools.append(json.loads(json.dumps(info)))  # 深拷貝整筆新增
        log.append(f"➕ 新增工具「{tid}」")
        log.append(f"   版本：{', '.join(v['version'] for v in info['versions'])}")
    else:
        log.append(f"✎ 更新既有工具「{tid}」")
        for f in TOP_FIELDS:
            if f in info and cur.get(f) != info.get(f):
                log.append(f"   {f}: {cur.get(f)!r} → {info.get(f)!r}")
                cur[f] = info[f]

        # hidden / unlock_hash 依 tool_info 為準（開放工具會移除這兩鍵）
        if info.get("hidden"):
            if not cur.get("hidden"):
                log.append("   設為隱藏工具（hidden=true）")
            cur["hidden"] = True
            if info.get("unlock_hash"):
                cur["unlock_hash"] = info["unlock_hash"]
        else:
            if cur.pop("hidden", None) is not None:
                log.append("   改為開放工具（移除 hidden）")
            cur.pop("unlock_hash", None)

        # versions 聯集：保留既有（含 yanked），同版本更新，新版本追加
        cur_vers = cur.setdefault("versions", [])
        by_ver = {v.get("version"): v for v in cur_vers}
        for nv in info["versions"]:
            ev = by_ver.get(nv["version"])
            if ev is None:
                cur_vers.append(dict(nv))
                log.append(f"   + 新版本 v{nv['version']}")
            else:
                if ev.get("url") != nv.get("url") or \
                        ev.get("size_bytes") != nv.get("size_bytes"):
                    ev["url"] = nv.get("url", ev.get("url"))
                    ev["size_bytes"] = nv.get("size_bytes", ev.get("size_bytes"))
                    log.append(f"   ~ 更新 v{nv['version']}（url/size）"
                               + ("（仍標記作廢）" if ev.get("yanked") else ""))

    catalog["updated_at"] = date.today().isoformat()
    return catalog, log


class App:
    def __init__(self, root: tk.Tk):
        root.title("套用 tool_info → tools.json")
        root.geometry("680x520")
        root.minsize(600, 460)
        self.info: dict | None = None
        self.src = tk.StringVar()

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="tool_info.json").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(frm, textvariable=self.src, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(frm, text="選擇…", command=self._pick).grid(row=0, column=2, padx=6, pady=6)

        ttk.Label(frm, text=f"目標：{TOOLS_JSON}", foreground="#888").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=6)

        self.txt = tk.Text(frm, height=18, wrap="word")
        self.txt.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=6, pady=8)
        self.txt.tag_config("warn", foreground="#c0392b")
        self.txt.tag_config("ok", foreground="#1a6f1a")
        self.txt.tag_config("muted", foreground="#888")
        self.txt.configure(state="disabled")
        frm.rowconfigure(2, weight=1)

        bar = ttk.Frame(frm)
        bar.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6)
        self.btn = ttk.Button(bar, text="套用並寫入 tools.json",
                              command=self._apply, state="disabled")
        self.btn.pack(side="right")
        ttk.Label(bar, text="寫入前會自動備份 tools.json.bak",
                  foreground="#888").pack(side="left")

        if not TOOLS_JSON.exists():
            self._set([(f"⚠ 找不到 {TOOLS_JSON}", "warn"),
                       ("請把此程式放在 tools-launcher repo（小工具管理）根目錄。", "muted")])

    def _set(self, lines):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        for s, tag in lines:
            self.txt.insert("end", s + "\n", tag)
        self.txt.configure(state="disabled")

    def _pick(self):
        p = filedialog.askopenfilename(
            title="選擇 tool_info.json",
            filetypes=[("tool_info / JSON", "*.json"), ("所有檔案", "*.*")])
        if not p:
            return
        try:
            info = json.loads(Path(p).read_text(encoding="utf-8"))
            catalog = json.loads(TOOLS_JSON.read_text(encoding="utf-8"))
            preview = json.loads(json.dumps(catalog))  # 在副本上預演
            _, log = merge_into_catalog(preview, info)
        except Exception as e:
            self.info = None
            self.btn.configure(state="disabled")
            self._set([("讀取 / 預覽失敗：", "warn"), (str(e), "warn")])
            return
        self.src.set(p)
        self.info = info
        self.btn.configure(state="normal")
        lines = [("預覽（尚未寫入,按下方按鈕才會改檔）", "muted"), ("", "muted")]
        lines += [(x, "ok" if x.startswith(("➕", "✎")) else "") for x in log]
        self._set(lines)

    def _apply(self):
        if not self.info:
            return
        if not messagebox.askyesno("確認", "確定把這份 tool_info 套用進 tools.json?"):
            return
        try:
            shutil.copy2(TOOLS_JSON, TOOLS_JSON.with_suffix(".json.bak"))
            catalog = json.loads(TOOLS_JSON.read_text(encoding="utf-8"))
            catalog, log = merge_into_catalog(catalog, self.info)
            TOOLS_JSON.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        except Exception as e:
            messagebox.showerror("寫入失敗", str(e))
            return
        self._set(
            [("✓ 已寫入 tools.json（備份在 tools.json.bak）", "ok"), ("", "muted")]
            + [(x, "") for x in log]
            + [("", "muted"),
               ("記得 push 才會對使用者生效：", "muted"),
               ('  git add tools.json && git commit -m "更新工具" && git push',
                "muted")])
        self.btn.configure(state="disabled")
        messagebox.showinfo(
            "完成", "tools.json 已更新。\n記得 git commit & push tools-launcher repo。")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
