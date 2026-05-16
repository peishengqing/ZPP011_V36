@echo off
chcp 65001 >nul
cd /d E:\zpp011_dev\模块化脚本\gui
python stock_summary_standalone.py
echo.
echo 程序执行完毕，按任意键退出...
pause >nul