#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器 - PyInstaller 打包脚本
功能：
 - 自动备份源码
 - 版本号自动递增（基于 config/version.json）
 - 打包前检查 changelog 是否已添加当前版本记录
 - 更新窗口标题、关于窗口版本号（通过 version.json）
 - 打包后输出 exe
"""

import PyInstaller.__main__
import os
import sys
import shutil
import json
import datetime
import re

# ==================== 配置 ====================
APP_NAME = "ZPP011偏差分析器"
DEFAULT_VERSION = "v36.12"
VERSION_INCREMENT_RULE = "minor"  # 版本递增规则: major, minor, patch

# ==================== 辅助函数 ====================

def get_version_info():
    """读取 version.json，返回当前版本号、主次修订号"""
    version_file = os.path.join(os.path.dirname(__file__), 'config', 'version.json')
    if not os.path.exists(version_file):
        print(f"[WARN] {version_file} not found, using default {DEFAULT_VERSION}")
        return DEFAULT_VERSION, 36, 12, 0, DEFAULT_VERSION[1:]

    with open(version_file, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    ver_str = cfg.get('version', DEFAULT_VERSION)
    if ver_str.startswith('v'):
        ver_str = ver_str[1:]
    parts = ver_str.split('.')
    major = int(parts[0]) if len(parts) > 0 else 36
    minor = int(parts[1]) if len(parts) > 1 else 12
    patch = int(parts[2]) if len(parts) > 2 else 0
    return cfg, major, minor, patch, ver_str


def increment_version(major, minor, patch, rule='minor'):
    """版本号递增规则"""
    if rule == 'major':
        major += 1; minor = 0; patch = 0
    elif rule == 'minor':
        minor += 1; patch = 0
    elif rule == 'patch':
        patch += 1
    else:
        minor += 1
    return major, minor, patch


def check_changelog_updated(version):
    """检查 _CHANGELOG_EMBEDDED 中是否包含指定版本记录"""
    events_path = os.path.join(os.path.dirname(__file__), 'gui', 'events.py')
    if not os.path.exists(events_path):
        print("[WARN] gui/events.py not found, skipping changelog check")
        return True

    with open(events_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 匹配 "version": "vX.Y" 或 'version': 'vX.Y'
    pattern = rf'''["']version["']\s*:\s*["']v{version}["']'''
    if re.search(pattern, content):
        return True
    else:
        print(f"[ERROR] version {version} not found in _CHANGELOG_EMBEDDED of gui/events.py")
        print("   Please add current version record to _CHANGELOG_EMBEDDED['versions'] first.")
        return False


def update_version_file(version):
    """更新 config/version.json 中的版本号和打包时间"""
    version_file = os.path.join(os.path.dirname(__file__), 'config', 'version.json')
    if os.path.exists(version_file):
        with open(version_file, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    else:
        cfg = {}

    cfg['version'] = version
    cfg['last_build'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if 'version_schema' not in cfg:
        cfg['version_schema'] = 'major.minor.patch'
    if 'changelog_required' not in cfg:
        cfg['changelog_required'] = True

    config_dir = os.path.dirname(version_file)
    os.makedirs(config_dir, exist_ok=True)
    with open(version_file, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print(f"[OK] version updated to {version}")


def update_changelog_embedded(new_version):
    """递增版本后，自动往 _CHANGELOG_EMBEDDED 插入新版本的占位记录"""
    events_path = os.path.join(os.path.dirname(__file__), 'gui', 'events.py')
    if not os.path.exists(events_path):
        print("[WARN] gui/events.py not found, skipping changelog_embedded update")
        return

    with open(events_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 "versions": [ 的位置
    match = re.search(r'("versions"\s*:\s*\[)', content)
    if not match:
        print("[WARN] versions array not found in events.py")
        return

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_entry = f'''            {{
                "version": "{new_version}",
                "date": "{timestamp}",
                "changes": [
                    "🔧【修复】打包版本日志自动同步"
                ]
            }},'''

    # 在 versions: [ 后面插入新条目
    insert_pos = match.end()
    new_content = content[:insert_pos] + '\n' + new_entry + content[insert_pos:]

    with open(events_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"[OK] changelog_embedded updated with {new_version}")


def backup_source_code():
    """备份当前项目源码到用户目录下的 source_backups 文件夹"""
    try:
        backup_root = os.path.join(os.path.expanduser('~'), '.zpp011_audit', 'source_backups')
        os.makedirs(backup_root, exist_ok=True)

        _, major, minor, patch, _ = get_version_info()
        version = f"v{major}.{minor}.{patch}"

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{version}_{timestamp}"
        backup_path = os.path.join(backup_root, backup_name)

        items_to_backup = [
            'gui', 'analysis', 'storage', 'domain', 'utils', 'config',
            'widgets.py', 'main.py', 'build_exe.py', 'build.py', 'requirements.txt'
        ]

        for item in items_to_backup:
            src = os.path.join(os.path.dirname(__file__), item)
            if os.path.exists(src):
                dst = os.path.join(backup_path, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, ignore_dangling_symlinks=True,
                                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
                else:
                    shutil.copy2(src, dst)

        print(f"[OK] source backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"[WARN] backup failed (non-fatal): {e}")
        return None


def clean_build():
    """清理旧的构建文件"""
    dirs_to_remove = ['build', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            print(f"清理 {dir_name}/...")
            shutil.rmtree(dir_name)
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            print(f"删除 {f}")
            os.remove(f)


# ==================== 主函数 ====================

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    print("=" * 60)
    print("ZPP011 打包工具（含版本自动管理）")
    print("=" * 60)

    # 1. 清理构建缓存
    clean_build()

    # 2. 版本管理
    cfg, major, minor, patch, cur_ver_str = get_version_info()
    current_version = cur_ver_str  # 使用完整版本号（含patch）
    print(f"当前版本: {current_version}")

    # 检查 changelog 是否已更新
    if not check_changelog_updated(current_version):
        sys.exit(1)

    # 递增版本号
    new_major, new_minor, new_patch = increment_version(major, minor, patch, rule=VERSION_INCREMENT_RULE)
    new_version = f"v{new_major}.{new_minor}.{new_patch}"
    print(f"新版本: {new_version}")

    # 更新 version.json
    update_version_file(new_version)

    # 自动更新 _CHANGELOG_EMBEDDED，确保新版本有记录
    update_changelog_embedded(new_version)

    # 3. 备份源码（使用新版本号）
    backup_source_code()

    # 4. 打包配置
    # 生成带时间戳的输出文件名
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    OUTPUT_NAME = f"{APP_NAME}_{new_version}_{timestamp}"
    sep = os.pathsep

    args = [
        'main.py',
        '--name', OUTPUT_NAME,
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
    ]

    # 添加数据文件
    data_items = [
        'widgets.py',
        'gui', 'analysis', 'storage', 'domain', 'utils', 'config'
    ]
    for item in data_items:
        if os.path.exists(item):
            args.extend(['--add-data', f'{item}{sep}{item if os.path.isdir(item) else "."}'])

    # 隐藏导入
    hidden_imports = [
        'pandas', 'openpyxl', 'PIL', 'PIL.Image', 'PIL.ImageTk',
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
        'widgets', 'storage.storage', 'analysis.analyzer',
        'gui.app', 'gui.events', 'gui.inventory_view', 'gui.tree_utils', 'gui.ui_builder'
    ]
    for imp in hidden_imports:
        args.extend(['--hidden-import', imp])

    # 收集完整包
    collect_all = ['pandas', 'openpyxl', 'PIL']
    for pkg in collect_all:
        args.extend(['--collect-all', pkg])

    # 添加路径
    args.extend(['--paths', base_dir])

    print("\nPyInstaller 参数:")
    print(" ".join(args))
    print("\n" + "=" * 60)

    # 执行打包
    PyInstaller.__main__.run(args)

    print("\n" + "=" * 60)
    print("打包完成!")
    exe_path = os.path.join('dist', f'{OUTPUT_NAME}.exe')
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"输出文件: {exe_path}")
        print(f"文件大小: {size_mb:.1f} MB")
    else:
        print("✗ 未找到输出文件")
    print("=" * 60)


if __name__ == "__main__":
    main()
