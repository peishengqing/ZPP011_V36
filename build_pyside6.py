#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 PySide6 版打包脚本
用法: python build_pyside6.py

⚠️ 版本号统一规则：
  - 版本号、版本日志仅由 utils/version_history.py 管理
  - 打包前必须更新 version_history.py（新增一个版本条目）
  - 重复打包同一版本会报错退出
"""
import os
import sys
import shutil
import PyInstaller.__main__
import datetime

# ── 确保工作目录是项目根目录 ───────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# ── 从 version_history.py 读取版本号 ─────────────────────────
try:
    sys.path.insert(0, BASE_DIR)
    from utils.version_history import get_current_version, VERSION_HISTORY
    VERSION = get_current_version()
except Exception as e:
    print(f"❌ 无法读取 version_history.py：{e}")
    sys.exit(1)

APP_NAME = "ZPP011偏差分析器"
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_NAME = f"{APP_NAME}_PySide6_{VERSION}_{TIMESTAMP}"

# ── 版本号一致性检查 ───────────────────────────────────────────
latest = VERSION_HISTORY[0] if VERSION_HISTORY else {}
if latest.get("version") != VERSION:
    print(f"❌ 版本号不一致！version_history.py 最新条目为 {latest.get('version')}，"
          f"当前读取为 {VERSION}")
    sys.exit(1)

# ── 版本日志检查：打包前必须填写变更记录 ─────────────────────
has_log = bool(
    latest.get("features") or latest.get("fixes") or
    latest.get("optimizations") or latest.get("notes")
)
if not has_log:
    print(f"❌ 版本 {VERSION} 没有版本日志！请在 version_history.py 中填写变更记录再打包。")
    sys.exit(1)

# ── 重复打包检查：dist 已有同版本 exe 则报错 ────────────────
# 检查 dist/ 中是否有任何 exe 文件名包含当前版本号（两种命名规则都查）
if os.path.isdir("dist"):
    for f in os.listdir("dist"):
        if f.endswith(".exe") and f"_{VERSION}" in f:
            print(f"❌ 版本号 {VERSION} 已打包过！请先更新 version_history.py 版本号再打包。")
            print(f"   发现已有文件: {f}")
            sys.exit(1)

print(f"✅ 版本号 {VERSION} 验证通过，版本日志已更新，继续打包")

# ── 备份 dist 目录（防止 --clean 丢失旧版）────────────────
def backup_dist():
    dist_dir = os.path.join(BASE_DIR, "dist")
    if not os.path.exists(dist_dir):
        return
    # 备份到项目目录下，避免沙箱拦截
    backup_root = os.path.join(BASE_DIR, "exe_backups")
    os.makedirs(backup_root, exist_ok=True)
    for fname in os.listdir(dist_dir):
        if fname.endswith(".exe"):
            src = os.path.join(dist_dir, fname)
            dst_name = f"{os.path.splitext(fname)[0]}_{TIMESTAMP}.exe"
            shutil.copy2(src, os.path.join(backup_root, dst_name))
            print(f"[备份] {fname} -> {dst_name}")

# ── 清理旧构建 ───────────────────────────────────────────────
def clean_build():
    build_dir = os.path.join(BASE_DIR, "build")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    # 不删 dist/，让 backup_dist 先执行

# ── 主流程 ───────────────────────────────────────────────────
def main():
    # 工作目录已在模块加载时切换到 BASE_DIR，这里无需重复
    print("=" * 60)
    print(f"开始打包 PySide6 版: {OUTPUT_NAME}")
    print("=" * 60)

    # 备份和清理在沙箱外手动操作，这里跳过
    # backup_dist()
    # clean_build()
    pass

    # ── 自动备份源码 ─────────────────────────────────────────
    print("=" * 60)
    print("正在备份源码...")
    import zipfile
    from datetime import datetime as dt

    backup_base = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "source_backups")
    os.makedirs(backup_base, exist_ok=True)

    ts = dt.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"zpp011_source_{VERSION}_{ts}.zip"
    zip_path = os.path.join(backup_base, zip_name)

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
                    an = os.path.relpath(fp, BASE_DIR)
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
        os.remove(os.path.join(backup_base, old))
        print(f"[备份] 清理旧备份: {old}")

    print("=" * 60)

    sep = os.pathsep
    entry = os.path.join(BASE_DIR, "run_pyside6.py")
    args = [
        entry,                    # 入口文件（绝对路径，防止跨盘符报错）
        "--name", OUTPUT_NAME,
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        "--distpath", os.path.join(BASE_DIR, "dist"),   # 强制指定 dist 输出目录
    ]

    # 图标
    for icon in ["ZPP011偏差分析器.ico", "icon.png", "icon.ico"]:
        if os.path.exists(icon):
            args.extend(["--icon", icon])
            break

    # 添加数据目录（config, gui_pyside6/theme.qss 等）
    # 使用绝对路径，防止 PyInstaller 在错误的工作目录里查找
    data_dirs = ["config", "gui_pyside6"]
    for dirname in data_dirs:
        abs_dir = os.path.join(BASE_DIR, dirname)
        if os.path.exists(abs_dir):
            args.extend(["--add-data", f"{abs_dir}{sep}{dirname}"])

    # PySide6 隐式导入（关键！）
    hidden_imports = [
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtWidgets",
        "PySide6.QtGui",
        "pandas", "openpyxl",
        "pptx", "pptx.util", "pptx.enum.text", "pptx.enum.chart",
        "numpy", "dateutil",
    ]
    for imp in hidden_imports:
        args.extend(["--hidden-import", imp])

    # 排除不需要的大包（减小体积）
    # 注意：不要排除 matplotlib！dashboard_dialog.py 用到了
    excludes = ["tkinter", "scipy"]
    for ex in excludes:
        args.extend(["--exclude", ex])

    args.extend(["--paths", BASE_DIR])

    print("[INFO] PyInstaller 参数列表：")
    for i, a in enumerate(args):
        print(f"  {i:2d}: {a}")

    PyInstaller.__main__.run(args)

    # 检查输出（使用 BASE_DIR 绝对路径）
    exe_path = os.path.join(BASE_DIR, "dist", f"{OUTPUT_NAME}.exe")
    if not os.path.exists(exe_path):
        # 兜底：检查当前工作目录下的 dist
        alt_path = os.path.join("dist", f"{OUTPUT_NAME}.exe")
        if os.path.exists(alt_path):
            exe_path = os.path.abspath(alt_path)
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n[成功] 输出文件: {exe_path}")
        print(f"[大小] {size_mb:.1f} MB")
    else:
        print("\n[失败] 未找到输出 exe 文件")
        print(f"期望路径: {exe_path}")
        # 列出 dist 目录内容帮助调试
        for d in [os.path.join(BASE_DIR, "dist"), "dist"]:
            if os.path.exists(d):
                print(f"{d} 目录内容: {os.listdir(d)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
