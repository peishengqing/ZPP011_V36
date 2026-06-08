#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全局替换 self.audit_data 为 self.view_model.df"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py"

with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 统计替换次数
original_count = content.count('self.audit_data')
print(f"找到 {original_count} 处 'self.audit_data'")

# 替换
content = content.replace('self.audit_data', 'self.view_model.df')

new_count = content.count('self.audit_data')
print(f"替换后剩余 {new_count} 处 'self.audit_data'")
print(f"实际替换 {original_count - new_count} 处")

# 写入文件
with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✓ 替换完成！")

# 验证：搜索是否还有 self.audit_data
if new_count > 0:
    print("\n警告：以下行仍包含 'self.audit_data'：")
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'self.audit_data' in line:
            print(f"  Line {i+1}: {line.strip()}")
