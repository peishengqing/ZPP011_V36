# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('config\\system', 'config/system'), ('gui_pyside6\\style.qss', 'gui_pyside6')]
binaries = []
hiddenimports = ['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'PySide6.QtCharts', 'PySide6.QtPrintSupport', 'gui_pyside6.main_window', 'gui_pyside6.models.data_frame_model', 'gui_pyside6.models.workers', 'gui_pyside6.widgets.filter_panel', 'gui_pyside6.widgets.toast', 'gui_pyside6.dialogs.import_wizard_dialog', 'gui_pyside6.dialogs.rule_config_dialog', 'gui_pyside6.dialogs.drill_down_dialog', 'gui_pyside6.dialogs.settings_dialog', 'gui_pyside6.dialogs.alert_dialog', 'gui_pyside6.dialogs.unit_summary_dialog', 'gui_pyside6.dialogs.dashboard_dialog', 'gui_pyside6.dialogs.history_compare_dialog', 'gui_pyside6.dialogs.batch_operations_dialog', 'core.alert_monitor', 'core.rule_engine', 'core.audit_logger', 'core.config_manager', 'core.ai_client', 'core.read_status', 'core.fingerprint', 'core.change_detector', 'analysis.analyzer', 'analysis.net_offset', 'analysis.bom_diff', 'analysis.excel_builder.sheet5_full', 'modules.audit.filters.filter_engine', 'domain.alt_material.alt_manager', 'utils.excel_helper', 'utils.version_history', 'numpy.core._methods', 'numpy.lib.format', 'pandas._libs.tslibs.np_datetime']
tmp_ret = collect_all('pyside6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['run_pyside6.py'],
    pathex=[],
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
    name='ZPP011偏差分析器_v42.1',
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
