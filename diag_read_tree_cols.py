#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接读文件，找 audit_tree 列定义和 insert values 数量"""
import sys, os, io, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.chdir(r'E:\zpp011_dev\模块化脚本')

print("=== 找 audit_tree 列定义 ===")
with open('gui/event_handlers/table_events.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找列定义
for i, line in enumerate(lines):
    if 'audit_tree' in line and ('columns' in line or '["columns"]' in line or "['columns']" in line):
        print(f"L{i+1}: {line.rstrip()}")
        # print next few lines
        for j in range(i+1, min(i+10, len(lines))):
            print(f"L{j+1}: {lines[j].rstrip()}")
        print("---")

print("\n=== 找 insert values 参数（数逗号）===")
in_insert = False
paren_depth = 0
for i, line in enumerate(lines):
    if 'audit_tree.insert(' in line:
        print(f"\nL{i+1}: {line.rstrip()}")
        # 从这一行开始，找 values=(...) 并数逗号
        in_insert = True
        paren_depth = 0
        val_lines = []
        started = False
        for j in range(i, min(i+80, len(lines))):
            cline = lines[j]
            val_lines.append(cline)
            if not started:
                vi = cline.find('values=(')
                if vi >= 0:
                    started = True
                    paren_depth = 1
                    # 从 vi+8 开始数
                    rest = cline[vi+8:]
                    for ch in rest:
                        if ch == '(': paren_depth += 1
                        elif ch == ')': paren_depth -= 1
                    continue
            if started:
                for ch in cline:
                    if ch == '(': paren_depth += 1
                    elif ch == ')':
                        paren_depth -= 1
                        if paren_depth == 0:
                            break
                if paren_depth == 0:
                    break
        # 现在 val_lines 里有完整的 values 元组
        val_str = ''.join(val_lines)
        vi2 = val_str.find('values=(')
        if vi2 >= 0:
            # 提取元组内容
            paren = 1
            content = []
            k = vi2 + 8
            while k < len(val_str) and paren > 0:
                ch = val_str[k]
                if ch == '(': paren += 1
                elif ch == ')': paren -= 1
                if paren > 0:
                    content.append(ch)
                k += 1
            content_str = ''.join(content)
            # 数顶层逗号
            p2 = 0
            commas = 0
            for ch in content_str:
                if ch == '(': p2 += 1
                elif ch == ')': p2 -= 1
                elif ch == ',' and p2 == 0: commas += 1
            print(f"  values 元素数: {commas + 1}")
            print(f"  values 内容:\n{content_str[:600]}")
        break  # 只看第一个 insert

print("\n=== 找 _refresh_audit_tree 中 tree 列数 vs values 数 ===")
# 找 _refresh_audit_tree 方法
for i, line in enumerate(lines):
    if 'def _refresh_audit_tree' in line:
        print(f"方法从 L{i+1} 开始")
        # 找 return 或下一个 def
        for j in range(i, min(i+500, len(lines))):
            if j > i and lines[j].strip().startswith('def '):
                break
            # 打印 insert 行
            if 'audit_tree.insert(' in lines[j]:
                print(f"  L{j+1}: {lines[j].rstrip()[:120]}")
        break

input("\n按回车退出...")
