# Launcher 操作影片按鈕修改說明

目標：在 Launcher 的工具卡片上新增「操作影片」按鈕。  
如果該工具在 `tools.json` 裡有 `manual_video.url`，就顯示按鈕；按下後在 Launcher 右側內容區開啟內嵌影片觀看頁，不開啟外部網頁或瀏覽器。

## 一、整體資料流程

```text
tools-releases-pack
→ 產生 tool_info.json 的 manual_video 欄位

Launcher 內建 Catalog 維護面板
→ 從 tool_info.json 把 manual_video 合併進 tools.json

Launcher
→ 讀取 tools.json
→ 工具卡片看到 manual_video.url
→ 顯示「操作影片」按鈕
→ 使用者點擊後切換右側內容區
→ Launcher 內嵌影片觀看頁播放 manual_video.url
```

## 二、tools.json 需要的格式

工具物件內需要有 `manual_video`：

```json
{
  "id": "PDFToolkit",
  "name": "PDF工具集",
  "version": "1.1.0",
  "manual_video": {
    "url": "https://github.com/burt-chen/PDFToolkit/releases/download/v1.1.0/PDFToolkit_manual-v1.1.0.mp4",
    "version": "1.1.0",
    "filename": "PDFToolkit_manual-v1.1.0.mp4",
    "size_bytes": 12345678,
    "sha256": "",
    "duration_seconds": 130,
    "updated_at": "2026-06-11",
    "type": "silent"
  }
}
```

Launcher 主要只需要讀：

```python
tool.get("manual_video", {}).get("url")
```

有網址就顯示按鈕，沒有網址就不顯示。

## 三、修改 Launcher 內建 Catalog 維護面板

檔案：

```text
D:\工具開發\小工具管理\app\catalog_sync.py
```

目前 `TOP_FIELDS` 只同步工具基本欄位：

```python
TOP_FIELDS = ("name", "description", "version", "size_bytes",
              "installed_size_bytes", "url",
              "sha256", "category", "homepage")
```

需要加入 `manual_video`：

```python
TOP_FIELDS = ("name", "description", "version", "size_bytes",
              "installed_size_bytes", "url",
              "sha256", "category", "homepage",
              "manual_video")
```

目的：讓各工具 Release 的 `tool_info.json` 裡的 `manual_video` 可以被同步進 `tools.json`。

注意：舊的獨立工具 `apply_tool_info_gui.py` 已經整合進 Launcher。現在要改的是 `app/catalog_sync.py` 裡的 `TOP_FIELDS`，不是再改獨立 GUI 檔。

## 四、修改 Launcher 工具卡片

檔案：

```text
D:\工具開發\小工具管理\app\main.py
```

工具卡片 class：

```python
class ToolCard(ttk.Frame):
```

按鈕產生位置：

```python
def _render_buttons(self) -> None:
```

目前工具卡片會依狀態顯示：

```text
未安裝：安裝
可更新：更新 / 切換版本 / 移除
已安裝：切換版本 / 移除
```

要新增：

```text
只要 manual_video.url 存在，就顯示「操作影片」按鈕
```

建議按鈕順序：

```text
操作影片 | 安裝
操作影片 | 更新 | 切換版本 | 移除
操作影片 | 切換版本 | 移除
```

## 五、採用方案

採用「方案 A：Launcher 內嵌影片觀看頁」。

```text
按「操作影片」
→ 不開外部瀏覽器
→ Launcher 右側內容區切換成影片觀看頁
→ 內嵌播放器載入 manual_video.url
```

Tkinter 本身沒有內建 mp4 播放元件，因此需要新增一個內嵌影片播放能力。建議使用 WebView 型播放器，例如 `pywebview` 搭配系統 WebView2。

播放頁不直接開 GitHub 網頁，而是載入一段本機產生的 HTML，HTML 內用 `<video>` 播放 mp4：

```html
<video controls autoplay style="width:100%;height:100%;">
  <source src="https://github.com/.../PDFToolkit_manual-v1.1.0.mp4" type="video/mp4">
</video>
```

這樣使用者看到的是 Launcher 內部的影片觀看頁，不會跳到外部瀏覽器。

## 六、main.py 實作方式

### 1. 新增影片頁入口方法

在 Launcher 主程式中新增一個方法，例如：

