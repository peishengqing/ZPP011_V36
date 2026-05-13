# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui\\app.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['widgets', 'storage', 'analysis', 'domain', 'utils', 'ppt_generator', 'inventory_loader', 'config', 'matplotlib'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_err.py'],
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
    name='ZPP011_v36_debug2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
