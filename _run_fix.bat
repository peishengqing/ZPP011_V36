@echo off
cd /d "E:\zpp011_dev\模块化脚本"
python _add_doughnut_chart.py
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 执行失败
    pause
) else (
    echo ✅ 执行成功
)
