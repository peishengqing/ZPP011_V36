# -*- coding: utf-8 -*-
"""
生成 smart_ppt_generator_v4.py 的脚本
分块写入，避免单次内容过长
"""
import textwrap

parts = []

# ========== PART 1: 头部 + 配置 + 工具函数 ==========
part1 = '''
# -*- coding: utf-8 -*-
"""
ZPP011 智能PPT生成器 v4 (10维高阶思维 + 不限页数)
10维分析框架：
  1. 执行摘要    2. 数据质量评估  3. 整体偏差概览
  4. 食品/饮料对比  5. 车间维度分析  6. 物料分类分析
  7. 偏差原因根因  8. 趋势预测      9. 异常预警
 10. 改进建议 + 动态附录（按数据量自动扩展页数）
"""
import os, re, warnings, math
from datetime import datetime
from io import BytesIO
from typing import List, Dict, Tuple, Optional, Any

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import ChartData

warnings.filterwarnings("ignore", category=UserWarning)
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
COMPANY = "云南达利生产基地"
TITLE   = "ZPP011 生产偏差深度分析报告"
SUBTITLE = "数据驱动决策 · 精准管控成本"

COLOR = {
    'primary':   RGBColor(41, 128, 185),
    'secondary': RGBColor(142, 68, 173),
    'accent':    RGBColor(230, 126, 34),
    'success':   RGBColor(39, 174, 96),
    'danger':   RGBColor(231, 76, 60),
    'warning':   RGBColor(241, 196, 15),
    'dark':     RGBColor(44, 62, 80),
    'light':    RGBColor(236, 240, 241),
    'white':    RGBColor(255, 255, 255),
    'text':     RGBColor(52, 73, 94),
    'text_l':   RGBColor(149, 165, 166),
    'food':     RGBColor(231, 76, 60),
    'bev':      RGBColor(41, 128, 185),
}
MPL = {'pos':'#e74c3c','neg':'#27ae60','pri':'#2980b9','acc':'#e67e22'}
ROWS_PER_SLIDE = 18
'''.strip()

parts.append(('PART1', part1))
print('PART1 ready, len=%d' % len(part1))
