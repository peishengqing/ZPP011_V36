#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 gui/app.py 第322-324行缩进错误
问题：
1. 第322行 'from core.view_manager import ViewManager  # Task 012' 缩进错误（在 __init__ 方法内部）
2. 第324行 'self.audit_logger = AuditLogger()' 可能与上一行缩进不一致
修复：将导入语句移到文件顶部，修复缩进
"""
import os
import re

def fix_indentation():
    app_path = r'E:\zpp011_dev\模块化脚本\gui\app.py'
    
    print("[INFO] 读取 gui/app.py...")
    with open(app_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"[INFO] 共 {len(lines)} 行")
    
    # 1. 找到错误缩进的导入行（第322行附近）
    target_line_idx = None
    for i, line in enumerate(lines):
        if 'from core.view_manager import ViewManager' in line:
            # 检查是否在 __init__ 内部（有缩进）
            if line.startswith('        '):  # 8个空格，在方法内部
                target_line_idx = i
                print(f"[INFO] 发现错误位置的导入，行 {i+1}: {line.rstrip()}")
                break
    
    if target_line_idx is not None:
        # 从 __init__ 方法中删除这行
        del lines[target_line_idx]
        print(f"[FIX] 已删除错误位置的导入语句")
    
    # 2. 在文件顶部添加导入（如果还没有）
    # 找到最后一个 'from core.xxx import' 或 'import xxx' 的位置
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('from core.') or line.startswith('import '):
            last_import_idx = i
    
    # 检查顶部是否已有这个导入
    has_import = False
    for line in lines[:50]:  # 检查前50行
        if 'from core.view_manager import ViewManager' in line and not line.strip().startswith('#'):
            has_import = True
            print(f"[INFO] 顶部已有导入语句")
            break
    
    if not has_import:
        # 在最后一个导入后插入
        insert_idx = last_import_idx + 1
        lines.insert(insert_idx, 'from core.view_manager import ViewManager  # Task 012\n')
        print(f"[FIX] 在行 {insert_idx+1} 添加导入语句")
    
    # 3. 修复 __init__ 方法内的缩进（确保 self.audit_logger 等正确缩进）
    in_init = False
    init_indent = '        '  # 8个空格
    
    for i, line in enumerate(lines):
        if 'def __init__(self' in line:
            in_init = True
            continue
        
        if in_init:
            # 如果遇到下一个方法定义，退出 __init__
            if line.strip().startswith('def ') and not line.strip().startswith('def __init__'):
                in_init = False
                continue
            
            # 修复以 self. 开头的行的缩进
            if line.strip().startswith('self.'):
                # 移除原有缩进，添加正确的8空格缩进
                lines[i] = init_indent + line.strip() + '\n'
    
    # 4. 保存修复后的文件
    backup_path = app_path + '.bak3'
    print(f"[INFO] 创建备份: {backup_path}")
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"[INFO] 保存修复后的文件...")
    with open(app_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("[OK] 缩进修复完成！")
    print(f"[INFO] 请运行: python \"{app_path}\" 验证")

if __name__ == '__main__':
    fix_indentation()
