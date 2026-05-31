#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复 changelog.json 中的所有 JSON 格式问题
"""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

changelog_path = r'E:\zpp011_dev\模块化脚本\changelog.json'

with open(changelog_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复所有未转义的中文引号
replacements = [
    ('"合格/需改进/AI 建议/未处理"', '合格/需改进/AI 建议/未处理'),
    ('"已审核"', '已审核'),
    ('"已备注"', '已备注'),
    ('"需补备注"', '需补备注'),
]

for old, new in replacements:
    content = content.replace(old, new)

with open(changelog_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ 已修复引号')

# 验证
try:
    with open(changelog_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f'✓ JSON 格式有效，共 {len(data.get("versions", []))} 个版本')
except Exception as e:
    print(f'✗ 仍有错误：{e}')
    # 显示错误位置附近的内容
    import re
    match = re.search(r'line (\d+)', str(e))
    if match:
        line_num = int(match.group(1))
        lines = content.split('\n')
        print(f'\n错误在 Line {line_num} 附近:')
        for i in range(max(0, line_num-3), min(len(lines), line_num+2)):
            marker = '>>>' if i+1 == line_num else '   '
            print(f'{marker} {i+1}: {lines[i][:80]}')
