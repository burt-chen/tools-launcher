# MyTools Launcher

依據 [工具啟動器_設計文件.md](工具啟動器_設計文件.md) 實作的初始版本。

## 結構

```
小工具管理/
├── run.py              # 開發時直接執行
├── build.bat           # PyInstaller 打包成 exe
├── tools.json          # 範例 catalog(本地測試用)
└── app/
    ├── config.py       # 路徑、catalog URL 設定
    ├── catalog.py      # 載入 tools.json(線上 + 離線快取)
    ├── installer.py    # 下載 / 驗 SHA256 / 安裝 / 移除
    ├── launcher_run.py # subprocess 啟動工具
    └── main.py         # Tkinter UI
```

## 開發執行

```powershell
python run.py
```

預設讀的 catalog URL 是設計文件中的範例 `https://USER.github.io/my-tools/tools.json`,
還沒有實際內容。本地測試時用環境變數指向本機檔案:

```powershell
# 注意 file:/// 用三斜線、檔案路徑用正斜線
$env:MYTOOLS_CATALOG_URL = "file:///D:/工具開發/小工具管理/tools.json"
python run.py
```

範例 `tools.json` 裡的 URL 指向不存在的 repo,要實際測「安裝」功能時請
改成你自己有效的 GitHub Releases asset URL。

## 已安裝工具的位置

`%LOCALAPPDATA%\MyTools\`
```
├── installed.json
├── catalog_cache.json
└── tools/
    └── {tool_id}/
        ├── *.exe
        └── _meta.json
```

要重置乾淨:刪掉整個 `%LOCALAPPDATA%\MyTools\` 資料夾即可。

## 打包

```powershell
pip install pyinstaller
.\build.bat
```

產出:`dist\MyToolsLauncher.exe`

## 已實作(MVP)

- [x] 從 catalog URL 載入工具清單,失敗時 fallback 到離線快取
- [x] 列出工具:名稱、版本、描述、分類、大小、狀態(未安裝 / 已安裝 / 有更新)
- [x] 安裝:背景下載 → 驗 SHA256(若有提供)→ 寫入 `installed.json`
- [x] 啟動:`subprocess.Popen` 跑起工具
- [x] 移除:刪除工具資料夾 + 從 `installed.json` 移除
- [x] 下載進度條 + 取消
- [x] 搜尋(過濾名稱/描述/id)

## 尚未實作(進階,參考設計文件 §5)

- [ ] 自動檢查更新(背景每 6 小時)
- [ ] 版本回滾、多版本並存
- [ ] 我的最愛分組
- [ ] Launcher 自更新
- [ ] 私有 repo 的 Token 設定 UI

## 切換正式 catalog URL

把 [app/config.py](app/config.py) 裡的 `CATALOG_URL` 預設值改成你的 GitHub Pages URL,
或在使用者環境設 `MYTOOLS_CATALOG_URL`。
