#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" ZPP011 一键打包脚本 - 自动备份旧版本 """

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

PYTHON_EXE = Path(r"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe")
PROJECT_DIR = Path(__file__).parent
DIST_DIR = PROJECT_DIR / "dist"
BACKUP_DIR = PROJECT_DIR / "dist_backup"
RELEASE_DIR = Path(r"E:\zpp011_dev\发布包")
CHANGELOG_SOURCE = RELEASE_DIR / "changelog.json"


def log(msg, level="info"):
    icons = {"info": "ℹ️", "success": "✅", "warn": "⚠️", "error": "❌"}
    print(f"{icons.get(level, '')} {msg}")


def get_version():
    """从 version.json 读取版本号"""
    version_file = PROJECT_DIR / "config" / "version.json"
    if version_file.exists():
        import json
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version", "unknown")
    return "unknown"


def sync_changelog():
    """复制 changelog.json 到项目目录（供打包进 exe）"""
    if CHANGELOG_SOURCE.exists():
        dest = PROJECT_DIR / "changelog.json"
        shutil.copy2(CHANGELOG_SOURCE, dest)
        log(f"已同步 changelog.json 到项目目录", "info")
    else:
        log(f"未找到 changelog.json，跳过同步", "warn")


def backup_old_exe():
    """备份旧版本 exe 到 dist_backup"""
    BACKUP_DIR.mkdir(exist_ok=True)

    if DIST_DIR.exists():
        exe_files = list(DIST_DIR.glob("*.exe"))
        if exe_files:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_subdir = BACKUP_DIR / f"dist_{timestamp}"
            backup_subdir.mkdir(exist_ok=True)

            for exe in exe_files:
                dest = backup_subdir / exe.name
                shutil.copy2(exe, dest)
                log(f"已备份: {exe.name}", "success")
            log(f"备份目录: {backup_subdir}", "success")
        else:
            log("dist 目录为空，跳过备份", "warn")
    else:
        log("dist 目录不存在，跳过备份", "warn")


def clean_build():
    """清理旧构建文件"""
    for item in ["build", "*.spec"]:
        path = PROJECT_DIR / item.replace("*", "")
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            log(f"已清理: {item}", "info")


def build_exe(version):
    """执行 PyInstaller 打包"""
    entry = PROJECT_DIR / "gui" / "app.py"
    if not entry.exists():
        log(f"入口文件不存在: {entry}", "error")
        sys.exit(1)

    exe_name = f"ZPP011偏差分析器_{version}"

    cmd = [
        str(PYTHON_EXE), "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--name", exe_name,
        "--add-data", "widgets.py;.",
        "--add-data", "gui;gui",
        "--add-data", "analysis;analysis",
        "--add-data", "storage;storage",
        "--add-data", "domain;domain",
        "--add-data", "utils;utils",
        "--add-data", "config;config",
        "--add-data", "changelog.json;.",
        "--hidden-import", "pandas",
        "--hidden-import", "openpyxl",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageTk",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
        "--hidden-import", "ppt_generator",
        "--hidden-import", "pptx",
        "--hidden-import", "domain",
        "--hidden-import", "domain.alt_material",
        "--hidden-import", "domain.alt_material.alt_manager",
        "--hidden-import", "utils",
        "--hidden-import", "utils.helpers",
        "--hidden-import", "widgets",
        "--hidden-import", "storage.storage",
        "--hidden-import", "analysis.analyzer",
        "--hidden-import", "gui.app",
        "--hidden-import", "gui.events",
        "--hidden-import", "gui.events.EventsMixIn",
        "--hidden-import", "gui.inventory_view",
        "--hidden-import", "gui.tree_utils",
        "--hidden-import", "gui.ui_builder",
        "--collect-all", "pandas",
        "--collect-all", "openpyxl",
        "--paths", str(PROJECT_DIR),
        str(entry),
    ]

    log("开始打包 (5-15分钟) ...", "info")
    log(f"版本: {version}", "info")

    import subprocess
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))

    if result.returncode != 0:
        log("打包失败!", "error")
        sys.exit(1)

    return PROJECT_DIR / "dist" / f"{exe_name}.exe"


def copy_to_release(exe_path):
    """复制新版本到发布包目录"""
    if RELEASE_DIR.exists():
        dest = RELEASE_DIR / exe_path.name
        shutil.copy2(exe_path, dest)
        log(f"已复制到发布包: {dest}", "success")


def main():
    print("=" * 50)
    print("  ZPP011 偏差分析器 - 一键打包")
    print("=" * 50)
    print()

    version = get_version()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    full_name = f"{version}_{timestamp}"
    log(f"目标版本: {full_name}", "info")
    print()

    # Step 1: 备份旧版本
    log("[1/4] 备份旧版本...", "info")
    backup_old_exe()
    print()

    # Step 2: 同步 changelog.json 到项目目录
    log("[2/5] 同步 changelog...", "info")
    sync_changelog()
    print()

    # Step 3: 清理旧构建
    log("[3/5] 清理旧构建...", "info")
    clean_build()
    print()

    # Step 4: 打包
    log("[4/5] 执行打包...", "info")
    exe_path = build_exe(full_name)
    print()

    # Step 5: 复制到发布包
    log("[5/5] 复制到发布包...", "info")
    copy_to_release(exe_path)
    print()

    log(f"打包完成! {exe_path.name}", "success")
    print()
    log(f"输出路径: {exe_path}", "info")


if __name__ == "__main__":
    main()
