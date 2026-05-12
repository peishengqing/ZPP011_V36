@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo ZPP011 Deviation Analyzer - Build Tool
echo Auto build EXE without garbled characters
echo ==============================================

pyinstaller -w -F --noconsole --hidden-import=matplotlib ZPP011*.py

echo.
echo Build completed! Check dist folder.
pause