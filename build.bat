@echo off
chcp 65001 >nul
cd /d "%~dp0"
pyinstaller -F --hidden-import=matplotlib --hidden-import=tkinter --hidden-import=ttk gui/app.py
pause