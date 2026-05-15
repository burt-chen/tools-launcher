"""開發測試啟動腳本 — 不需網路、不需真實工具，直接模擬已安裝狀態。

使用方式:
    python dev_run.py
"""
import json
import os
import shutil
from pathlib import Path

THIS_DIR = Path(__file__).parent

# 1. Catalog 指向本機 tools.json
os.environ["MYTOOLS_CATALOG_URL"] = THIS_DIR.joinpath("tools.json").as_uri()

# 2. 把 LOCALAPPDATA 改成本地測試資料夾，避免污染真實安裝目錄
TEST_DATA = THIS_DIR / "_test_data"
os.environ["LOCALAPPDATA"] = str(TEST_DATA)

# 3. 建立目錄結構
TOOLS_DIR = TEST_DATA / "MyTools" / "tools"
INSTALLED_JSON = TEST_DATA / "MyTools" / "installed.json"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)

# 4. 把 mock_tools/ 下的每個工具複製到測試安裝目錄
MOCK_ROOT = THIS_DIR / "mock_tools"
installed: dict = {}

if MOCK_ROOT.exists():
    for mock_dir in MOCK_ROOT.iterdir():
        if not mock_dir.is_dir():
            continue
        tool_id = mock_dir.name
        dest = TOOLS_DIR / tool_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(mock_dir, dest)

        # 從 tools.json 讀版本，找不到就填 "dev"
        version = "dev"
        try:
            catalog = json.loads((THIS_DIR / "tools.json").read_text(encoding="utf-8"))
            for t in catalog.get("tools", []):
                if t["id"] == tool_id:
                    version = t["version"]
                    break
        except Exception:
            pass

        installed[tool_id] = {
            "version": version,
            "path": str(dest),
            "installed_at": "2026-05-16T00:00:00",
        }

# 5. 寫入 installed.json
INSTALLED_JSON.write_text(
    json.dumps(installed, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"[dev] Catalog : {os.environ['MYTOOLS_CATALOG_URL']}")
print(f"[dev] Data dir: {TEST_DATA}")
print(f"[dev] 模擬已安裝工具: {list(installed.keys())}")
print()

from app.main import main  # noqa: E402

main()
