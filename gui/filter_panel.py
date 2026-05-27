# -*- coding: utf-8 -*-
"""
侧边栏筛选面板 v1.1（完整功能版）
"""
import tkinter as tk
from tkinter import ttk


class FilterPanel(tk.Frame):
    """侧边栏筛选面板（可折叠/展开）"""

    def __init__(self, parent, on_filter_changed=None, **kw):
        super().__init__(parent, **kw)
        self.parent = parent
        self.on_filter_changed = on_filter_changed
        self.is_expanded = False
        self._search_delay = 300   # 搜索防抖延迟(ms)
        self._search_timer = None

        self.configure(bg="#f0f0f0")
        self._create_toggle_bar()
        self._create_container()

    # ------------------------------------------------------------------ #
    #  UI 构建
    # ------------------------------------------------------------------ #
    def _create_toggle_bar(self):
        """创建右侧折叠/展开按钮条"""
        self.toggle_bar = tk.Frame(self, width=10, bg="#d0d0d0", cursor="hand2")
        self.toggle_bar.pack(side="right", fill="y")
        self.toggle_bar.pack_propagate(False)

        self.toggle_label = tk.Label(
            self.toggle_bar, text="筛\n选", bg="#d0d0d0",
            font=("微软雅黑", 9), fg="#333", cursor="hand2"
        )
        self.toggle_label.pack(expand=True)

        self.toggle_bar.bind("<Button-1>", lambda e: self.toggle())
        self.toggle_label.bind("<Button-1>", lambda e: self.toggle())

    def _create_container(self):
        """创建左侧筛选控件容器（初始隐藏）"""
        self.container = tk.Frame(self, bg="#f8f9fa", width=250)
        self.container.pack_propagate(False)
        self.container.configure(width=250)

        # ---- 基础筛选 ----
        self.group_basic = ttk.LabelFrame(self.container, text="基础筛选", padding=5)
        self.group_basic.pack(fill="x", pady=5, padx=5)

        ttk.Label(self.group_basic, text="工厂:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.factory_var = tk.StringVar(value="全部")
        self.factory_cb = ttk.Combobox(
            self.group_basic, textvariable=self.factory_var,
            values=["全部"], state="readonly", width=20
        )
        self.factory_cb.grid(row=0, column=1, padx=5, pady=2)
        self.factory_cb.bind("<<ComboboxSelected>>", self._on_immediate_change)

        ttk.Label(self.group_basic, text="车间:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.workshop_var = tk.StringVar(value="全部")
        self.workshop_cb = ttk.Combobox(
            self.group_basic, textvariable=self.workshop_var,
            values=["全部"], state="readonly", width=20
        )
        self.workshop_cb.grid(row=1, column=1, padx=5, pady=2)
        self.workshop_cb.bind("<<ComboboxSelected>>", self._on_immediate_change)

        ttk.Label(self.group_basic, text="物料描述:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.material_var = tk.StringVar()
        self.material_entry = ttk.Entry(self.group_basic, textvariable=self.material_var, width=20)
        self.material_entry.grid(row=2, column=1, padx=5, pady=2)
        self.material_var.trace_add("write", self._on_search_changed)

        # ---- 偏差筛选 ----
        self.group_dev = ttk.LabelFrame(self.container, text="偏差筛选", padding=5)
        self.group_dev.pack(fill="x", pady=5, padx=5)

        ttk.Label(self.group_dev, text="偏差率:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.dev_rate_var = tk.StringVar(value="全部")
        self.dev_rate_cb = ttk.Combobox(
            self.group_dev, textvariable=self.dev_rate_var,
            values=["全部", ">10%", ">20%", ">30%", "<-10%", "<-20%", "绝对值≥10%"],
            state="readonly", width=20
        )
        self.dev_rate_cb.grid(row=0, column=1, padx=5, pady=2)
        self.dev_rate_cb.bind("<<ComboboxSelected>>", self._on_immediate_change)

        ttk.Label(self.group_dev, text="金额范围:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        frame_amount = tk.Frame(self.group_dev)
        frame_amount.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        self.amount_min_var = tk.StringVar()
        self.amount_min_entry = ttk.Entry(frame_amount, textvariable=self.amount_min_var, width=8)
        self.amount_min_entry.pack(side="left")

        ttk.Label(frame_amount, text=" ~ ").pack(side="left")

        self.amount_max_var = tk.StringVar()
        self.amount_max_entry = ttk.Entry(frame_amount, textvariable=self.amount_max_var, width=8)
        self.amount_max_entry.pack(side="left")

        self.amount_min_var.trace_add("write", self._on_search_changed)
        self.amount_max_var.trace_add("write", self._on_search_changed)

        # ---- 其他筛选 ----
        self.group_other = ttk.LabelFrame(self.container, text="其他筛选", padding=5)
        self.group_other.pack(fill="x", pady=5, padx=5)

        ttk.Label(self.group_other, text="审核状态:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.status_var = tk.StringVar(value="全部")
        self.status_cb = ttk.Combobox(
            self.group_other, textvariable=self.status_var,
            values=["全部", "已备注", "需补备注"],
            state="readonly", width=20
        )
        self.status_cb.grid(row=0, column=1, padx=5, pady=2)
        self.status_cb.bind("<<ComboboxSelected>>", self._on_immediate_change)

        ttk.Label(self.group_other, text="替代料:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.alt_var = tk.StringVar(value="全部")
        self.alt_cb = ttk.Combobox(
            self.group_other, textvariable=self.alt_var,
            values=["全部", "是", "否"],
            state="readonly", width=20
        )
        self.alt_cb.grid(row=1, column=1, padx=5, pady=2)
        self.alt_cb.bind("<<ComboboxSelected>>", self._on_immediate_change)

        ttk.Label(self.group_other, text="优先级颜色:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.color_var = tk.StringVar(value="全部")
        self.color_cb = ttk.Combobox(
            self.group_other, textvariable=self.color_var,
            values=["全部", "红", "黄", "绿"],
            state="readonly", width=20
        )
        self.color_cb.grid(row=2, column=1, padx=5, pady=2)
        self.color_cb.bind("<<ComboboxSelected>>", self._on_immediate_change)

        # ---- 重置按钮 ----
        self.reset_btn = ttk.Button(self.container, text="重置全部筛选", command=self._reset_filters)
        self.reset_btn.pack(pady=10)

    # ------------------------------------------------------------------ #
    # 展开 / 折叠
    # ------------------------------------------------------------------ #
    def toggle(self):
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        if not self.is_expanded:
            self.container.pack(side="right", fill="y", before=self.toggle_bar)
            self.is_expanded = True
            if self.parent and hasattr(self.parent, '_on_filter_panel_expand'):
                self.parent._on_filter_panel_expand(True)

    def collapse(self):
        if self.is_expanded:
            self.container.pack_forget()
            self.is_expanded = False
            if self.parent and hasattr(self.parent, '_on_filter_panel_expand'):
                self.parent._on_filter_panel_expand(False)

    # ------------------------------------------------------------------ #
    # 事件回调
    # ------------------------------------------------------------------ #
    def _on_immediate_change(self, event=None):
        """下拉框立即触发回调"""
        if self.on_filter_changed:
            self.on_filter_changed(self.get_filters())

    def _on_search_changed(self, *args):
        """搜索框防抖（300ms 后触发）"""
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(self._search_delay, self._on_search_delayed)

    def _on_search_delayed(self):
        """防抖后的实际触发"""
        if self.on_filter_changed:
            self.on_filter_changed(self.get_filters())

    def _reset_filters(self):
        """重置全部筛选条件"""
        self.factory_var.set("全部")
        self.workshop_var.set("全部")
        self.material_var.set("")
        self.dev_rate_var.set("全部")
        self.amount_min_var.set("")
        self.amount_max_var.set("")
        self.status_var.set("全部")
        self.alt_var.set("全部")
        self.color_var.set("全部")
        if self.on_filter_changed:
            self.on_filter_changed(self.get_filters())

    # ------------------------------------------------------------------ #
    # 动态选项更新（数据加载后调用）
    # ------------------------------------------------------------------ #
    def update_options(self, audit_data):
        """根据加载的 audit_data 动态更新下拉框的可选值"""
        if audit_data is None or audit_data.empty:
            return

        # 更新工厂列表
        if '工厂' in audit_data.columns:
            factories = sorted(audit_data['工厂'].dropna().unique())
            factories = ['全部'] + [str(f) for f in factories if str(f) != '全部']
            self.factory_cb['values'] = factories
            if self.factory_var.get() not in factories:
                self.factory_var.set('全部')

        # 更新车间列表
        if '车间' in audit_data.columns:
            workshops = sorted(audit_data['车间'].dropna().unique())
            workshops = ['全部'] + [str(w) for w in workshops if str(w) != '全部']
            self.workshop_cb['values'] = workshops
            if self.workshop_var.get() not in workshops:
                self.workshop_var.set('全部')

    # ------------------------------------------------------------------ #
    # 获取当前筛选条件
    # ------------------------------------------------------------------ #
    def get_filters(self):
        """返回当前所有筛选条件（字典）"""
        return {
            "factory": self.factory_var.get(),
            "workshop": self.workshop_var.get(),
            "material": self.material_var.get().strip(),
            "dev_rate": self.dev_rate_var.get(),
            "amount_min": self.amount_min_var.get().strip(),
            "amount_max": self.amount_max_var.get().strip(),
            "status": self.status_var.get(),
            "is_alt": self.alt_var.get(),
            "priority_color": self.color_var.get(),
        }
