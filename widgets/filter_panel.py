# -*- coding: utf-8 -*-
"""
侧边栏筛选组件（v39 重构）
冻结期版本：仅 UI 骨架，无实际过滤逻辑
"""
import tkinter as tk
from tkinter import ttk


class FilterPanel(tk.Frame):
    """侧边栏筛选面板，支持折叠/展开"""
    def __init__(self, parent, on_filter_changed=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_filter_changed = on_filter_changed
        self.is_expanded = False
        self.container = None
        self._create_widgets()
        # 初始状态折叠
        self.collapse()

    def _create_widgets(self):
        """创建折叠按钮和内容容器"""
        # 折叠/展开按钮（始终显示）
        self.toggle_btn = tk.Button(
            self, text="▶", font=("Arial", 12), width=2,
            command=self.toggle, relief="flat", bg="#f0f0f0"
        )
        self.toggle_btn.pack(side="top", anchor="ne", padx=2, pady=2)

        # 内容容器（初始为空，展开时填充）
        self.container = tk.Frame(self, bg="#f8f9fa")
        # 不 pack，由 toggle 控制

    def toggle(self):
        """切换展开/折叠状态"""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        """展开侧边栏，显示筛选控件"""
        if not self.is_expanded:
            self.container.pack(side="top", fill="both", expand=True, padx=5, pady=5)
            self._build_filters()
            self.toggle_btn.config(text="◀")
            self.is_expanded = True

    def collapse(self):
        """折叠侧边栏，隐藏筛选控件"""
        if self.is_expanded:
            self.container.pack_forget()
            self.toggle_btn.config(text="▶")
            self.is_expanded = False

    def _build_filters(self):
        """构建筛选控件（冻结期只放占位标签，后续逐步实现）"""
        # 清空容器
        for child in self.container.winfo_children():
            child.destroy()

        # 占位内容（后续替换为真实筛选控件）
        lbl = ttk.Label(self.container, text="筛选栏开发中...", font=("微软雅黑", 10))
        lbl.pack(pady=20)

        # 示例：分组框架
        group_basic = ttk.LabelFrame(self.container, text="基础筛选", padding=5)
        group_basic.pack(fill="x", pady=5)

        ttk.Label(group_basic, text="工厂:").grid(row=0, column=0, sticky="w")
        # 后续添加 Combobox...

        group_adv = ttk.LabelFrame(self.container, text="高级筛选", padding=5)
        group_adv.pack(fill="x", pady=5)
        ttk.Label(group_adv, text="待实现").pack()

    def get_filters(self):
        """返回当前筛选条件字典（冻结期返回空字典）"""
        return {}
