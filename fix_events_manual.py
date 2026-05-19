# -*- coding: utf-8 -*-
import os

fp = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到位置并插入列名清理
for i, line in enumerate(lines):
    if 'raise ValueError("偏差明细工作表为空")' in line:
        new_lines = [
            '        # 列名清理（去除空格）\n',
            "        dev_df.columns = [str(c).strip().replace(' ', '') for c in dev_df.columns]\n",
            '\n'
        ]
        lines = lines[:i+1] + new_lines + lines[i+1:]
        print(f'Inserted at line {i+2}')
        break

with open(fp, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
