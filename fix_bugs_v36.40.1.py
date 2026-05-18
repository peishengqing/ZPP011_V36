#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bug 修复脚本 v36.40.1
修复内容：
1. Bug 4: 偏差金额计算错误（全部为0）
2. Bug 6: 去重逻辑不严谨（允许 A=B）
3. Bug 5: 替代料下拉框显示格式

使用方法：
1. 将此脚本复制到项目根目录
2. 运行: python fix_bugs_v36.40.1.py
3. 重新打包 exe
"""

import os
import sys

def fix_analyzer_deviation_amount():
    """修复 Bug 4: 偏差金额计算逻辑"""
    file_path = "analysis/analyzer.py"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找并替换偏差金额计算逻辑
    old_code = '''    # 计算偏差金额(含税)
    df['_unit_price_tax'] = 0.0
    valid_mask = (df['数量-实际'] > 0) & (df['金额-实际(含税)'] > 0)
    df.loc[valid_mask, '_unit_price_tax'] = df.loc[valid_mask, '金额-实际(含税)'] / df.loc[valid_mask, '数量-实际']
    df['偏差金额(含税)'] = (df['材料偏差'] * df['_unit_price_tax']).round(2)'''
    
    new_code = '''    # 计算偏差金额(含税) - 修复：增加兜底逻辑
    df['_unit_price_tax'] = 0.0
    
    # 尝试从多个来源获取单价
    # 优先级：1.金额-实际(含税)/数量-实际  2.金额-定额(含税)/数量-定额
    valid_mask_actual = (df['数量-实际'] > 0) & (df['金额-实际(含税)'] > 0)
    valid_mask_quota = (df['数量-定额'] > 0) & (df['金额-定额(含税)'] > 0)
    
    # 先用实际金额计算
    df.loc[valid_mask_actual, '_unit_price_tax'] = (
        df.loc[valid_mask_actual, '金额-实际(含税)'] / 
        df.loc[valid_mask_actual, '数量-实际']
    )
    
    # 实际金额缺失的，用定额金额计算
    missing_mask = (~valid_mask_actual) & valid_mask_quota
    df.loc[missing_mask, '_unit_price_tax'] = (
        df.loc[missing_mask, '金额-定额(含税)'] / 
        df.loc[missing_mask, '数量-定额']
    )
    
    # 计算偏差金额
    df['偏差金额(含税)'] = (df['材料偏差'] * df['_unit_price_tax']).round(2)
    
    # 调试日志：记录有多少行成功计算了单价
    calculated_count = (df['_unit_price_tax'] > 0).sum()
    print(f"[偏差金额计算] 成功计算 {calculated_count}/{len(df)} 行的单价")'''
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已修复: {file_path} - 偏差金额计算逻辑")
        return True
    else:
        print(f"⚠️ 未找到目标代码，可能已修复: {file_path}")
        return False

def fix_events_alt_duplicate_check():
    """修复 Bug 6: 去重逻辑增加 A≠B 检查"""
    file_path = "gui/events.py"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找确认按钮的代码块，在添加配对前增加 A≠B 检查
    old_code = '''            factory_a, a_code, a_name = parse_selection(a)
            factory_b, b_code, b_name = parse_selection(b)

            # 去重检查：是否已存在相同配对'''
    
    new_code = '''            factory_a, a_code, a_name = parse_selection(a)
            factory_b, b_code, b_name = parse_selection(b)

            # Bug 6 修复：检查 A 和 B 不能是同一个物料
            if a_code == b_code:
                messagebox.showwarning("提示", "物料A和物料B不能是同一个物料！")
                return

            # 去重检查：是否已存在相同配对'''
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已修复: {file_path} - 去重逻辑增加 A≠B 检查")
        return True
    else:
        print(f"⚠️ 未找到目标代码，可能已修复: {file_path}")
        return False

def fix_events_material_list_format():
    """修复 Bug 5: 替代料下拉框显示格式"""
    file_path = "gui/events.py"
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找 parse_selection 函数，确保能正确解析 编码|名称|工厂 格式
    old_code = '''            def parse_selection(x):
                if '|' in x:
                    parts = [p.strip() for p in x.split('|')]
                    if len(parts) >= 3:
                        return parts[0], parts[1], parts[2]
                    elif len(parts) == 2:
                        return '', parts[0], parts[1]
                    else:
                        return '', parts[0], ''
                else:
                    # 手动输入时尝试从物料列表匹配
                    for item in getattr(self, 'material_list', []):
                        if x in item:
                            parts = [p.strip() for p in item.split('|')]
                            if len(parts) >= 3:
                                return parts[0], parts[1], parts[2]
                    return '', x, x'''
    
    new_code = '''            def parse_selection(x):
                if '|' in x:
                    parts = [p.strip() for p in x.split('|')]
                    if len(parts) >= 3:
                        # 格式: 编码 | 名称 | 工厂
                        return parts[2], parts[0], parts[1]  # (工厂, 编码, 名称)
                    elif len(parts) == 2:
                        # 格式: 编码 | 工厂
                        return parts[1], parts[0], ''  # (工厂, 编码, 空名称)
                    else:
                        return '', parts[0], ''  # (空工厂, 编码, 空名称)
                else:
                    # 手动输入时尝试从物料列表匹配
                    for item in getattr(self, 'material_list', []):
                        if x in item:
                            parts = [p.strip() for p in item.split('|')]
                            if len(parts) >= 3:
                                return parts[2], parts[0], parts[1]  # (工厂, 编码, 名称)
                    return '', x, x  # 兜底'''
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已修复: {file_path} - 物料解析格式（编码|名称|工厂）")
        return True
    else:
        print(f"⚠️ 未找到目标代码，可能已修复: {file_path}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("ZPP011 Bug 修复脚本 v36.40.1")
    print("=" * 60)
    
    results = []
    
    # 修复 Bug 4
    print("\n[1/3] 修复 Bug 4: 偏差金额计算...")
    results.append(("Bug 4 偏差金额", fix_analyzer_deviation_amount()))
    
    # 修复 Bug 6
    print("\n[2/3] 修复 Bug 6: 去重逻辑...")
    results.append(("Bug 6 A≠B检查", fix_events_alt_duplicate_check()))
    
    # 修复 Bug 5
    print("\n[3/3] 修复 Bug 5: 物料格式...")
    results.append(("Bug 5 物料格式", fix_events_material_list_format()))
    
    print("\n" + "=" * 60)
    print("修复结果汇总:")
    print("=" * 60)
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"  {name}: {status}")
    
    print("\n修复完成后，请重新打包生成 exe。")
    print("命令: python build.py")
