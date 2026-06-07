# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

block_cipher = None

# 收集 PySide6 的 DLL 和 plugins（关键：qwindows.dll 在这里）
pyside6_binaries = collect_dynamic_libs('PySide6')
pyside6_datas = collect_data_files('PySide6')

a = Analysis(
    ['gui_pyside6/main_window.py'],
    pathex=[],
    binaries=pyside6_binaries,
    datas=pyside6_datas + [
        ('config/system', 'config/system'),
        ('gui_pyside6/style.qss', 'gui_pyside6'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtCharts',
        'PySide6.QtPrintSupport',
        'gui_pyside6.models.data_frame_model',
        'gui_pyside6.models.workers',
        'gui_pyside6.dialogs.import_wizard_dialog',
        'core.rule_engine',
        'core.audit_logger',
        'numpy.core._methods',
        'numpy.lib.format',
        'pandas._libs.tslibs.np_datetime',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ZPP011偏差分析器_v42.0_preview',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # 先保留 console，方便看报错
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[],
)
