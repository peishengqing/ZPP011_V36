# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui\\events.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config'), ('config/version.json', 'config'), ('.zpp011_audit', '.zpp011_audit'), ('inventory_loader.py', '.'), ('build_log.md', '.')],
    hiddenimports=[],
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
    name='偏差分析+库存流水智能助手_v36.2',
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
