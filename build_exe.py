#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器 - PyInstaller 打包脚本
支持 matplotlib PPT 导出，自动备份源码
"""

import PyInstaller.__main__
import os
import sys
import shutil
import datetime

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
    """清理旧的构建文件（保留 dist 目录）"""
    if os.path.exists('build'):
        shutil.rmtree('build')
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            os.remove(f)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    
    print("=" * 60)
    print(f"开始打包: {OUTPUT_NAME}")
    print("=" * 60)
    
    clean_build()
    
    sep = os.pathsep
    args = [
        'main.py',
        '--name', OUTPUT_NAME,
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
    ]
    
    # 添加图标文件
    for icon in ['ZPP011偏差分析器.ico', 'ZPP011偏差分析器.icon.png']:
        if os.path.exists(icon):
            args.extend(['--add-data', f'{icon}{sep}.'])
    
    # 添加数据目录
    data_dirs = ['config', 'temp', 'logs']
    for dirname in data_dirs:
        os.makedirs(dirname, exist_ok=True)
        args.extend(['--add-data', f'{dirname}{sep}{dirname}'])
    
    # matplotlib 数据目录（重要）
    try:
        import matplotlib as mpl
        mpl_data = os.path.join(os.path.dirname(mpl.__file__), 'mpl-data')
        if os.path.exists(mpl_data):
            args.extend(['--add-data', f'{mpl_data}{sep}mpl-data'])
            print("[INFO] 已添加 matplotlib 数据目录")
    except ImportError:
        print("[WARN] 未找到 matplotlib，PPT 导出可能失败")
    
    # 隐藏导入（完整列表）
    hidden_imports = [
        'pandas', 'pandas.core', 'pandas.core.algorithms', 'pandas.core.arrays',
        'openpyxl', 'openpyxl.styles',
        'PIL', 'PIL.Image', 'PIL.ImageTk',
        'matplotlib', 'matplotlib.backends', 'matplotlib.backends.backend_agg',
        'matplotlib.pyplot',
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
        'ctypes', 'json', 'csv', 'calendar', 'shutil', 'traceback', 'threading',
        'datetime', 'time', 'glob',
        'widgets', 'storage', 'storage.storage',
        'analysis', 'analysis.analyzer',
        'gui', 'gui.app', 'gui.events', 'gui.inventory_view', 'gui.tree_utils', 'gui.ui_builder',
        'core', 'core.decorators', 'core.state_store', 'core.config_manager',
        'core.task_manager', 'core.rule_engine', 'core.exporter', 'core.logger',
        'utils', 'utils.version_history',
    ]
    for imp in hidden_imports:
        args.extend(['--hidden-import', imp])
    
    # 收集完整包
    collect_packages = ['pandas', 'openpyxl', 'PIL', 'matplotlib']
    for pkg in collect_packages:
        args.extend(['--collect-all', pkg])
    
    # 添加路径
    args.extend(['--paths', base_dir])
    
    print("\nPyInstaller 参数数量:", len(args))
    # 可选：打印参数（调试用）
    # print(" ".join(args))
    
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
        print("错误: 未找到输出文件")
    print("=" * 60)

if __name__ == "__main__":
    main()