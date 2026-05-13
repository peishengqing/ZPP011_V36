# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('config', 'config'), ('inventory_loader.py', '.')],
    hiddenimports=['widgets', 'storage', 'analysis', 'domain', 'utils', 'ppt_generator', 'inventory_loader', 'config', 'matplotlib', 'gui', 'gui.app', 'gui.events', 'gui.ui_builder', 'gui.inventory_view', 'gui.tree_utils', 'alt_manager'],
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
    name='ZPP011_v36.3',
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