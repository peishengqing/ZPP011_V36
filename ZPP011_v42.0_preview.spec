# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui_pyside6\\main_window.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config'), ('core', 'core'), ('analysis', 'analysis'), ('modules', 'modules'), ('domain', 'domain'), ('utils', 'utils'), ('gui_pyside6', 'gui_pyside6')],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'matplotlib.backends.backend_qtagg', 'openpyxl', 'pandas'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ZPP011_v42.0_preview',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
