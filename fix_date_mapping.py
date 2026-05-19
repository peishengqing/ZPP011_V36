# -*- coding: utf-8 -*-
import os

fp = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 "生成唯一ID" 并在前面插入日期映射
for i, line in enumerate(lines):
    if '# 生成唯一ID' in line or "audit_df['_uid'] = (" in line:
        # 在这行前面插入日期映射
        new_lines = [
            '        # 日期列映射\n',
            "        if '订单开始日期' in audit_df.columns and '订单日期' not in audit_df.columns:\n",
            "            audit_df['订单日期'] = audit_df['订单开始日期'].astype(str).str[:10]\n",
            "        elif '订单日期' not in audit_df.columns:\n",
            "            audit_df['订单日期'] = ''\n",
            '\n'
        ]
        lines = lines[:i] + new_lines + lines[i:]
        print(f'Inserted at line {i+1}')
        break

with open(fp, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
