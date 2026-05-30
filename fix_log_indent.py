#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 gui/app.py 中 log 方法的缩进问题
"""
import re

def fix_log_indent():
    app_py = r'E:\zpp011_dev\模块化脚本\gui\app.py'
    
    print("[INFO] 读取 gui/app.py...")
    with open(app_py, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"[INFO] 文件共 {len(lines)} 行")
    
    # 找到 log 方法的位置
    in_log_method = False
    log_start = -1
    log_end = -1
    
    for i, line in enumerate(lines):
        if 'def log(self, msg, tag="info"):' in line:
            in_log_method = True
            log_start = i
            print(f"[INFO] 找到 log 方法，起始行: {i+1}")
            continue
        
        if in_log_method:
            # 如果遇到下一个方法或类定义，log 方法结束
            if line.strip().startswith('def ') or line.strip().startswith('class '):
                log_end = i
                break
            # 如果遇到空行后有顶格代码，也认为是结束
            if line.strip() == '' and i+1 < len(lines) and not lines[i+1].startswith('    '):
                log_end = i
                break
    
    if log_start == -1:
        print("[ERROR] 未找到 log 方法")
        return
    
    if log_end == -1:
        log_end = len(lines)
    
    print(f"[INFO] log 方法范围: 行{log_start+1} 到 行{log_end}")
    
    # 修复 log 方法内的缩进
    # 方法定义应该是 4 个空格
    # 方法体应该是 8 个空格
    for i in range(log_start, log_end):
        line = lines[i]
        if line.strip() == '':
            continue
        
        # 方法定义行
        if 'def log(self, msg, tag="info"):' in line:
            # 确保方法定义是 4 个空格
            lines[i] = '    ' + line.strip() + '\n'
            print(f"[FIX] 修复方法定义缩进: 行 {i+1}")
            continue
        
        # 方法体内的行应该是 8 个空格
        if not line.startswith('        '):
            # 移除原有缩进，添加正确的 8 个空格
            lines[i] = '        ' + line.strip() + '\n'
            print(f"[FIX] 修复方法体缩进: 行 {i+1}")
    
    # 保存修复后的文件
    backup_path = app_py + '.bak_final'
    print(f"[INFO] 创建备份: {backup_path}")
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"[INFO] 保存修复后的文件...")
    with open(app_py, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("[OK] 修复完成！")
    print(f"[INFO] 请运行: python -m tabnanny \"{app_py}\"")

if __name__ == '__main__':
    fix_log_indent()
