@echo off
chcp 65001 > nul
echo ================================
echo   ZPP011 PySide6 启动脚本
echo ================================
echo.

REM Pin the interpreter. A bare "python" follows PATH, and PATH may hold another
REM venv whose PySide6/numpy versions clash (and which has a stale copy of this
REM project installed) -> window flashes open and dies. Try known-good first.
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

echo [信息] Python: %PYTHON_EXE%
echo [信息] 正在启动 PySide6 主窗口...
echo.

cd /d "%~dp0"
REM run_pyside6.py puts the project root on sys.path; launching
REM gui_pyside6\main_window.py directly cannot import the gui_pyside6 package.
"%PYTHON_EXE%" run_pyside6.py

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，错误代码: %errorlevel%
    pause
)
