#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""添加环形饼图函数到 ppt_generator.py"""

import re

file_path = r"E:\zpp011_dev\模块化脚本\ppt_generator.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在 _create_trend_chart_image 函数后添加 _add_doughnut_chart 函数
trend_func_end = content.find('    img_buf.seek(0)\n    return img_buf\n\ndef run_ppt_generation(')
if trend_func_end == -1:
    print("❌ 未找到 _create_trend_chart_image 函数结束位置")
    exit(1)

new_func = '''    img_buf.seek(0)
    return img_buf

def _add_doughnut_chart(slide, over_amount, under_amount):
    """添加多耗/少耗环形饼图"""
    if over_amount == 0 and under_amount == 0:
        return  # 无数据，跳过

    chart_data = ChartData()
    chart_data.categories = ['多耗', '少耗']
    chart_data.add_series('偏差金额', [over_amount, under_amount])

    x, y, cx, cy = Inches(1), Inches(1.5), Inches(8), Inches(4.5)
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.DOUGHNUT, x, y, cx, cy, chart_data
    ).chart

    # 设置标题
    chart.has_title = True
    chart.chart_title.text_frame.text = "多耗与少耗占比"

    # 设置数据点颜色
    series = chart.series[0]
    points = series.points
    if len(points) >= 2:
        # 多耗 -> 红色
        points[0].format.fill.solid()
        points[0].format.fill.fore_color.rgb = RGBColor(0xE7, 0x4C, 0x3C)
        # 少耗 -> 绿色
        points[1].format.fill.solid()
        points[1].format.fill.fore_color.rgb = RGBColor(0x2E, 0xCC, 0x71)

def run_ppt_generation('''

content = content.replace(
    '    img_buf.seek(0)\n    return img_buf\n\ndef run_ppt_generation(',
    new_func
)

# 2. 在 run_ppt_generation 中，dev_detail_df 生成后添加环形饼图
# 找到 dev_detail_df 生成位置
dev_detail_pos = content.find("    dev_detail_df = safe_read('完整偏差明细')")
if dev_detail_pos == -1:
    print("⚠️ 未找到 dev_detail_df 生成位置，将跳过插入图表代码")
else:
    # 找到 dev_detail_df 使用后的合适位置（在第一个 slide 创建前）
    # 查找 "prs = Presentation()" 后的第一个 slide 创建
    prs_pos = content.find('    prs = Presentation()', dev_detail_pos)
    if prs_pos == -1:
        print("⚠️ 未找到 prs 创建位置")
    else:
        # 在 prs 创建后、第一个 slide 创建前插入饼图代码
        first_slide_pos = content.find('    slide1 =', prs_pos)
        if first_slide_pos == -1:
            print("⚠️ 未找到第一个 slide 创建位置")
        else:
            # 在前一个换行符后插入
            insert_pos = first_slide_pos
            doughnut_code = '''
    # 新增：多耗/少耗环形饼图
    over_total = 0.0
    under_total = 0.0
    if not dev_detail_df.empty and '偏差金额(含税)' in dev_detail_df.columns:
        over_total = dev_detail_df[dev_detail_df['偏差金额(含税)'] > 0]['偏差金额(含税)'].sum()
        under_total = dev_detail_df[dev_detail_df['偏差金额(含税)'] < 0]['偏差金额(含税)'].abs().sum()

    if over_total > 0 or under_total > 0:
        doughnut_slide = prs.slides.add_slide(_get_blank_layout(prs))
        set_slide_bg(doughnut_slide, C_BG)
        add_title_bar(doughnut_slide, '多耗与少耗占比', '偏差金额分布')
        _add_doughnut_chart(doughnut_slide, over_total, under_total)
        _log("  [PPT] 环形饼图完成")
'''
            content = content[:insert_pos] + doughnut_code + content[insert_pos:]

# 写入文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 成功添加 _add_doughnut_chart 函数")
print("✅ 成功在 run_ppt_generation 中插入环形饼图代码")
