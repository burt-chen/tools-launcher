# MyTools Launcher

依據 [工具啟動器_設計文件.md](工具啟動器_設計文件.md) 實作,並在開發過程中演進為
「工具以 Python 原始碼發佈、由 launcher 動態載入並嵌入分頁」的架構。

## 結構

```
小工具管理/
├── run.py              # 開發時直接執行
├── build.bat           # PyInstaller 打包成 exe
├── tools.json          # catalog(工具清單)
└── app/
    ├── config.py       # 路徑、catalog URL、設定檔路徑
    ├── catalog.py      # 載入 tools.json(線上 + 離線快取)
    ├── installer.py    # 下載 / 驗 SHA256 / 安裝 / 移除 / installed.json
    ├── launcher_run.py # 動態載入工具的 UI frame(嵌入右側內容區)
    ├── python_env.py   # 內嵌 Python 的下載與設定
    ├── settings.py     # 使用者設定的讀寫
    └── main.py         # Tkinter UI(左右分割版面)
```

## 版面

- **左側「作業清單」**:`工具清單`(固定最上)→ 已安裝工具 → `設定`(固定最下)
- **右側內容區**:顯示當前選取項目 —— 工具清單卡片、工具操作畫面、或設定頁

## 開發執行

```powershell
python run.py
```

本地測試時可用環境變數把 catalog 指向本機檔案:

```powershell
# 注意 file:/// 用三斜線、檔案路徑用正斜線
$env:MYTOOLS_CATALOG_URL = "file:///F:/程式集/AI製作工具/小工具管理/tools.json"
python run.py
```

正式環境的 catalog URL 預設值在 [app/config.py](app/config.py) 的 `CATALOG_URL`。

## 已安裝工具的位置

`%LOCALAPPDATA%\MyTools\`
```
├── installed.json       # 已安裝工具:名稱 / 版本 / 路徑
├── catalog_cache.json   # catalog 離線快取
├── settings.json        # 使用者設定
└── tools/
    └── {tool_id}/
        ├── main_frame.py    # 工具入口,提供 create_frame(parent)
        ├── app/             # 工具自己的程式碼
        └── (pip 安裝的依賴套件)
```

要重置乾淨:刪掉整個 `%LOCALAPPDATA%\MyTools\` 資料夾即可。

## 內嵌 Python

launcher 旁的 `python/` 目錄是可攜版 Python,首次執行時自動下載(約 15 MB),
用來為工具 `pip install` 依賴套件。使用者不需自行安裝 Python。

## 打包

```powershell
pip install pyinstaller
.\build.bat
```

產出:`dist\MyToolsLauncher.exe`

> 注意:launcher 是動態載入工具的 host。PyInstaller 只會打包 launcher 自己用到的
> 標準庫,工具(如 openpyxl)需要的 `xml` 等模組必須在 `build.bat` 用
> `--collect-submodules` / `--hidden-import` 明確納入。

## 已實作

- [x] 從 catalog URL 載入工具清單,失敗時 fallback 到離線快取
- [x] 列出工具:名稱、版本、描述、分類、大小、狀態(未安裝 / 已安裝 / 有更新)
- [x] 安裝:背景下載 → 驗 SHA256(若有提供)→ pip 安裝依賴 → 寫入 `installed.json`
- [x] 啟動:動態載入工具 UI、嵌入 launcher 右側內容區
- [x] 移除:刪除工具資料夾 + 從 `installed.json` 移除
- [x] 下載進度條 + 取消
- [x] 搜尋(過濾名稱 / 描述 / id)
- [x] 左右分割版面:左側作業清單、右側內容區
- [x] 內嵌 Python(首次執行自動下載,工具不需使用者自行裝 Python)
- [x] 設定頁(切換工具時是否保留畫面與狀態)

## 尚未實作(進階,參考設計文件 §5)

- [ ] 自動檢查更新(背景每 6 小時)
- [ ] 版本回滾、多版本並存
- [ ] 我的最愛 + 自訂分組
- [ ] Launcher 自更新
- [ ] 私有 repo 的 Token 設定 UI
