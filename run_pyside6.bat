@echo off
chcp 65001 > nul
echo ================================
echo   ZPP011 PySide6 启动脚本
echo ================================
echo.

REM 尝试找到 Python
set PYTHON_EXE=python

%PYTHON_EXE% -c "import PySide6" 2>nul
if errorlevel 1 (
    echo [警告] PySide6 未安装，尝试安装...
    %PYTHON_EXE% -m pip install PySide6==6.8.0.2 -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [信息] 正在启动 PySide6 主窗口...
echo.

cd /d "%~dp0"
%PYTHON_EXE% gui_pyside6\main_window.py

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，错误代码: %errorlevel%
    pause
)
