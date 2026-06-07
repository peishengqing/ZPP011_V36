@echo off
chcp 65001 >nul
title ZPP011 PySide6 一键打包
echo ========================================
echo   ZPP011 PySide6 版一键打包工具
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请确认已安装并添加到 PATH
    pause
    exit /b 1
)

echo [1/4] 安装依赖...
pip install PySide6 pandas openpyxl xlsxwriter matplotlib python-pptx pyinstaller -q

echo [2/4] 清理旧文件...
if exist "build" rd /s /q build
if exist "dist\ZPP011偏差分析器_v42.0_preview.exe" del /f /q "dist\ZPP011偏差分析器_v42.0_preview.exe"

echo [3/4] 生成 spec 文件...
set SPECFILE=temp_pyside6.spec
(
echo # -*- mode: python ; coding: utf-8 -*-
echo a = Analysis(['gui_pyside6/main_window.py'],
echo              pathex=[],
echo              binaries=[],
echo              datas=[('config', 'config'), ('core', 'core'), ('analysis', 'analysis'), ('modules', 'modules'), ('domain', 'domain'), ('utils', 'utils'), ('gui_pyside6', 'gui_pyside6')],
echo              hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'matplotlib.backends.backend_qtagg', 'openpyxl', 'pandas'],
echo              hookspath=[],
echo              hooksconfig={{}},
echo              runtime_hooks=[],
echo              excludes=[],
echo              noarchive=False)
echo pyz = PYZ(a.pure)
echo exe = EXE(pyz,
echo           a.scripts,
echo           a.binaries,
echo           a.datas,
echo           [],
echo           name='ZPP011偏差分析器_v42.0_preview',
echo           debug=False,
echo           bootloader_ignore_signals=False,
echo           strip=False,
echo           upx=True,
echo           upx_exclude=[],
echo           runtime_tmpdir=None,
echo           console=False,
echo           disable_windowed_traceback=False,
echo           argv_emulation=False,
echo           target_arch=None,
echo           codesign_identity=None,
echo           entitlements_file=None,
echo           icon='ZPP011偏差分析器.ico')
) > %SPECFILE%

echo [4/4] 执行打包...
pyinstaller %SPECFILE% --noconfirm
del %SPECFILE%

if errorlevel 1 (
    echo [错误] 打包失败，请检查控制台输出
    pause
    exit /b 1
)

echo.
echo 打包完成！
echo 输出文件：dist\ZPP011偏差分析器_v42.0_preview.exe
echo.
pause