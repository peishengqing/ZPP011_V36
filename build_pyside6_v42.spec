# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# ── 收集 PySide6 动态库和 data 文件 ─────────────────────
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

pyside6_binaries = collect_dynamic_libs('PySide6')
pyside6_datas = collect_data_files('PySide6')

# ── 数据文件 ──────────────────────────────────────────────
datas = pyside6_datas + [
    ('config/system', 'config/system'),
]

import os
if os.path.isfile(os.path.join('config', 'template.pptx')):
    datas.append(('config/template.pptx', 'config'))

# ── 隐藏导入 ─────────────────────────────────────────────
hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtCharts',
    'PySide6.QtPrintSupport',
    'PySide6.QtNetwork',
    'gui_pyside6.models.data_frame_model',
    'gui_pyside6.models.workers',
    'gui_pyside6.dialogs.import_wizard_dialog',
    'gui_pyside6.dialogs.rule_config_dialog',
    'gui_pyside6.dialogs.dashboard_dialog',
    'gui_pyside6.dialogs.health_check_dialog',
    'gui_pyside6.dialogs.benefit_report_dialog',
    'gui_pyside6.dialogs.remark_cleaner_dialog',
    'gui_pyside6.widgets.filter_panel',
    'core.rule_engine',
    'core.ai_client',
    'analysis.analyzer',
    'analysis.alt_material.alt_manager',
    'openpyxl',
    'openpyxl.styles',
    'pptx',
    'pptx.util',
    'numpy',
    'numpy.core._methods',
    'numpy.lib.format',
    'pandas',
    'pandas._libs.tslibs.np_datetime',
    'dateutil',
]

a = Analysis(
    ['gui_pyside6/main_window.py'],
    pathex=[os.path.abspath('.')],
    binaries=pyside6_binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ZPP011偏差分析器_v42.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # 最终版无控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[],
)
