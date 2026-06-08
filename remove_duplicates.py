#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除 main_window.py 中重复的方法，只保留一份"""

import re

def remove_duplicates():
    fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"
    
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"原始文件长度: {len(content)}")
    
    # 要检查的方法列表
    methods = [
        '_update_summary',
        '_update_stat_cards',
        '_on_selection_changed',
        '_cancel_analysis',
        '_batch_mark_selected_read',
        '_copy_previous_remark',
        '_on_alert'
    ]
    
    # 对每个方法，如果出现多次，只保留第一次出现的
    for method in methods:
        pattern = f'    def {method}\('
        count = content.count(pattern)
        if count > 1:
            print(f"方法 {method} 出现 {count} 次，删除重复的...")
            
            # 找到所有出现的位置
            positions = [m.start() for m in re.finditer(re.escape(pattern), content)]
            
            # 从后往前删除（避免位置偏移）
            for pos in sorted(positions[1:], reverse=True):
                # 找到该方法结束的位置（下一个 def 或文件结束）
                next_def = content.find('\n    def ', pos + len(pattern))
                if next_def == -1:
                    next_def = len(content)
                
                # 删除该方法
                content = content[:pos] + content[next_def:]
            
            print(f"  已删除 {count-1} 个重复")
    
    # 保存
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"保存后文件长度: {len(content)}")
    
    # 验证语法
    import py_compile
    try:
        py_compile.compile(fp, doraise=True)
        print("语法验证通过")
        return True
    except py_compile.PyCompileError as e:
        print(f"语法错误: {e}")
        return False

if __name__ == '__main__':
    ok = remove_duplicates()
    print("\n=== 修复完成 ===" if ok else "\n=== 修复失败 ===")
