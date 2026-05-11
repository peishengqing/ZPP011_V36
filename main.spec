# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\zpp011_dev\\模块化脚本\\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('E:\\zpp011_dev\\模块化脚本\\changelog.json', '.'),
        ('E:\\zpp011_dev\\模块化脚本\\ZPP011偏差分析器.icon.ico', '.'),
        ('E:\\zpp011_dev\\模块化脚本\\ZPP011偏差分析器.icon.png', '.'),
    ],
    hiddenimports=['storage', 'widgets', 'ppt_generator', 'alt_manager', 'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageFilter'],
    hookspath=['C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\hooks'],
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
    name='ZPP011生产偏差分析器_v35.0',
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
    icon='E:\\zpp011_dev\\模块化脚本\\ZPP011偏差分析器.icon.ico',
)
