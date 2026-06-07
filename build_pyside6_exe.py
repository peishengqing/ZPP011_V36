# -*- coding: utf-8 -*-
"""打包 PySide6 版本的 EXE（v42.0 预览版 - 修复版）"""
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
    opts = [
        "gui_pyside6/main_window.py",
        "--name=ZPP011偏差分析器_v42.1_预警看板",
        "--windowed",
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
        # PySide6 插件（Qt 平台插件等关键 DLL）
        "--collect-all=pyside6",
        # 业务模块隐藏导入
        "--hidden-import=gui_pyside6.models.data_frame_model",
        "--hidden-import=gui_pyside6.models.workers",
        "--hidden-import=gui_pyside6.dialogs.import_wizard_dialog",
        "--hidden-import=gui_pyside6.dialogs.rule_config_dialog",
        "--hidden-import=gui_pyside6.dialogs.drill_down_dialog",
        "--hidden-import=gui_pyside6.dialogs.settings_dialog",
        "--hidden-import=gui_pyside6.dialogs.alert_dialog",
        "--hidden-import=core.alert_monitor",
        "--hidden-import=core.rule_engine",
        "--hidden-import=core.audit_logger",
        "--hidden-import=analysis.bom_diff",
        "--hidden-import=utils.excel_helper",
        # numpy/pandas 后端
        "--hidden-import=numpy.core._methods",
        "--hidden-import=numpy.lib.format",
        "--hidden-import=pandas._libs.tslibs.np_datetime",
    ])
    print("=" * 60)
    print("开始打包 PySide6 EXE（console 模式）")
    print("=" * 60)
    for o in opts:
        print(" ", o)
    pyinstaller_run(opts)
