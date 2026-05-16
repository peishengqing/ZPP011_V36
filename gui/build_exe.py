#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器 - PyInstaller 打包脚本
解决 exe 无法启动的常见问题
"""

import PyInstaller.__main__
import os
import sys
import shutil

# 应用信息
APP_NAME = "ZPP011偏差分析器"
VERSION = "v36.12"
OUTPUT_NAME = f"{APP_NAME}_{VERSION}"

def clean_build():
    """清理之前的构建文件"""
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            print(f"清理 {dir_name}/...")
            shutil.rmtree(dir_name)
    
    # 清理 .spec 文件
    for f in os.listdir('.'):
        if f.endswith('.spec'):
            print(f"删除 {f}")
            os.remove(f)

def get_all_py_files():
    """获取所有 Python 文件，确保都被包含"""
    py_files = []
    for root, dirs, files in os.walk('.'):
        # 跳过虚拟环境和构建目录
        dirs[:] = [d for d in dirs if d not in ['venv', 'env', '.venv', 'build', 'dist', '__pycache__', '.git']]
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                py_files.append(full_path)
    return py_files

def main():
    # 获取当前目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    
    print("=" * 60)
    print(f"开始打包: {OUTPUT_NAME}")
    print("=" * 60)
    
    # 清理旧构建
    clean_build()
    
    # 检测操作系统路径分隔符
    sep = os.pathsep  # Windows: ';', Linux/Mac: ':'
    
    # 构建 PyInstaller 参数
    args = [
        'main.py',                          # 入口文件
        '--name', OUTPUT_NAME,              # 输出文件名
        '--onefile',                        # 打包成单个 exe
        '--windowed',                       # 不显示控制台窗口
        '--clean',                          # 清理临时文件
        '--noconfirm',                      # 不确认覆盖
    ]
    
    # 添加数据文件（图标）
    icon_files = [
        'ZPP011偏差分析器.ico',
        'ZPP011偏差分析器.icon.png',
    ]
    for icon in icon_files:
        if os.path.exists(icon):
            args.extend(['--add-data', f'{icon}{sep}.'])
            print(f"包含图标: {icon}")
        else:
            print(f"警告: 图标文件不存在: {icon}")
    
    # 添加所有 Python 文件作为数据（确保模块能被找到）
    py_files = get_all_py_files()
    for py_file in py_files:
        # 跳过 main.py（已作为入口）和构建脚本
        if py_file not in ['main.py', 'build_exe.py', 'build.py']:
            # 计算相对路径
            rel_dir = os.path.dirname(py_file)
            if rel_dir == '':
                rel_dir = '.'
            args.extend(['--add-data', f'{py_file}{sep}{rel_dir}'])
    
    # 关键：添加所有子目录作为路径
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ['venv', 'env', '.venv', 'build', 'dist', '__pycache__', '.git']]
        if root != '.':
            rel_path = root.lstrip('.\\/')
            args.extend(['--paths', rel_path])
    
    # 添加隐藏导入（关键模块）
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
        # 项目内部模块
        'widgets',
        'storage',
        'storage.storage',
        'analysis',
        'analysis.analyzer',
        'gui',
        'gui.app',
        'gui.events',
        'gui.inventory_view',
        'gui.tree_utils',
        'gui.ui_builder',
    ]
    
    for imp in hidden_imports:
        args.extend(['--hidden-import', imp])
    
    # 收集完整的包
    collect_all = ['pandas', 'openpyxl', 'PIL']
    for pkg in collect_all:
        args.extend(['--collect-all', pkg])
    
    # 添加当前目录到路径
    args.extend(['--paths', '.'])
    
    print("\nPyInstaller 参数:")
    print(" ".join(args))
    print("\n" + "=" * 60)
    
    # 运行 PyInstaller
    PyInstaller.__main__.run(args)
    
    print("\n" + "=" * 60)
    print("打包完成!")
    print(f"输出文件: dist/{OUTPUT_NAME}.exe")
    print("=" * 60)
    
    # 检查输出文件
    exe_path = os.path.join('dist', f'{OUTPUT_NAME}.exe')
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"✓ 文件大小: {size_mb:.1f} MB")
    else:
        print("✗ 未找到输出文件")

if __name__ == "__main__":
    main()
