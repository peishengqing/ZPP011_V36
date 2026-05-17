#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器 - PyInstaller 打包脚本
支持 matplotlib 图表导出功能
"""

import PyInstaller.__main__
import os
import sys
import shutil

# 应用信息
APP_NAME = "ZPP011偏差分析器"
# 版本号从 utils/version_history.py 动态读取
import sys as _sys
from pathlib import Path
_sys.path.insert(0, str(Path(__file__).parent))
try:
    from utils.version_history import get_current_version
    VERSION = get_current_version()
except ImportError:
    VERSION = "v0.0.0"
OUTPUT_NAME = f"{APP_NAME}_{VERSION}"

def clean_build():
    """清理之前的构建文件（保留 dist 目录，只清 build 和 spec）"""
    if os.path.exists('build'):
        print("清理 build/...")
        shutil.rmtree('build')
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            print(f"删除 {f}")
            os.remove(f)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    
    print("=" * 60)
    print(f"开始打包: {OUTPUT_NAME}")
    print("=" * 60)
    
    # 清理旧构建
    clean_build()
    
    sep = os.pathsep  # Windows: ';'
    
    # PyInstaller 参数
    args = [
        'main.py',                          # 入口文件
        '--name', OUTPUT_NAME,              # 输出文件名
        '--onefile',                        # 单 exe 文件
        '--windowed',                       # 无控制台窗口
        '--clean',
        '--noconfirm',
    ]
    
    # 添加图标文件（如果存在）
    icon_files = ['ZPP011偏差分析器.ico', 'ZPP011偏差分析器.icon.png']
    for icon in icon_files:
        if os.path.exists(icon):
            args.extend(['--add-data', f'{icon}{sep}.'])
            print(f"包含图标: {icon}")
    
    # 添加 config 目录（存放配置文件）
    if os.path.exists('config'):
        args.extend(['--add-data', f'config{sep}config'])
        print("包含 config/ 目录")
    
    # 添加 temp 目录（用于临时文件）
    if os.path.exists('temp'):
        args.extend(['--add-data', f'temp{sep}temp'])
        print("包含 temp/ 目录")
    
    # 添加日志目录（空目录也加上）
    if not os.path.exists('logs'):
        os.makedirs('logs', exist_ok=True)
    args.extend(['--add-data', f'logs{sep}logs'])
    
    # 隐藏导入（核心依赖）
    hidden_imports = [
        'pandas',
        'pandas.core',
        'pandas.core.algorithms',
        'pandas.core.arrays',
        'openpyxl',
        'openpyxl.styles',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'matplotlib',                       # 新增：支持 PPT 图表
        'matplotlib.backends',
        'matplotlib.backends.backend_agg',
        'matplotlib.pyplot',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'ctypes',
        'json',
        'csv',
        'calendar',
        'shutil',
        'traceback',
        'threading',
        'datetime',
        'time',
        'glob',
        'widgets',
        'storage',
        'storage.storage',
        'analysis',
        'analysis.analyzer',
        'analysis.sheets',
        'analysis.sheets.sheet5_full',
        'gui',
        'gui.app',
        'gui.events',
        'gui.inventory_view',
        'gui.tree_utils',
        'gui.ui_builder',
        'core',
        'core.decorators',
        'core.state_store',
        'core.config_manager',
        'core.task_manager',
        'core.rule_engine',
        'core.exporter',
        'core.logger',
        'utils',
        'utils.version_history',
    ]
    
    for imp in hidden_imports:
        args.extend(['--hidden-import', imp])
    
    # 收集完整包（确保子模块被包含）
    collect_packages = ['pandas', 'openpyxl', 'PIL', 'matplotlib']
    for pkg in collect_packages:
        args.extend(['--collect-all', pkg])
    
    # 添加项目根目录到路径
    args.extend(['--paths', '.'])
    
    print("\nPyInstaller 参数数量:", len(args))
    # 可选：打印完整参数（注释掉以免刷屏）
    # print(" ".join(args))
    print("\n开始打包...")
    
    PyInstaller.__main__.run(args)
    
    print("\n" + "=" * 60)
    print("打包完成!")
    exe_path = os.path.join('dist', f'{OUTPUT_NAME}.exe')
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"输出文件: {exe_path}")
        print(f"文件大小: {size_mb:.1f} MB")
    else:
        print(f"错误: 未找到输出文件 {exe_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()