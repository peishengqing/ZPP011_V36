#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" UI 组件工厂与常量 """

import tkinter as tk
from tkinter import ttk

# ── 主题色 ─────────────────────────────────────────
C = {
    'bg': '#f0f2f5',
    'surface': '#ffffff',
    'surface2': '#f6f8fa',
    'border': '#d0d7de',
    'accent': '#0969da',
    'accent_hover': '#0550ae',
    'accent_text': '#ffffff',
    'text': '#1f2328',
    'text_dim': '#656d76',
    'warn': '#9a6700',
    'danger': '#cf222e',
    'info': '#0969da',
    'green': '#1a7f37',
    'purple': '#8250df',
    'header_bg': '#1a365d',
}

# ── 分析步骤 ─────────────────────────────────────────
STEPS = [
    ('预处理', '⚙'),
    ('Sheet1-汇总统计', '📋'),
    ('Sheet2-替代料明细', '🔄'),
    ('Sheet3-无备注预警', '🚨'),
    ('Sheet4-中间地带', '🖖'),
    ('Sheet5-完整偏差', '📊'),
    ('Sheet6-异常预警', '⚠'),
    ('Sheet7-偏差金额', '💰'),
    ('Sheet8-原因汇总', '📝'),
    ('Sheet9-原因分析', '🔍'),
    ('Sheet10-趋势分析', '📈'),
    ('生成Excel', '💾'),
]

# ── 悬停颜色映射 ────────────────────────────────
_HOVER_MAP = {
    '#0969da': '#0550ae',
    '#9a6700': '#c47f00',
    '#cf222e': '#a50f22',
    '#1a7f37': '#17642e',
    '#f6f8fa': '#e0e3e7',
}

def _hover(bg):
    """获取悬停时的颜色"""
    return _HOVER_MAP.get(bg, bg)

# ── 通用组件工厂 ─────────────────────────────

def card(parent, **kwargs):
    """创建一个带边框的卡片容器"""
    f = tk.Frame(parent, bg=C['surface'], highlightbackground=C['border'],
                highlightthickness=1, **kwargs)
    return f

def btn(parent, text, cmd, bg=C['accent'], fg=C['accent_text'],
       font=("Microsoft YaHei", 10, "bold"), **kw):
    """创建带悬停效果的按钮"""
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                 font=font, relief="flat", cursor="hand2", **kw)
    b.bind("<Enter>", lambda e: b.configure(bg=_hover(bg)))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b

def label(parent, text, size=10, color=C['text'], bold=False, **kw):
    """创建标签"""
    return tk.Label(parent, text=text,
                   font=("Microsoft YaHei", size, "bold" if bold else "normal"),
                   fg=color, bg=C['surface'], **kw)

def entry(parent, var, readonly=False, **kw):
    """创建输入框"""
    e = tk.Entry(parent, textvariable=var, font=("Consolas", 9),
                bg=C['surface2'], fg=C['text'], insertbackground=C['accent'],
                relief="flat", **kw)
    if readonly:
        e.configure(state="readonly", readonlybackground=C['surface2'])
    return e