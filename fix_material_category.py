#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复物料大类筛选：优先用 material_category 列，下拉框也用此列"""

import re

# ========== 第一步：修改 filter_engine.py ==========
print("="*60)
print("第一步：修改 filter_engine.py")
print("="*60)

with open('modules/audit/filters/filter_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到第12点物料大类筛选的代码块，替换为优先使用 material_category
old_filter = """        # 12. 物料大类筛选（兼容 material_category 和 物料类型 两种列名）
        material_category = filters.get('material_category')
        if material_category and material_category != '全部':
            cat_col = None
            for col in ['material_category', '物料类型', '物料大类']:
                if col in df.columns:
                    cat_col = col
                    break
            if cat_col:
                print(f'[DEBUG] 物料大类筛选: 选={material_category}, 使用列={cat_col}, 列值分布={df[cat_col].value_counts().to_dict()}')
                df = df[df[cat_col] == material_category]
                print(f'[DEBUG] 筛选后行数: {len(df)}')
            else:
                print(f'[DEBUG] 物料大类筛选: 未找到物料类型列, df.columns={list(df.columns)}')"""

new_filter = """        # 12. 物料大类筛选（优先使用 material_category 列）
        material_category = filters.get('material_category')
        if material_category and material_category != '全部':
            # 优先使用计算出的 material_category 列
            if 'material_category' in df.columns:
                print(f'[DEBUG] 物料大类筛选: 选={material_category}, 使用列=material_category, 列值分布={df["material_category"].value_counts().to_dict()}')
                df = df[df['material_category'] == material_category]
                print(f'[DEBUG] 筛选后行数: {len(df)}')
            elif '物料类型' in df.columns:
                print(f'[DEBUG] 物料大类筛选: 选={material_category}, 使用列=物料类型, 列值分布={df["物料类型"].value_counts().to_dict()}')
                df = df[df['物料类型'] == material_category]
                print(f'[DEBUG] 筛选后行数: {len(df)}')
            else:
                print(f'[DEBUG] 物料大类筛选: 未找到物料类型列, df.columns={list(df.columns)}')"""

if old_filter in content:
    content = content.replace(old_filter, new_filter, 1)
    print("✅ filter_engine.py 第12点已修改")
else:
    print("⚠️ 未找到匹配文本，手动检查")
    # 打印附近内容帮助调试
    idx = content.find('物料大类筛选')
    if idx >= 0:
        print(f"找到'物料大类筛选'位置: {idx}")
        print(content[idx:idx+200])

with open('modules/audit/filters/filter_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

# ========== 第二步：修改 table_events.py 下拉框更新逻辑 ==========
print("\n" + "="*60)
print("第二步：修改 table_events.py 下拉框更新逻辑")
print("="*60)

with open('gui/event_handlers/table_events.py', 'r', encoding='utf-8') as f:
    content2 = f.read()

# 找到动态更新物料大类下拉框的代码，确保使用 material_category 列
old_dropdown = """        # ── 动态更新物料大类下拉框选项 ──
        if hasattr(self, 'mat_category_cb') and self.mat_category_cb:
            unique_cats = sorted(df['material_category'].dropna().unique())
            values = ["全部"] + [str(c) for c in unique_cats if c]
            self.mat_category_cb['values'] = values
            current = self.mat_category_cb.get()
            if current not in values:
                self.mat_category_cb.set("全部")
            print(f'[DEBUG] material_category 实际唯一值: {unique_cats}')
            print(f'[DEBUG] 下拉框当前values: {values}')"""

# 检查这段是否已经正确（应该已经是正确的了）
if old_dropdown in content2:
    print("✅ table_events.py 下拉框更新逻辑已正确使用 material_category 列")
else:
    print("⚠️ table_events.py 下拉框更新逻辑可能不同，检查当前代码...")
    # 查找相关代码
    idx = content2.find('mat_category_cb')
    if idx >= 0:
        print(f"找到 mat_category_cb 位置: {idx}")
        print(content2[max(0,idx-100):idx+300])

print("\n" + "="*60)
print("修改完成，请运行语法检查")
print("="*60)