```python
def show_manual_video(self, tool: dict) -> None:
    mv = tool.get("manual_video") or {}
    url = str(mv.get("url") or "").strip()
    if not url:
        messagebox.showinfo("操作影片", "這個工具目前沒有操作影片。")
        return

    self._show_view("manual_video", lambda parent: ManualVideoView(parent, tool))
```

實際要接到既有 Launcher 的頁面切換方法。重點是：不要呼叫 `webbrowser.open()`，而是把右側內容區換成 `ManualVideoView`。

### 2. 新增 ManualVideoView

新增一個影片觀看頁 class，例如：

```python
class ManualVideoView(ttk.Frame):
    def __init__(self, master: tk.Widget, tool: dict) -> None:
        super().__init__(master)
        self.tool = tool
        self.manual_video = tool.get("manual_video") or {}

        ttk.Label(
            self,
            text=f"{tool.get('name', tool.get('id', ''))} 操作影片",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 8))

        # 這裡嵌入 WebView 或影片播放容器。
        # WebView 內載入本機 HTML，HTML 的 <video> source 指向 manual_video.url。
```

### 3. 影片 HTML

WebView 載入的 HTML 可以由程式動態產生：

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {
      margin: 0;
      width: 100%;
      height: 100%;
      background: #111;
    }
    video {
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #111;
    }
  </style>
</head>
<body>
  <video controls autoplay>
    <source src="{manual_video_url}" type="video/mp4">
  </video>
</body>
</html>
```

### 4. 在 ToolCard 加入取得影片 URL 的方法

放在 `ToolCard` class 裡：

```python
def _manual_video_url(self) -> str:
    mv = self.tool.get("manual_video") or {}
    return str(mv.get("url") or "").strip()
```

### 5. 在 ToolCard 加入開啟內嵌影片頁的方法

放在 `ToolCard` class 裡：

```python
def _open_manual_video(self) -> None:
    if not self._manual_video_url():
        messagebox.showinfo("操作影片", "這個工具目前沒有操作影片。")
        return
    self.panel.app.show_manual_video(self.tool)
```

### 6. 在 _render_buttons() 加入按鈕

在 `_render_buttons()` 清掉舊按鈕後，狀態判斷前加入：

```python
if self._manual_video_url():
    self._add_btn("操作影片", self._open_manual_video)
```

範例位置：

```python
def _render_buttons(self) -> None:
    for w in self.button_frame.winfo_children():
        w.destroy()

    if self._manual_video_url():
        self._add_btn("操作影片", self._open_manual_video)

    installed_ver = self.panel.installed_version(self.tool["id"])
    latest = self.tool["version"]
```

這樣不管工具是未安裝、可更新、已安裝，只要有影片 URL 就會顯示。

## 七、需要新增的相依與打包注意

因為 Tkinter 不能原生播放 mp4，需要新增內嵌播放元件。建議方向：

```text
pywebview + Windows WebView2
```

需要確認：

```text
requirements.txt 是否加入 pywebview
PyInstaller 打包時是否能帶入 pywebview 相關模組
使用者 Windows 環境是否有 WebView2 Runtime
```

若不想新增相依，則無法在 Tkinter 內直接播放 mp4，只能改成外部播放器或圖文手冊頁。

## 八、驗證方式

### 1. 確認 tools.json 有 manual_video

確認目標工具有：

```json
"manual_video": {
  "url": "https://..."
}
```

### 2. 啟動 Launcher

啟動後進入「工具清單」。

### 3. 檢查工具卡片

如果工具有 `manual_video.url`，應該看到：

```text
操作影片
```

### 4. 點擊按鈕

按下「操作影片」後，Launcher 右側內容區應切換成影片觀看頁。

預期結果：

```text
不開啟外部瀏覽器
不跳出 GitHub 網頁
在 Launcher 內顯示影片播放器
可以播放 / 暫停 / 調整進度
```

### 5. 沒有 manual_video 的工具

沒有 `manual_video.url` 的工具不應顯示「操作影片」按鈕。

## 九、注意事項

- Launcher 需要負責顯示內嵌影片觀看頁。
- 影片可以直接串流 `manual_video.url`，不一定要先下載。
- 影片檔應該跟工具 zip 一起上傳到 GitHub Release。
- `manual_video.url` 必須是使用者可存取的網址。
- 這個方案不開外部網頁，但內部播放仍需要 WebView 或其他 mp4 播放元件。
- 如果工具是隱藏工具，影片網址若放在公開 Release，知道網址的人仍可能直接開啟影片；若影片也需要保護，需另外設計權限或不要放公開網址。
