"""路徑與常數設定。"""
import os
import sys
from pathlib import Path

APP_NAME = "MyTools"
APP_VERSION = "1.1.5"  # Launcher 自身版本,與 tools.json 的 launcher.version 比對

# Catalog 來源 URL。優先讀環境變數,方便測試切換到本地檔。
# 例:set MYTOOLS_CATALOG_URL=file:///D:/工具開發/小工具管理/tools.json
CATALOG_URL = os.environ.get(
    "MYTOOLS_CATALOG_URL",
    "https://raw.githubusercontent.com/burt-chen/tools-launcher/main/tools.json",
)

# 本地資料夾:%LOCALAPPDATA%\MyTools\
_LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
ROOT = Path(_LOCALAPPDATA) / APP_NAME

TOOLS_DIR = ROOT / "tools"
INSTALLED_JSON = ROOT / "installed.json"
CATALOG_CACHE = ROOT / "catalog_cache.json"
SETTINGS_JSON = ROOT / "settings.json"

HTTP_TIMEOUT = 10
DOWNLOAD_CHUNK = 64 * 1024

# 內嵌 Python（由 python_env 管理）
def _launcher_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent

LAUNCHER_DIR = _launcher_dir()
PYTHON_EXE = LAUNCHER_DIR / "python" / "python.exe"


def ensure_dirs() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
