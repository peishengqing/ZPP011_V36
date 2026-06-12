#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""删除 main_window.py 中已迁移到 ExportController 的方法"""

import re

file_path = r'E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 要删除的方法列表（按出现在文件中的顺序）
methods_to_remove = [
    '_export_current_table',
    '_export_full_excel',
    '_export_full_analysis_excel',
    '_generate_simple_ppt',
    '_generate_advanced_report',
]

# 删除每个方法
modified = False
for method_name in methods_to_remove:
    # 匹配方法定义及其内容（直到下一个 def 或类结束）
    pattern = rf'    def {method_name}\(self.*?(?=\n    def |\nclass )'
    new_content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    if new_content != content:
        content = new_content
        modified = True
        print(f'✅ 已删除方法: {method_name}')
    else:
        print(f'⚠️  未找到方法: {method_name}')

if modified:
    # 创建备份
    backup_path = file_path + '.backup3'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(open(file_path, 'r', encoding='utf-8').read())
    print(f'✅ 已创建备份: {backup_path}')
    
    # 写入新内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'✅ 成功删除 {len(methods_to_remove)} 个已迁移的方法！')
else:
    print('❌ 没有删除任何方法')
