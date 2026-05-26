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
if exist dist  rmdir /s /q dist
if exist %NAME%.spec del /q %NAME%.spec

REM 動態載入的工具若含穩定 ABI 原生擴充(如 PyMuPDF 的 _extra.pyd),
REM 依賴 python3.dll(穩定 ABI 轉發 DLL)。PyInstaller 只帶 pythonXY.dll,
REM 不帶 python3.dll,凍結後外部 .pyd 會「DLL load failed / 找不到模組」。
REM 把 python3.dll 一併打包進去。
for /f "delims=" %%i in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'python3.dll'))"') do set PY3DLL=%%i

REM 注意:launcher 是動態載入工具的 host。
REM PyInstaller 只會打包 launcher 自己用到的標準庫,
REM 但工具(如 openpyxl)需要 xml 等模組,必須在此明確納入。
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name %NAME% ^
    --add-binary "%PY3DLL%;." ^
    --hidden-import tkinter.filedialog ^
    --hidden-import tkinter.scrolledtext ^
    --hidden-import tkinter.messagebox ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.font ^
    --hidden-import tkinter.simpledialog ^
    --hidden-import tkinter.colorchooser ^
    --hidden-import importlib.util ^
    --collect-submodules xml ^
    --collect-submodules html ^
    --hidden-import _elementtree ^
    --hidden-import pyexpat ^
    --hidden-import decimal ^
    --hidden-import _decimal ^
    --hidden-import smtplib ^
    --collect-submodules email ^
    --hidden-import ssl ^
    --collect-submodules unittest ^
    --collect-submodules doctest ^
    --hidden-import logging.config ^
    --hidden-import logging.handlers ^
    --hidden-import csv ^
    --hidden-import sqlite3 ^
    %ENTRY%

if errorlevel 1 (
    echo [錯誤] PyInstaller 打包失敗
    exit /b 1
)

echo.
echo [完成] 產出:dist\%NAME%.exe
endlocal
