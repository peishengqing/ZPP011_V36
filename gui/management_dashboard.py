# -*- coding: utf-8 -*-
"""
管理看板 - 车间/时间维度偏差趋势
Task 011: 偏差趋势可视化看板

用法: from gui.management_dashboard import ManagementDashboard
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional

try:
    import matplotlib
    matplotlib.use('Agg')  # headless
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

from widgets import C


def _configure_matplotlib_chinese():
    """配置 matplotlib 中文字体（一次性）"""
    if not HAS_MATPLOTLIB:
        return
    # 尝试系统自带微软雅黑
    for font_name in ['Microsoft YaHei', '微软雅黑', 'SimHei', 'Arial Unicode MS']:
        font_paths = fm.findSystemFonts(fontpaths=None, fontext='ttf')
        for fp in font_paths:
            if font_name.lower() in fp.lower():
                try:
                    fm.fontManager.addfont(fp)
                    prop = fm.FontProperties(fname=fp)
                    plt.rcParams['font.family'] = prop.get_name()
                    return
                except Exception:
                    pass
    # 回退到无衬线
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Arial']


_configure_matplotlib_chinese()


class ManagementDashboard:
    """
    管理看板窗口：展示车间/月份偏差趋势数据
    """

    def __init__(self, parent: tk.Tk | tk.Toplevel):
        self.window = tk.Toplevel(parent)
        self.window.title("📊 管理看板 — 偏差趋势")
        self.window.geometry("1000x680")
        self.window.configure(bg=C['bg'])
        self.window.transient(parent)
        self.window.grab_set()

        self._df = None
        self._chart_label: Optional[tk.Label] = None

        self._create_ui()
        self._load_data()

    def _create_ui(self):
        """布局"""
        # 标题栏
        header = tk.Frame(self.window, bg=C['header_bg'], pady=8)
        header.pack(fill="x")
        tk.Label(
            header, text="📊  车间偏差趋势看板",
            font=("Microsoft YaHei", 14, "bold"),
            fg="white", bg=C['header_bg']
        ).pack(side="left", padx=15)

        # 右侧刷新按钮
        ttk.Button(
            header, text="🔄 刷新", command=self._load_data
        ).pack(side="right", padx=15)

        # 标签页
        nb = ttk.Notebook(self.window)
        nb.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Tab1: 月度趋势
        trend_frame = ttk.Frame(nb, padding=5)
        nb.add(trend_frame, text="📈 月度趋势")
        self._build_trend_tab(trend_frame)

        # Tab2: 车间 TOP10
        workshop_frame = ttk.Frame(nb, padding=5)
        nb.add(workshop_frame, text="🏭 车间 TOP10")
        self._build_workshop_tab(workshop_frame)

    def _build_trend_tab(self, parent: ttk.Frame):
        """月度趋势 Tab"""
        # 上部：统计摘要
        summary_frame = ttk.LabelFrame(parent, text="概览", padding=8)
        summary_frame.pack(fill="x", padx=5, pady=(0, 5))
        self._summary_labels = {}
        for key in ['total', 'high', 'avg_rate', 'total_amt']:
            lbl = ttk.Label(summary_frame, text="—", font=("Microsoft YaHei", 12, "bold"),
                            foreground=C['accent'])
            lbl.pack(side="left", padx=20)
            self._summary_labels[key] = lbl
        ttk.Label(summary_frame, text="↑ 全部记录   ↑ 高偏差   ↑ 均偏差率(%)   ↑ 偏差总额(元)").pack(side="right")

        # 图表区域（matplotlib canvas）
        chart_frame = ttk.LabelFrame(parent, text="月度偏差趋势（条数）", padding=5)
        chart_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        self._chart_container = tk.Frame(chart_frame, bg=C['surface'])
        self._chart_container.pack(fill="both", expand=True)

        if not HAS_MATPLOTLIB:
            tk.Label(
                self._chart_container,
                text="⚠ matplotlib 未安装，图表不可用\n\npip install matplotlib numpy",
                font=("Microsoft YaHei", 11), fg=C['warn'], bg=C['surface'],
                justify="center"
            ).pack(fill="both", expand=True)
        else:
            tk.Label(
                self._chart_container,
                text="📊 图表加载中...", font=("Microsoft YaHei", 11),
                fg=C['text_dim'], bg=C['surface']
            ).pack(fill="both", expand=True)

        # 表格区域
        table_frame = ttk.LabelFrame(parent, text="明细", padding=5)
        table_frame.pack(fill="both", expand=True, padx=5)

        self._trend_tree = self._make_tree(
            table_frame,
            columns=('月份', '车间', '总条数', '高偏差条数', '平均偏差率(%)', '总偏差金额'),
            headings=('#0', '月份', '车间', '总条数', '≥30%条数', '均偏差率(%)', '总金额(元)')
        )

    def _build_workshop_tab(self, parent: ttk.Frame):
        """车间 TOP10 Tab"""
        chart_frame = ttk.LabelFrame(parent, text="车间高偏差条数 TOP10", padding=5)
        chart_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self._ws_chart_container = tk.Frame(chart_frame, bg=C['surface'])
        self._ws_chart_container.pack(fill="both", expand=True)

        if not HAS_MATPLOTLIB:
            tk.Label(
                self._ws_chart_container,
                text="⚠ matplotlib 未安装",
                font=("Microsoft YaHei", 11), fg=C['warn'], bg=C['surface']
            ).pack(fill="both", expand=True)
        else:
            tk.Label(
                self._ws_chart_container,
                text="📊 图表加载中...",
                font=("Microsoft YaHei", 11), fg=C['text_dim'], bg=C['surface']
            ).pack(fill="both", expand=True)

        table_frame = ttk.LabelFrame(parent, text="车间排名明细", padding=5)
        table_frame.pack(fill="both", expand=True, padx=5)
        self._ws_tree = self._make_tree(
            table_frame,
            columns=('rank', '车间', '总条数', '高偏差条数', '高偏差占比(%)', '平均偏差率(%)', '总偏差金额'),
            headings=('#0', '排名', '车间', '总条数', '高偏差条数', '占比(%)', '均偏差率(%)', '总金额(元)')
        )

    def _make_tree(self, parent: ttk.Frame, columns: tuple, headings: tuple) -> ttk.Treeview:
        """创建 Treeview + 滚动条"""
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        tree = ttk.Treeview(
            tree_frame,
            columns=columns[1:],  # 第一列是 #0（图标列）
            show='table headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            height=10
        )
        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        # 设置列
        col_widths = {'月份': 100, '车间': 120, '总条数': 80, '高偏差条数': 90,
                      '平均偏差率(%)': 100, '总偏差金额': 110,
                      'rank': 50, '高偏差占比(%)': 100}
        for i, col in enumerate(columns):
            heading_text = headings[i + 1] if i < len(headings) - 1 else col
            tree.heading(f'#{i}', text=heading_text)
            tree.column(f'#{i}', width=col_widths.get(col, 100), anchor="center")

        return tree

    def _load_data(self):
        """从 history_db 加载数据并刷新 UI"""
        from core.history_db import get_monthly_trend

        try:
            self._df = get_monthly_trend()
        except Exception as e:
            self._df = None
            print(f"[管理看板] 加载数据失败: {e}")
            return

        self._refresh_trend_ui()
        self._refresh_workshop_ui()

    def _refresh_trend_ui(self):
        """刷新趋势 Tab"""
        df = self._df
        if df is None or df.empty:
            # 清空摘要
            for lbl in self._summary_labels.values():
                lbl.config(text="—")
            # 清空表格
            for item in self._trend_tree.get_children():
                self._trend_tree.delete(item)
            return

        # 摘要统计
        total = int(df['总条数'].sum())
        high = int(df['高偏差条数'].sum())
        avg_rate = round(df['平均偏差率(%)'].mean(), 1) if len(df) else 0
        total_amt = round(df['总偏差金额'].sum(), 0)

        self._summary_labels['total'].config(text=f"{total:,}")
        self._summary_labels['high'].config(text=f"{high:,}")
        self._summary_labels['avg_rate'].config(text=f"{avg_rate}%")
        self._summary_labels['total_amt'].config(text=f"{total_amt:,.0f}")

        # 刷新 Treeview
        for item in self._trend_tree.get_children():
            self._trend_tree.delete(item)

        # 按月份排序（最新在前）
        df_sorted = df.sort_values('月份', ascending=False)
        for _, row in df_sorted.iterrows():
            self._trend_tree.insert('', 'end', values=(
                row['月份'],
                row['车间'],
                f"{int(row['总条数']):,}",
                f"{int(row['高偏差条数']):,}",
                f"{row['平均偏差率(%)']:.1f}%",
                f"{row['总偏差金额']:,.0f}",
            ))

        # 绘制月度趋势图
        self._draw_trend_chart(df_sorted)

    def _draw_trend_chart(self, df: 'pd.DataFrame'):
        """绘制月度趋势图（高偏差条数堆叠柱状图）"""
        if not HAS_MATPLOTLIB or df.empty:
            return

        # 清理旧图
        for w in self._chart_container.winfo_children():
            w.destroy()

        try:
            # 按月份聚合
            monthly = df.groupby('月份').agg(
                总条数=('总条数', 'sum'),
                高偏差条数=('高偏差条数', 'sum')
            ).reset_index().sort_values('月份')

            if monthly.empty:
                return

            months = monthly['月份'].tolist()
            total_vals = monthly['总条数'].tolist()
            high_vals = monthly['高偏差条数'].tolist()

            fig, ax = plt.subplots(figsize=(8, 3.5), dpi=100)
            fig.patch.set_facecolor(C['surface'])
            ax.set_facecolor('#fafbfc')

            x = range(len(months))
            bar_width = 0.55
            bars1 = ax.bar(x, total_vals, bar_width, label='总偏差条数',
                           color=C['accent'], alpha=0.75, zorder=2)
            bars2 = ax.bar(x, high_vals, bar_width, label='高偏差条数(≥30%)',
                           color=C['danger'], alpha=0.90, zorder=2)

            # 数据标签
            for bar in bars1:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + 1,
                            f'{int(h)}', ha='center', va='bottom', fontsize=7,
                            color=C['text_dim'])
            for bar in bars2:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + 1,
                            f'{int(h)}', ha='center', va='bottom', fontsize=7,
                            color=C['danger'])

            ax.set_xticks(list(x))
            ax.set_xticklabels(months, rotation=30, ha='right', fontsize=8)
            ax.set_ylabel('条数', fontsize=9)
            ax.set_title('月度偏差趋势', fontsize=11, fontweight='bold', pad=8)
            ax.legend(fontsize=8, framealpha=0.5)
            ax.grid(axis='y', linestyle='--', alpha=0.4, zorder=1)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            plt.tight_layout()

            # 嵌入 tkinter
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            canvas = FigureCanvasTkAgg(fig, master=self._chart_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            tk.Label(
                self._chart_container,
                text=f"图表渲染失败: {e}",
                font=("Microsoft YaHei", 10), fg=C['warn'], bg=C['surface']
            ).pack(fill="both", expand=True)

    def _refresh_workshop_ui(self):
        """刷新车间 TOP10 Tab"""
        df = self._df
        if df is None or df.empty:
            for item in self._ws_tree.get_children():
                self._ws_tree.delete(item)
            return

        # 按车间聚合高偏差条数排序，取TOP10
        ws_rank = df.groupby('车间').agg(
            总条数=('总条数', 'sum'),
            高偏差条数=('高偏差条数', 'sum'),
            平均偏差率=('平均偏差率(%)', 'mean'),
            总偏差金额=('总偏差金额', 'sum'),
        ).reset_index().sort_values('高偏差条数', ascending=False).head(10).reset_index(drop=True)

        for item in self._ws_tree.get_children():
            self._ws_tree.delete(item)

        for idx, row in ws_rank.iterrows():
            rank = idx + 1
            total = int(row['总条数'])
            high = int(row['高偏差条数'])
            pct = round(high / total * 100, 1) if total else 0
            self._ws_tree.insert('', 'end', values=(
                f"#{rank}",
                row['车间'],
                f"{total:,}",
                f"{high:,}",
                f"{pct}%",
                f"{row['平均偏差率']:.1f}%",
                f"{row['总偏差金额']:,.0f}",
            ))

        # 绘制车间TOP10图
        self._draw_workshop_chart(ws_rank)

    def _draw_workshop_chart(self, ws_rank: 'pd.DataFrame'):
        """绘制车间TOP10柱状图"""
        if not HAS_MATPLOTLIB or ws_rank.empty:
            return

        for w in self._ws_chart_container.winfo_children():
            w.destroy()

        try:
            fig, ax = plt.subplots(figsize=(7, 3.5), dpi=100)
            fig.patch.set_facecolor(C['surface'])
            ax.set_facecolor('#fafbfc')

            workshops = ws_rank['车间'].tolist()
            high_vals = ws_rank['高偏差条数'].tolist()
            total_vals = ws_rank['总条数'].tolist()

            y = range(len(workshops))
            bar_height = 0.55

            ax.barh(list(y), total_vals, bar_height, label='总偏差条数',
                    color=C['accent'], alpha=0.65, zorder=2)
            ax.barh(list(y), high_vals, bar_height, label='高偏差条数(≥30%)',
                    color=C['danger'], alpha=0.90, zorder=2)

            ax.set_yticks(list(y))
            ax.set_yticklabels(workshops, fontsize=8)
            ax.set_xlabel('条数', fontsize=9)
            ax.set_title('车间高偏差条数 TOP10', fontsize=11, fontweight='bold', pad=8)
            ax.legend(fontsize=8, framealpha=0.5, loc='lower right')
            ax.grid(axis='x', linestyle='--', alpha=0.4, zorder=1)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.invert_yaxis()
            plt.tight_layout()

            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            canvas = FigureCanvasTkAgg(fig, master=self._ws_chart_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            tk.Label(
                self._ws_chart_container,
                text=f"图表渲染失败: {e}",
                font=("Microsoft YaHei", 10), fg=C['warn'], bg=C['surface']
            ).pack(fill="both", expand=True)
