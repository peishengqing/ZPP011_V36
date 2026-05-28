# -*- coding: utf-8 -*-
"""历史对比对话框"""
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from core.history_db import get_analysis_list, compare_analyses, init_db


class HistoryCompareDialog:
    """历史对比窗口"""

    def __init__(self, parent):
        self.parent = parent
        self.selected_id1 = None
        self.selected_id2 = None
        self.analysis_list = []

        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title("历史对比")
        self.window.geometry("900x600")
        self.window.transient(parent)
        self.window.grab_set()

        self._init_db()
        self._create_ui()
        self._load_history_list()

    def _init_db(self):
        """初始化数据库"""
        try:
            init_db()
        except Exception as e:
            messagebox.showerror("错误", f"初始化历史数据库失败：{e}")

    def _create_ui(self):
        """创建 UI"""
        # 主框架
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill="both", expand=True)

        # 左侧：历史记录列表
        left_frame = ttk.LabelFrame(main_frame, text="历史记录", padding=10)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # 列表框
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                   font=('微软雅黑', 10), height=20)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.listbox.bind('<<ListboxSelect>>', self._on_list_select)

        # 按钮行
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(btn_frame, text="刷新", command=self._load_history_list).pack(side="left")

        # 右侧：选择和对比
        right_frame = ttk.LabelFrame(main_frame, text="对比设置", padding=10)
        right_frame.pack(side="right", fill="y", padx=(5, 0))

        # 第一次选择
        ttk.Label(right_frame, text="第一次：").pack(anchor="w")
        self.combo1 = ttk.Combobox(right_frame, state="readonly", width=35)
        self.combo1.pack(fill="x", pady=(0, 10))

        # 第二次选择
        ttk.Label(right_frame, text="第二次：").pack(anchor="w")
        self.combo2 = ttk.Combobox(right_frame, state="readonly", width=35)
        self.combo2.pack(fill="x", pady=(0, 10))

        # 对比按钮
        self.compare_btn = ttk.Button(right_frame, text="开始对比", command=self._do_compare)
        self.compare_btn.pack(fill="x", pady=(10, 0))

        # 结果显示区域
        self.result_frame = ttk.LabelFrame(main_frame, text="对比结果", padding=10)
        self.result_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.result_text = tk.Text(self.result_frame, wrap="word", height=15, width=40,
                                    font=('微软雅黑', 10))
        self.result_text.pack(fill="both", expand=True)

    def _load_history_list(self):
        """加载历史记录"""
        try:
            self.analysis_list = get_analysis_list(limit=100)

            self.listbox.delete(0, tk.END)
            self.combo1['values'] = []
            self.combo2['values'] = []

            if not self.analysis_list:
                self.listbox.insert(0, "暂无历史记录")
                return

            display_items = []
            for item in self.analysis_list:
                ts = item['timestamp'][:19].replace('T', ' ')
                filename = item['file_name']
                total = item['total_rows']
                display = f"{ts} | {filename} ({total}行)"
                display_items.append(display)
                self.listbox.insert(tk.END, display)

            # 更新下拉框
            self.combo1['values'] = display_items
            self.combo2['values'] = display_items

        except Exception as e:
            messagebox.showerror("错误", f"加载历史记录失败：{e}")

    def _on_list_select(self, event):
        """列表选择事件"""
        selection = self.listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx < len(self.analysis_list):
            item = self.analysis_list[idx]
            # 可以在这里设置选择
            pass

    def _do_compare(self):
        """执行对比"""
        idx1 = self.combo1.current()
        idx2 = self.combo2.current()

        if idx1 < 0 or idx2 < 0:
            messagebox.showwarning("提示", "请选择两次分析记录")
            return

        id1 = self.analysis_list[idx1]['id']
        id2 = self.analysis_list[idx2]['id']

        try:
            result = compare_analyses(id1, id2)
            self._show_compare_result(result)
        except Exception as e:
            messagebox.showerror("错误", f"对比失败：{e}")

    def _show_compare_result(self, result: dict):
        """显示对比结果"""
        self.result_text.delete("1.0", tk.END)

        a1 = result['analysis1']
        a2 = result['analysis2']
        diff = result['diff']

        lines = []
        lines.append("=" * 50)
        lines.append("历史对比结果")
        lines.append("=" * 50)
        lines.append("")

        # 警告
        if result.get('filter_warning'):
            lines.append("⚠️ 警告：两次分析的筛选条件不同，对比结果仅供参考！")
            lines.append("")

        # 第一次分析
        lines.append("【第一次分析】")
        lines.append(f"  时间：{a1['timestamp'][:19].replace('T', ' ')}")
        lines.append(f"  文件：{a1['file_name']}")
        lines.append(f"  总行数：{a1['total_rows']}")
        lines.append(f"  高偏差行：{a1['high_dev_rows']}")
        lines.append(f"  待备注行：{a1['need_note_rows']} ({a1['need_note_rate']*100:.1f}%)")
        lines.append(f"  已审核行：{a1['approved_rows']} ({a1['approved_rate']*100:.1f}%)")
        lines.append("")

        # 第二次分析
        lines.append("【第二次分析】")
        lines.append(f"  时间：{a2['timestamp'][:19].replace('T', ' ')}")
        lines.append(f"  文件：{a2['file_name']}")
        lines.append(f"  总行数：{a2['total_rows']}")
        lines.append(f"  高偏差行：{a2['high_dev_rows']}")
        lines.append(f"  待备注行：{a2['need_note_rows']} ({a2['need_note_rate']*100:.1f}%)")
        lines.append(f"  已审核行：{a2['approved_rows']} ({a2['approved_rate']*100:.1f}%)")
        lines.append("")

        # 差异
        lines.append("【变化情况】")
        d_total = diff['total_rows']
        d_high = diff['high_dev_rows']
        d_note = diff['need_note_rows']
        d_approved = diff['approved_rows']

        lines.append(f"  总行数：{d_total:+d}")
        lines.append(f"  高偏差行：{d_high:+d}")
        lines.append(f"  待备注行：{d_note:+d}")
        lines.append(f"  已审核行：{d_approved:+d}")

        self.result_text.insert("1.0", "\n".join(lines))
