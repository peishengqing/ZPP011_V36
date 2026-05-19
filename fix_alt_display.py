# -*- coding: utf-8 -*-
"""修复替代料配对列表显示：改为 编码+名称 格式"""
import os

fp = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''            # 解析物料A：支持三元组 (factory, code, name)
            if isinstance(a, (list, tuple)) and len(a) == 3:
                _, a_code, a_name = a
            elif isinstance(a, (list, tuple)) and len(a) == 2:
                a_code, a_name = a
            else:
                a_code, a_name = str(a), ''
            # 解析物料B
            if isinstance(b, (list, tuple)) and len(b) == 3:
                _, b_code, b_name = b
            elif isinstance(b, (list, tuple)) and len(b) == 2:
                b_code, b_name = b
            else:
                b_code, b_name = str(b), ''
            # 显示：编码 + 名称（若名称存在）
            a_disp = f"{a_code} {a_name}" if a_name else a_code
            b_disp = f"{b_code} {b_name}" if b_name else b_code'''

new_code = '''            # 解析物料A：支持三元组 (factory, code, name)
            if isinstance(a, (list, tuple)) and len(a) == 3:
                _, a_code, a_name = a
            elif isinstance(a, (list, tuple)) and len(a) == 2:
                a_code, a_name = a
            else:
                a_code, a_name = '', str(a)
            # 解析物料B
            if isinstance(b, (list, tuple)) and len(b) == 3:
                _, b_code, b_name = b
            elif isinstance(b, (list, tuple)) and len(b) == 2:
                b_code, b_name = b
            else:
                b_code, b_name = '', str(b)
            # 清理 None 值
            a_code = '' if a_code is None or str(a_code) in ('None', 'nan') else str(a_code).strip()
            a_name = '' if a_name is None or str(a_name) in ('None', 'nan') else str(a_name).strip()
            b_code = '' if b_code is None or str(b_code) in ('None', 'nan') else str(b_code).strip()
            b_name = '' if b_name is None or str(b_name) in ('None', 'nan') else str(b_name).strip()
            # 显示：编码 + 名称（优先显示编码+名称，编码为空则只显示名称）
            if a_code and a_name:
                a_disp = f"{a_code} {a_name}"
            elif a_code:
                a_disp = a_code
            else:
                a_disp = a_name
            if b_code and b_name:
                b_disp = f"{b_code} {b_name}"
            elif b_code:
                b_disp = b_code
            else:
                b_disp = b_name'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: Fixed alt display in events.py')
else:
    print('SKIP: Pattern not found')
