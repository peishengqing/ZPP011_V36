#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""详细调试 changelog.json JSON 错误"""

import json
import sys

file_path = r'E:\zpp011_dev\模块化脚本\changelog.json'

# 读取文件内容
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 尝试解析，捕获详细错误
try:
    data = json.loads(content)
    print("[OK] JSON 解析成功 ✅")
    print(f"[INFO] 版本数量: {len(data.get('versions', []))}")
except json.JSONDecodeError as e:
    print(f"[ERROR] JSON 解析失败:")
    print(f"  错误信息: {e.msg}")
    print(f"  错误位置: 第 {e.lineno} 行，第 {e.colno} 列")
    print(f"  字符位置: {e.pos}")
    
    # 提取错误位置附近的文本（前后各 50 个字符）
    start = max(0, e.pos - 50)
    end = min(len(content), e.pos + 50)
    context = content[start:end]
    
    print(f"\n[DEBUG] 错误位置附近的文本:")
    print(f"  ...{repr(context)}...")
    
    # 显示错误行的内容
    lines = content.split('\n')
    if e.lineno <= len(lines):
        error_line = lines[e.lineno - 1]  # 1-indexed
        print(f"\n[DEBUG] 错误行内容 (第 {e.lineno} 行):")
        print(f"  {repr(error_line)}")
        print(f"  错误位置标记为: {' ' * (e.colno - 1)}^")
    
    # 尝试自动修复常见问题
    print(f"\n[INFO] 尝试自动修复...")
    
    # 常见修复：删除多余的 , 或 }
    # 这里需要根据具体情况手动修复
    print(f"[WARN] 无法自动修复，请手动检查")
    sys.exit(1)
