@echo off
chcp 65001 >nul
cd /d E:\zpp011_dev\模块化脚本

echo [1/2] Cleaning old build...
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

echo [2/2] Starting PyInstaller (5-15min)...
C:\Users\Administrator\AppData\Local\Programs\Python\Python311\Scripts\pyinstaller.exe --onefile --windowed --name "ZPP011偏差分析器_v36.12" --add-data "widgets.py;." --add-data "gui;gui" --add-data "analysis;analysis" --add-data "storage;storage" --add-data "domain;domain" --add-data "utils;utils" --hidden-import pandas --hidden-import openpyxl --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageTk --hidden-import tkinter --hidden-import tkinter.ttk --hidden-import tkinter.filedialog --hidden-import tkinter.messagebox --hidden-import widgets --hidden-import storage.storage --hidden-import analysis.analyzer --hidden-import gui.app --hidden-import gui.events --hidden-import gui.inventory_view --hidden-import gui.tree_utils --hidden-import gui.ui_builder --collect-all pandas --collect-all openpyxl --paths "E:\zpp011_dev\模块化脚本" gui/app.py

if exist "dist\ZPP011偏差分析器_v36.12.exe" (
    echo [OK] Done!
    echo Path: E:\zpp011_dev\模块化脚本\dist\ZPP011偏差分析器_v36.12.exe
) else (
    echo [FAIL] Build failed - check errors above.
)
pause