# -*- coding: utf-8 -*-
"""
筛选管理器 - 处理统计卡片点击筛选等 UI 逻辑
"""
import tkinter as tk
from widgets import C  # 添加这一行


class FilterManager:
    def __init__(self, host):
        self.host = host
        # 其余保持不变
