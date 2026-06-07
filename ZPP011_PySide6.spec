# -*- mode: python ; coding: utf-8 -*-

# PySide6 版打包配置
# 用法: pyinstaller ZPP011_PySide6.spec

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# ── 数据文件 ─────────────────────────────────────────────────
datas = [
    ('config', 'config'),
    ('gui_pyside6', 'gui_pyside6'),
]

# ── 收集 PySide6 全部依赖（关键！）─────────────────────────
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]
binaries = tmp_ret[1]
hidden_imports = tmp_ret[2]

# ── 收集 pandas ──────────────────────────────────────────────
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hidden_imports += tmp_ret[2]

# ── 收集 openpyxl ────────────────────────────────────────────
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hidden_imports += tmp_ret[2]

# ── 收集 python-pptx ─────────────────────────────────────────
try:
    tmp_ret = collect_all('pptx')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hidden_imports += tmp_ret[2]
except Exception:
    pass

# ── 手动添加隐式导入 ─────────────────────────────────────────
hidden_imports += [
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtWidgets',
    'PySide6.QtGui',
    'PySide6.QtNetwork',
    'pandas',
    'openpyxl',
    'openpyxl.styles',
    'pptx',
    'pptx.util',
    'pptx.enum.text',
    'numpy',
    'dateutil',
]

# ── Analysis ──────────────────────────────────────────────────
a = Analysis(
    ['run_pyside6.py'],
    pathex=['E:\\zpp011_dev\\模块化脚本'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ZPP011_PySide6_v40.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
