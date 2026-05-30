# -*- coding: utf-8 -*-
"""管理看板 - 车间偏差排名 + 时间趋势"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import pandas as pd

from core import history_db


class DashboardWindow:
    def __init__(self, parent, history_db_path=None, current_data_func=None):
        self.parent = parent
        self.history_db_path = history_db_path
        self.current_df = None
        self._current_data_func = current_data_func
        self.window = tk.Toplevel(parent)
        self.window.title("管理看板 - ZPP011")
        self.window.geometry("900x650")
        self.window.minsize(800, 500)

        self.source_var = tk.StringVar(value="current")
        self.history_id = None

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        # 工具栏
        toolbar = tk.Frame(self.window)
        toolbar.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(toolbar, text="数据源:").pack(side=tk.LEFT)
        tk.Radiobutton(toolbar, text="当前分析结果", variable=self.source_var,
                       value="current", command=self._refresh).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(toolbar, text="历史分析", variable=self.source_var,
                       value="history", command=self._on_history_selected).pack(side=tk.LEFT, padx=5)

        self.history_combo = ttk.Combobox(toolbar, state="readonly", width=40)
        self.history_combo.pack(side=tk.LEFT, padx=5)
        self.history_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh())

        tk.Button(toolbar, text="刷新", command=self._refresh).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="导出截图", command=self._export_screenshot).pack(side=tk.RIGHT, padx=5)

        # Notebook 标签页
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tab_workshop = tk.Frame(self.notebook)
        self.tab_trend = tk.Frame(self.notebook)
        self.notebook.add(self.tab_workshop, text="车间偏差排名")
        self.notebook.add(self.tab_trend, text="时间趋势（近6个月）")

        # 归因按钮（单独一行）
        btn_frame = tk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(btn_frame, text="AI 归因分析", command=self._show_attribution,
                  bg="#6f42c1", fg="white").pack(side=tk.RIGHT)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(self.window, textvariable=self.status_var, bd=1,
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _load_history_list(self):
        records = history_db.get_analysis_list(limit=50)
        if records:
            self.history_combo['values'] = [f"{r['id']}: {r['timestamp'][:16]} - {r['file_name']}" for r in records]
            if not self.history_combo.get():
                self.history_combo.current(0)
        else:
            self.history_combo['values'] = []
            self.history_combo.set("无历史数据")

    def _get_dataframe(self):
        if self.source_var.get() == "current":
            if self._current_data_func is not None:
                df = self._current_data_func()
                if df is not None and not df.empty:
                    return df
            self.status_var.set("当前无分析数据，请先执行分析")
            return None
        else:
            selected = self.history_combo.get()
            if selected and ":" in selected:
                try:
                    aid = int(selected.split(":")[0])
                    df = history_db.get_analysis_data(aid, db_path=self.history_db_path)
                    return df
                except Exception as e:
                    self.status_var.set(f"加载历史数据失败: {e}")
                    return None

    def _refresh(self):
        if self.source_var.get() == "history":
            self._load_history_list()

        df = self._get_dataframe()
        if df is None or df.empty:
            for widget in self.tab_workshop.winfo_children():
                widget.destroy()
            tk.Label(self.tab_workshop, text="无数据", font=("微软雅黑", 14)).pack(expand=True)
            self.status_var.set("无数据，请先执行分析或选择有效历史记录")
            return

        self.current_df = df
        self._draw_workshop_chart(df)
        self._draw_trend_chart()
        self.status_var.set(f"数据行数: {len(df)}")

    def _on_history_selected(self):
        self._load_history_list()
        self._refresh()

    def _draw_workshop_chart(self, df):
        """绘制各车间偏差金额排名柱状图"""
        for widget in self.tab_workshop.winfo_children():
            widget.destroy()

        # 确定偏差金额列名
        amount_col = None
        for col in ['偏差金额', '偏差金额(含税)', 'deviation_amount']:
            if col in df.columns:
                amount_col = col
                break
        if amount_col is None:
            tk.Label(self.tab_workshop, text="数据中无偏差金额列，无法生成车间排名",
                     font=("微软雅黑", 12), fg="red").pack(expand=True)
            return

        # 确定车间列名
        workshop_col = None
        for col in ['车间', '生产管理员描述', 'workshop']:
            if col in df.columns:
                workshop_col = col
                break
        if workshop_col is None:
            tk.Label(self.tab_workshop, text="数据中无车间列",
                     font=("微软雅黑", 12), fg="red").pack(expand=True)
            return

        # 按车间聚合偏差金额（绝对值合计）
        workshop_amount = df.groupby(workshop_col)[amount_col].apply(
            lambda x: x.abs().sum()).sort_values(ascending=False)
        if workshop_amount.empty:
            tk.Label(self.tab_workshop, text="无有效偏差金额数据",
                     font=("微软雅黑", 12)).pack(expand=True)
            return

        fig = plt.Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        workshops = workshop_amount.index.tolist()
        amounts = workshop_amount.values
        bars = ax.bar(workshops, amounts, color='steelblue')
        ax.set_title('各车间偏差金额（绝对值）排名')
        ax.set_xlabel('车间')
        ax.set_ylabel('偏差金额（元）')
        ax.tick_params(axis='x', rotation=45)
        # 添加数值标签
        for bar, val in zip(bars, amounts):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(amounts)*0.01,
                    f'{val:,.0f}', ha='center', va='bottom', fontsize=8)

        canvas = FigureCanvasTkAgg(fig, master=self.tab_workshop)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _draw_trend_chart(self):
        for widget in self.tab_trend.winfo_children():
            widget.destroy()

        try:
            # 兜底：如果 history_db_path 为 None，使用默认路径
            db_path = self.history_db_path if self.history_db_path else history_db.DB_PATH
            monthly = history_db.get_monthly_trend(months=6)
            if monthly.empty:
                tk.Label(self.tab_trend, text="历史数据不足，无法绘制趋势图", font=("微软雅黑", 14)).pack(expand=True)
                return

            fig = plt.Figure(figsize=(8, 4), dpi=100)
            ax = fig.add_subplot(111)
            ax.plot(monthly['month'], monthly['high_dev_rows'], marker='o', linestyle='-', color='green')
            ax.set_title('近6个月偏差>10% 行数趋势')
            ax.set_xlabel('月份')
            ax.set_ylabel('行数')
            ax.tick_params(axis='x', rotation=45)

            canvas = FigureCanvasTkAgg(fig, master=self.tab_trend)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            tk.Label(self.tab_trend, text=f"加载趋势失败: {e}", fg="red").pack(expand=True)

    def _export_screenshot(self):
        current_tab = self.notebook.select()
        tab_text = self.notebook.tab(current_tab, "text")
        for widget in self.notebook.nametowidget(current_tab).winfo_children():
            if isinstance(widget, FigureCanvasTkAgg):
                file_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                        filetypes=[("PNG files", "*.png")])
                if file_path:
                    widget.figure.savefig(file_path, dpi=150)
                    messagebox.showinfo("导出成功", f"已保存到 {file_path}")
                return
        messagebox.showwarning("无法导出", "未找到可导出的图表")

    def _show_attribution(self):
        if self.current_df is None or self.current_df.empty:
            messagebox.showwarning("无数据", "没有可分析的数据")
            return

        from core.attribution import generate_report_text, get_latest_history_analysis
        # 获取历史数据
        history_df = None
        if self.source_var.get() == "history" and self.history_combo.get():
            selected = self.history_combo.get()
            if ":" in selected:
                try:
                    aid = int(selected.split(":")[0])
                    history_df = history_db.get_analysis_data(aid, db_path=self.history_db_path)
                except Exception:
                    pass
        elif self.source_var.get() == "current":
            history_df = get_latest_history_analysis()

        report = generate_report_text(self.current_df, history_df)
        self._show_report_window(report)

    def _show_report_window(self, report_text):
        win = tk.Toplevel(self.window)
        win.title("AI 归因分析报告")
        win.geometry("600x400")
        text = tk.Text(win, wrap=tk.WORD, font=("微软雅黑", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, report_text)
        text.config(state=tk.DISABLED)
        # 保存按钮
        def save_report():
            file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                     filetypes=[("Text files", "*.txt")])
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                messagebox.showinfo("保存成功", f"报告已保存至 {file_path}")
        tk.Button(win, text="保存报告", command=save_report).pack(side=tk.LEFT, padx=10, pady=5)
        tk.Button(win, text="关闭", command=win.destroy).pack(side=tk.RIGHT, padx=10, pady=5)
