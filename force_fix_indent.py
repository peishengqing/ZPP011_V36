#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制修复 gui/app.py 的缩进问题
使用最彻底的方法：逐行检查并强制统一为4空格缩进
"""
import re
import subprocess
import os

def force_fix_indent():
    app_py = r'E:\zpp011_dev\模块化脚本\gui\app.py'
    
    print("[INFO] 读取文件...")
    with open(app_py, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"[INFO] 文件共 {len(lines)} 行")
    
    # 方法1：使用 autopep8 的激进模式
    print("\n[STEP 1] 尝试 autopep8 --aggressive --aggressive...")
    try:
        result = subprocess.run(
            ['python', '-m', 'autopep8', '--in-place', '--aggressive', '--aggressive', app_py],
            capture_output=True,
            text=True,
            check=True
        )
        print("[OK] autopep8 执行完成")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] autopep8 失败: {e}")
    
    # 方法2：检查是否有制表符
    print("\n[STEP 2] 检查制表符...")
    tab_count = 0
    for i, line in enumerate(lines):
        if '\t' in line:
            tab_count += 1
            lines[i] = line.replace('\t', '    ')  # 制表符转4空格
            print(f"  [FIX] 行 {i+1}: 制表符 -> 空格")
    
    if tab_count > 0:
        print(f"[INFO] 共修复 {tab_count} 个制表符")
    else:
        print("[INFO] 未发现制表符")
    
    # 方法3：强制修复 log 方法的缩进
    print("\n[STEP 3] 强制修复 log 方法缩进...")
    in_log_method = False
    log_start = -1
    log_end = -1
    
    for i, line in enumerate(lines):
        if 'def log(self, msg, tag="info"):' in line:
            in_log_method = True
            log_start = i
            # 强制方法定义为4空格
            lines[i] = '    ' + line.strip() + '\n'
            print(f"  [FIX] 行 {i+1}: 强制4空格缩进")
            continue
        
        if in_log_method:
            # 如果遇到下一个方法或类定义，log 方法结束
            if line.strip().startswith('def ') or line.strip().startswith('class '):
                log_end = i
                break
            
            # 方法体内的行强制8空格
            if line.strip():
                lines[i] = '        ' + line.strip() + '\n'
                print(f"  [FIX] 行 {i+1}: 强制8空格缩进")
    
    if log_end == -1 and in_log_method:
        log_end = len(lines)
    
    print(f"[INFO] log 方法范围: 行{log_start+1} 到 行{log_end}")
    
    # 保存修复后的文件
    backup_path = app_py + '.bak_force'
    print(f"\n[INFO] 创建备份: {backup_path}")
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"[INFO] 保存修复后的文件...")
    with open(app_py, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    # 验证
    print("\n[STEP 4] 验证修复结果...")
    result = subprocess.run(
        ['python', '-m', 'tabnanny', app_py],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("[OK] tabnanny 验证通过！")
        print("\n[SUCCESS] 所有缩进问题已修复！")
        print(f"[INFO] 请运行: python \"{app_py}\"")
    else:
        print(f"[ERROR] tabnanny 仍有错误:")
        print(result.stderr)
        print("\n[INFO] 可能需要手动检查第1507行附近的代码")

if __name__ == '__main__':
    force_fix_indent()
