@echo off
chcp 65001 >nul
setlocal

REM 打包 Launcher 為單一 exe。
REM 預先安裝:pip install pyinstaller

set NAME=MyToolsLauncher
set ENTRY=run.py

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 找不到 pyinstaller。請先執行:pip install pyinstaller
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %NAME%.spec del /q %NAME%.spec

pyinstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name %NAME% ^
    %ENTRY%

if errorlevel 1 (
    echo [錯誤] PyInstaller 打包失敗
    exit /b 1
)

echo.
echo [完成] 產出:dist\%NAME%.exe
endlocal
