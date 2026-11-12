@echo off
chcp 65001 > nul
echo ================================
echo   ZPP011 PySide6 启动脚本
echo ================================
echo.

REM 先把 Python 锁定到装好依赖的那个解释器。裸 python 是跟着系统 PATH 找的，
REM PATH 里一旦混进别的虚拟环境，双击就会挑到错的 Python：那边 PySide6 与 numpy
REM 版本对不上、还会 import 到 site-packages 里的旧项目副本，窗口一闪就退。
set PYTHON_EXE=python
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe

"%PYTHON_EXE%" -c "import PySide6" 2>nul
if errorlevel 1 set PYTHON_EXE=python

"%PYTHON_EXE%" -c "import PySide6" 2>nul
if errorlevel 1 (
    echo [警告] PySide6 未安装，尝试安装...
    %PYTHON_EXE% -m pip install PySide6==6.8.0.2 -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [信息] 使用的 Python： %PYTHON_EXE%
echo [信息] 正在启动 PySide6 主窗口...
echo.

cd /d "%~dp0"
REM 走 run_pyside6.py：它先把项目根目录加进模块搜索路径。直接跑
REM gui_pyside6\main_window.py 时 Python 找不到 gui_pyside6 这个包。
"%PYTHON_EXE%" run_pyside6.py

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，错误代码: %errorlevel%
    pause
)
