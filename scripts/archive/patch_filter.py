#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""给 filter_engine.py 的 apply() 函数加防御性代码"""

with open('modules/audit/filters/filter_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 '        df = data.copy()' 的行号（缩进8空格）
target = '        df = data.copy()\n'
insert_idx = None
for i, line in enumerate(lines):
    if line == target:
        insert_idx = i
        break

if insert_idx is None:
    print('未找到 [df = data.copy()]，手动检查')
    exit(1)

# 插入防御性代码（缩进8空格）
insert_lines = [
    '\n',
    '        # 防御性：确保 material_category 列存在（如果不存在，现场从物料编码计算）\n',
    '        if "material_category" not in df.columns and "物料编码" in df.columns:\n',
    '            mat_cat_map = {\n',
    '                "100": "原辅料", "200": "包材", "400": "食品辅料/食品半成品",\n',
    '                "410": "饮料辅料/饮料半成品", "500": "食品成品", "510": "饮料成品",\n',
    '                "600": "促销品"\n',
    '            }\n',
    '            df["material_category"] = df["物料编码"].apply(\n',
    '                lambda x: mat_cat_map.get(str(x)[:3], str(x)[:3]) if pd.notna(x) else ""\n',
    '            )\n',
    '            print(f"[DEBUG FilterEngine] 现场计算 material_category, 值分布: {df["material_category"].value_counts().to_dict()}")\n',
    '\n',
]

for j, l in enumerate(insert_lines):
    lines.insert(insert_idx + 1 + j, l)

with open('modules/audit/filters/filter_engine.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f'已插入防御性代码，插入位置: 第{insert_idx+1}行')
print('修改完成，请运行语法检查')
