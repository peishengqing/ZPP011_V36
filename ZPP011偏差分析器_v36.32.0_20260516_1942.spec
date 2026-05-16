# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('widgets.py', '.'), ('gui', 'gui'), ('analysis', 'analysis'), ('storage', 'storage'), ('domain', 'domain'), ('utils', 'utils'), ('config', 'config'), ('changelog.json', '.')]
binaries = []
hiddenimports = ['pandas', 'openpyxl', 'PIL', 'PIL.Image', 'PIL.ImageTk', 'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox', 'ppt_generator', 'pptx', 'domain', 'domain.alt_material', 'domain.alt_material.alt_manager', 'utils', 'utils.helpers', 'widgets', 'storage.storage', 'analysis.analyzer', 'gui.app', 'gui.events', 'gui.events.EventsMixIn', 'gui.inventory_view', 'gui.tree_utils', 'gui.ui_builder']
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['E:\\zpp011_dev\\模块化脚本\\gui\\app.py'],
    pathex=['E:\\zpp011_dev\\模块化脚本'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='ZPP011偏差分析器_v36.32.0_20260516_1942',
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
