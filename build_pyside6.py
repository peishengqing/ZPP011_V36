#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 PySide6 版打包脚本
用法: python build_pyside6.py
"""
import os
import sys
import shutil
import PyInstaller.__main__
import datetime

# ── 应用信息 ──────────────────────────────────────────────────
APP_NAME = "ZPP011偏差分析器"
try:
    import json
    cfg_path = os.path.join(os.path.dirname(__file__), "config", "version.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            VERSION = cfg.get("version", "v42.0")
    else:
        VERSION = "v42.0"
except Exception:
    VERSION = "v42.0"

TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_NAME = f"{APP_NAME}_PySide6_{VERSION}_{TIMESTAMP}"

# ── 备份 dist 目录（防止 --clean 丢失旧版）────────────────
def backup_dist():
    dist_dir = os.path.join(os.path.dirname(__file__), "dist")
    if not os.path.exists(dist_dir):
        return
    # 备份到项目目录下，避免沙箱拦截
    backup_root = os.path.join(os.path.dirname(__file__), "exe_backups")
    os.makedirs(backup_root, exist_ok=True)
    for fname in os.listdir(dist_dir):
        if fname.endswith(".exe"):
            src = os.path.join(dist_dir, fname)
            dst_name = f"{os.path.splitext(fname)[0]}_{TIMESTAMP}.exe"
            shutil.copy2(src, os.path.join(backup_root, dst_name))
            print(f"[备份] {fname} -> {dst_name}")

# ── 清理旧构建 ─────────────────────────────────────────────────
def clean_build():
    build_dir = os.path.join(os.path.dirname(__file__), "build")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    # 不删 dist/，让 backup_dist 先执行

# ── 主流程 ───────────────────────────────────────────────────
def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    print("=" * 60)
    print(f"开始打包 PySide6 版: {OUTPUT_NAME}")
    print("=" * 60)

    # 备份和清理在沙箱外手动操作，这里跳过
    # backup_dist()
    # clean_build()
    pass

    sep = os.pathsep
    args = [
        "run_pyside6.py",          # 入口文件
        "--name", OUTPUT_NAME,
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
    ]

    # 图标
    for icon in ["ZPP011偏差分析器.ico", "icon.png", "icon.ico"]:
        if os.path.exists(icon):
            args.extend(["--icon", icon])
            break

    # 添加数据目录（config, gui_pyside6/theme.qss 等）
    data_dirs = ["config", "gui_pyside6"]
    for dirname in data_dirs:
        if os.path.exists(dirname):
            args.extend(["--add-data", f"{dirname}{sep}{dirname}"])

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
    excludes = ["tkinter", "matplotlib", "scipy"]
    for ex in excludes:
        args.extend(["--exclude", ex])

    args.extend(["--paths", base_dir])

    print("[INFO] PyInstaller 参数列表：")
    for i, a in enumerate(args):
        print(f"  {i:2d}: {a}")

    PyInstaller.__main__.run(args)

    # 检查输出
    exe_path = os.path.join("dist", f"{OUTPUT_NAME}.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n[成功] 输出文件: {exe_path}")
        print(f"[大小] {size_mb:.1f} MB")
    else:
        print("\n[失败] 未找到输出 exe 文件")
    print("=" * 60)


if __name__ == "__main__":
    main()
