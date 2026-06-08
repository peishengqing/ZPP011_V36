# -*- coding: utf-8 -*-
"""打包 PySide6 版本的 EXE（v42.1 功能迭代版）"""
import sys
import os

# 确保当前目录是项目根目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyInstaller.__main__ import run as pyinstaller_run

# 准备 add-data 参数，只加存在的目录
add_data_opts = []
if os.path.isdir("config/system"):
    add_data_opts.append(f"--add-data={os.path.join('config', 'system')};config/system")
if os.path.isdir("config/prompts"):
    add_data_opts.append(f"--add-data={os.path.join('config', 'prompts')};config/prompts")
if os.path.isfile(os.path.join("gui_pyside6", "style.qss")):
    add_data_opts.append(f"--add-data={os.path.join('gui_pyside6', 'style.qss')};gui_pyside6")
if os.path.isfile(os.path.join("config", "template.pptx")):
    add_data_opts.append(f"--add-data={os.path.join('config', 'template.pptx')};config")

if __name__ == "__main__":
    # 检测是否要调试模式（带控制台）
    import sys as _sys
    debug_mode = '--debug' in _sys.argv
    exe_name = "ZPP011偏差分析器_v42.1"
    window_mode = "--windowed" if not debug_mode else "--console"

    opts = [
        "run_pyside6.py",
        f"--name={exe_name}",
        window_mode,
        "--onefile",
        "--noconfirm",
        "--clean",
    ]
    opts.extend(add_data_opts)
    opts.extend([
        # PySide6 必要隐藏导入
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtCharts",
        "--hidden-import=PySide6.QtPrintSupport",
        # PySide6 插件
        "--collect-all=pyside6",
        # 业务模块隐藏导入
        "--hidden-import=gui_pyside6.main_window",
        "--hidden-import=gui_pyside6.models.data_frame_model",
        "--hidden-import=gui_pyside6.models.workers",
        "--hidden-import=gui_pyside6.widgets.filter_panel",
        "--hidden-import=gui_pyside6.widgets.toast",
        "--hidden-import=gui_pyside6.dialogs.import_wizard_dialog",
        "--hidden-import=gui_pyside6.dialogs.rule_config_dialog",
        "--hidden-import=gui_pyside6.dialogs.drill_down_dialog",
        "--hidden-import=gui_pyside6.dialogs.settings_dialog",
        "--hidden-import=gui_pyside6.dialogs.alert_dialog",
        "--hidden-import=gui_pyside6.dialogs.unit_summary_dialog",
        "--hidden-import=gui_pyside6.dialogs.dashboard_dialog",
        "--hidden-import=gui_pyside6.dialogs.history_compare_dialog",
        "--hidden-import=gui_pyside6.dialogs.batch_operations_dialog",
        "--hidden-import=core.alert_monitor",
        "--hidden-import=core.rule_engine",
        "--hidden-import=core.audit_logger",
        "--hidden-import=core.config_manager",
        "--hidden-import=core.ai_client",
        "--hidden-import=core.read_status",
        "--hidden-import=core.fingerprint",
        "--hidden-import=core.change_detector",
        "--hidden-import=analysis.analyzer",
        "--hidden-import=analysis.net_offset",
        "--hidden-import=analysis.bom_diff",
        "--hidden-import=analysis.excel_builder.sheet5_full",
        "--hidden-import=modules.audit.filters.filter_engine",
        "--hidden-import=domain.alt_material.alt_manager",
        "--hidden-import=utils.excel_helper",
        "--hidden-import=utils.version_history",
        # numpy/pandas 后端
        "--hidden-import=numpy.core._methods",
        "--hidden-import=numpy.lib.format",
        "--hidden-import=pandas._libs.tslibs.np_datetime",
    ])
    print("=" * 60)
    print("开始打包 PySide6 EXE")
    print("=" * 60)
    for o in opts:
        print(" ", o)
    pyinstaller_run(opts)
