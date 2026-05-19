# -*- coding: utf-8 -*-
"""修复 name_cols 匹配顺序 - 优先匹配'组件物料描述'"""
import os

fp = r'E:\zpp011_dev\模块化脚本\gui\app.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复: 先精确匹配'组件物料描述'，再匹配其他
old_code = '''                code_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['组件物料号', '组件编码', '物料编码', 'code', '编码'])]
                name_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['组件描述', '物料描述', '组件物料描述', '名称', 'name', '描述', '物料名称'])]
                factory_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['工厂名称', '工厂', 'factory'])]'''

new_code = '''                # 优先精确匹配，避免匹配到错误的列
                code_cols = [c for c in df.columns if '组件物料号' in str(c)]
                if not code_cols:
                    code_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['物料编码', '组件编码', '编码', 'code'])]
                
                name_cols = [c for c in df.columns if '组件物料描述' in str(c)]
                if not name_cols:
                    name_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['物料描述', '组件描述', '描述', '名称', 'name'])]
                
                factory_cols = [c for c in df.columns if '工厂名称' in str(c)]
                if not factory_cols:
                    factory_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['工厂', 'factory'])]'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: Fixed column matching order')
else:
    print('SKIP: Pattern not found')
