# -*- coding: utf-8 -*-
"""打包 PySide6 版本的 EXE（v42.1 功能迭代版）"""
import sys
import os
from datetime import datetime

# 确保当前目录是项目根目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyInstaller.__main__ import run as pyinstaller_run

# 准备 add-data 参数：整目录打包 config（含根目录 json、system、prompts、template.pptx 等），
# 避免遗漏 material_name_presets.json / auto_quarantine_config.json / column_widths.json 等运行时配置
add_data_opts = []
if os.path.isdir("config"):
    add_data_opts.append(f"--add-data={os.path.join('config')};config")
if os.path.isfile(os.path.join("gui_pyside6", "style.qss")):
    add_data_opts.append(f"--add-data={os.path.join('gui_pyside6', 'style.qss')};gui_pyside6")

if __name__ == "__main__":
    # 检测是否要调试模式（带控制台）
    import sys as _sys
    from utils.version_history import get_current_version
    debug_mode = '--debug' in _sys.argv
    version = get_current_version()
    base_name = f"ZPP011偏差分析器_{version}"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    exe_name = f"{base_name}_{ts}"

    # ── 版本号检查：防止重复打包（按版本号基础名前缀判断，与时间戳无关）──
    if os.path.isdir("dist"):
        existing = [f for f in os.listdir("dist") if f.startswith(base_name) and f.endswith(".exe")]
        if existing:
            print(f"❌ 版本号 {version} 已打包过！请先更新 version_history.py 版本号再打包。")
            print(f"   发现已有文件: {existing[0]}")
            sys.exit(1)

    # ── 版本日志检查：打包前必须更新日志 ──
    from utils.version_history import VERSION_HISTORY
    latest = VERSION_HISTORY[0] if VERSION_HISTORY else {}
    has_log = bool(latest.get("features") or latest.get("fixes") or
                   latest.get("optimizations") or latest.get("notes"))
    if not has_log:
        print(f"❌ 版本 {version} 没有版本日志！请在 version_history.py 中填写变更记录再打包。")
        sys.exit(1)
    if latest.get("version") != version:
        print(f"❌ 版本号不一致！version_history.py 最新条目为 {latest.get('version')}，当前读取为 {version}")
        sys.exit(1)
    print(f"✅ 版本号 {version} 验证通过，版本日志已更新，继续打包")

    window_mode = "--console" if not debug_mode else "--console"

    # ── 自动备份源码 ──
    import zipfile
    from datetime import datetime

    backup_base = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "source_backups")
    os.makedirs(backup_base, exist_ok=True)

    zip_name = f"zpp011_source_{version}_{ts}.zip"
    zip_path = os.path.join(backup_base, zip_name)

    # 要备份的目录和文件
    backup_items = [
        "analysis", "core", "domain", "modules", "utils",
        "gui_pyside6", "gui_pyside6/components", "gui_pyside6/controllers",
        "gui_pyside6/dialogs", "gui_pyside6/models", "gui_pyside6/services",
        "gui_pyside6/viewmodels", "gui_pyside6/widgets",
        "config", "config/system", "config/prompts",
        "CHANGELOG.md", "README.md",
        "run_pyside6.py", "ZPP011_技术蓝图_v11.0.md",
    ]
    files_to_add = []
    for item in backup_items:
        if os.path.isdir(item):
            for root, dirs, filenames in os.walk(item):
                for fn in filenames:
                    fp = os.path.join(root, fn)
                    an = os.path.relpath(fp, os.path.dirname(os.path.abspath(__file__)))
                    files_to_add.append((fp, an))
        elif os.path.isfile(item):
            files_to_add.append((item, item))

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fp, an in files_to_add:
            zf.write(fp, an)

    print(f"[备份] 源码已备份到: {zip_path}")
    print(f"[备份] 共 {len(files_to_add)} 个文件")

    # 只保留最近 20 个备份
    existing = sorted(
        [f for f in os.listdir(backup_base) if f.endswith('.zip')],
        reverse=True
    )
    for old in existing[20:]:
        try:
            os.remove(os.path.join(backup_base, old))
            print(f"[备份] 清理旧备份: {old}")
        except OSError:
            # 沙箱/回收站不可用等导致删除失败时不阻断打包（旧备份多留一个无害）
            print(f"[备份] 清理旧备份跳过(删除被拦截): {old}")

    opts = [
        "run_pyside6.py",
        f"--name={exe_name}",
        window_mode,
        "--onefile",
        "--noconfirm",
        # --clean 注释掉：保留 dist 已有 exe 不被清空
        # "--clean",
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
        "--hidden-import=analysis.dashboard_html",
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
        # SSL/crypto DLLs（PyInstaller onefile 不会自动收集 cryptography 的 OpenSSL DLL）
        "--collect-all=cryptography",
    ])
    print("=" * 60)
    print("开始打包 PySide6 EXE")
    print("=" * 60)
    for o in opts:
        print(" ", o)
    pyinstaller_run(opts)
