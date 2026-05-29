#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查找 audit_tree 定义和相关方法的脚本"""

import re

# 读取文件
with open('gui/event_handlers/table_events.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

print("=" * 60)
print("搜索 audit_tree 定义:")
print("=" * 60)

# 查找 audit_tree 的初始化
for i, line in enumerate(lines, 1):
    if 'audit_tree' in line and ('=' in line or 'self.audit_tree' in line):
        # 打印上下文
        start = max(0, i - 3)
        end = min(len(lines), i + 3)
        print(f"\n第 {i} 行附近:")
        for j in range(start, end):
            marker = ">>>" if j == i - 1 else "   "
            print(f"{marker} {j+1}: {lines[j]}")
        if i > 50:
            break

print("\n" + "=" * 60)
print("搜索 _on_filter_changed 方法:")
print("=" * 60)

for i, line in enumerate(lines, 1):
    if '_on_filter_changed' in line and 'def ' in line:
        print(f"\n找到方法定义在第 {i} 行:")
        # 打印整个方法（最多50行）
        for j in range(i - 1, min(i + 50, len(lines))):
            print(f"{j+1}: {lines[j]}")
            if j > i and lines[j].strip() and not lines[j].startswith('    '):
                break
        break

print("\n" + "=" * 60)
print("搜索 __init__ 方法:")
print("=" * 60)

for i, line in enumerate(lines, 1):
    if 'def __init__' in line:
        print(f"\n找到 __init__ 在第 {i} 行:")
        # 打印前80行
        for j in range(i - 1, min(i + 80, len(lines))):
            print(f"{j+1}: {lines[j]}")
        break
