@echo off
chcp 65001 >nul
title ZPP011 一键打包工具（无图标无changelog）
echo ========================================
echo   ZPP011 偏差分析器 - 一键打包
echo ========================================
echo.

cd /d "%~dp0"
set PROJECT_DIR=%CD%
echo 当前目录：%PROJECT_DIR%
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python
    pause
    exit /b 1
)
echo Python 环境正常。
echo.

echo 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec
echo 清理完成。
echo.

set ENTRY_FILE=gui\app.py
if not exist %ENTRY_FILE% (
    echo 错误：找不到入口文件 %ENTRY_FILE%
    pause
    exit /b 1
)
echo 入口文件：%ENTRY_FILE%
echo.

echo 开始打包，请稍候...
pyinstaller --onefile --windowed --name "ZPP011偏差分析器_v36.12" ^
    --add-data "widgets.py;." ^
    --add-data "gui;gui" ^
    --add-data "analysis;analysis" ^
    --add-data "storage;storage" ^
    --add-data "domain;domain" ^
    --add-data "utils;utils" ^
    --hidden-import pandas ^
    --hidden-import openpyxl ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageTk ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.filedialog ^
    --hidden-import tkinter.messagebox ^
    --hidden-import widgets ^
    --hidden-import storage.storage ^
    --hidden-import analysis.analyzer ^
    --hidden-import gui.app ^
    --hidden-import gui.events ^
    --hidden-import gui.inventory_view ^
    --hidden-import gui.tree_utils ^
    --hidden-import gui.ui_builder ^
    --collect-all pandas ^
    --collect-all openpyxl ^
    --paths "%PROJECT_DIR%" ^
    %ENTRY_FILE%

if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)

echo.
echo 打包成功！输出文件：dist\ZPP011偏差分析器_v36.12.exe
dir dist\*.exe
echo.
set /p open_dir="是否打开输出目录？(Y/N): "
if /i "%open_dir%"=="Y" start "" "dist"

pause