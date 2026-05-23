#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复 changelog.json 第 514 行语法错误（多余的 },）"""

# 读取文件
with open(r'E:\zpp011_dev\模块化脚本\changelog.json', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到第 514 行（1-indexed → 0-indexed: 513）
line_num = 513  # 0-indexed
problem_line = lines[line_num].strip()
print(f"[DEBUG] Line 514 (0-indexed 513): '{problem_line}'")

# 检查是否是多余的 },
if problem_line == '},':
    print("[INFO] 发现多余的 }, 正在删除...")
    del lines[line_num]
    print("[OK] 已删除多余的 },")
else:
    print(f"[WARN] 第 514 行内容不是 '}},', 而是 '{problem_line}'")
    print("[WARN] 请手动检查文件")

# 写回文件
with open(r'E:\zpp011_dev\模块化脚本\changelog.json', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("[INFO] 文件已保存，正在验证 JSON 格式...")

# 验证 JSON
import json
try:
    with open(r'E:\zpp011_dev\模块化脚本\changelog.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    print("[OK] JSON 格式验证通过 ✅")
    print(f"[INFO] 版本数量: {len(data.get('versions', []))}")
except Exception as e:
    print(f"[ERROR] JSON 格式验证失败: {e}")
    print("[INFO] 请手动修复")
