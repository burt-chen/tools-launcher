"""Launcher 進入點。"""

# ── 啟動硬化(self-heal)──────────────────────────────────────
# onefile 自我更新後,relaunch 的新行程可能沿用舊行程的 _MEIxxxx 暫存夾;
# 舊行程一結束該夾就被刪掉,之後任何「延遲 import」會找不到 base_library.zip
# (典型錯誤:urlopen error ... _MEIxxxx\base_library.zip)。
# 對策:在啟動最早期(此時舊行程多半還沒結束、_MEI 還在)就把之後
# 「安裝 / 切換版本 / 自我更新」會用到的標準庫全部先載入記憶體;
# 之後就算 _MEI 被刪,也不會再去 base_library.zip 找模組。
def _preload_stdlib() -> None:
    import importlib
    mods = [
        "ssl", "socket", "select", "http.client",
        "urllib.request", "urllib.error", "urllib.parse",
        "email.parser", "email.message", "email.feedparser",
        "email.utils", "email.header",
        "json", "zipfile", "zlib", "bz2", "lzma",
        "hashlib", "hmac", "shutil", "subprocess", "tempfile",
        "encodings.idna", "ctypes", "ctypes.util",
        "datetime", "queue", "threading",
    ]
    for name in mods:
        try:
            importlib.import_module(name)
        except Exception:
            pass


_preload_stdlib()
# ──────────────────────────────────────────────────────────────

from app.main import main

if __name__ == "__main__":
    main()
