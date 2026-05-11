# -*- coding: utf-8 -*-
"""
路径配置（v36 抽取）
"""

import os

# 基础路径（config目录的父目录即项目根目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 输出目录
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# 确保目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
