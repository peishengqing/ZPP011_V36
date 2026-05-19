# -*- coding: utf-8 -*-
"""修复 gui/events.py 乱码"""
import os

fp = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复乱码
old = 'messagebox.showwarning("已���消", str(error))'
new = 'messagebox.showwarning("已取消", str(error))'

if old in content:
    content = content.replace(old, new)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: Fixed garbage characters')
else:
    print('SKIP: Pattern not found')
    # 尝试查找并显示上下文
    if '已' in content and '消' in content:
        idx = content.find('已')
        print(f'Found 已 at {idx}, context: {repr(content[idx:idx+20])}')
