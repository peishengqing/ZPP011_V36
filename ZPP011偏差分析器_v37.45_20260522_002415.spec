# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('config', 'config'), ('temp', 'temp'), ('logs', 'logs'), ('C:\\Users\\Administrator\\AppData\\Local\\hermes\\hermes-agent\\venv\\Lib\\site-packages\\matplotlib\\mpl-data', 'mpl-data')]
binaries = []
hiddenimports = ['pandas', 'pandas.core', 'pandas.core.algorithms', 'pandas.core.arrays', 'openpyxl', 'openpyxl.styles', 'PIL', 'PIL.Image', 'PIL.ImageTk', 'matplotlib', 'matplotlib.backends', 'matplotlib.backends.backend_agg', 'matplotlib.pyplot', 'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox', 'ctypes', 'json', 'csv', 'calendar', 'shutil', 'traceback', 'threading', 'datetime', 'time', 'glob', 'widgets', 'storage', 'storage.storage', 'analysis', 'analysis.analyzer', 'gui', 'gui.app', 'gui.events', 'gui.inventory_view', 'gui.tree_utils', 'gui.ui_builder', 'core', 'core.decorators', 'core.state_store', 'core.config_manager', 'core.task_manager', 'core.rule_engine', 'core.exporter', 'core.logger', 'utils', 'utils.version_history']
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('matplotlib')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
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
    name='ZPP011偏差分析器_v37.45_20260522_002415',
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
