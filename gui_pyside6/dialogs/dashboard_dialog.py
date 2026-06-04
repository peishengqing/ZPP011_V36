# -*- coding: utf-8 -*-
"""管理看板对话框 - PySide6 迁移版"""

import json
from pathlib import Path

import pandas as pd
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QMessageBox,
)
from PySide6.QtCore import Signal, QThread, QObject
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

try:
    from gui_pyside6.utils.atomic_json import atomic_save_json
except ImportError:

    def atomic_save_json(data, path):
        import json as _json

        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        import os

        if os.path.exists(path):
            os.replace(tmp, path)
        else:
            os.rename(tmp, path)


class AnalysisWorker(QObject):
    """分析工作线程"""

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, audit_df, material_df):
        super().__init__()
        self.audit_df = audit_df
        self.material_df = material_df

    def run(self):
        try:
            self.progress.emit(10, "数据预处理...")
            result = self._analyze()
            self.progress.emit(100, "完成")
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def _analyze(self):
        audit_df = self.audit_df
        # material_df 预留，用于后续 AI 归因分析扩展
        self.progress.emit(30, "计算车间排名...")
        # 车间排名
        if "workshop" in audit_df.columns and "deviation_amount" in audit_df.columns:
            ws = (
                audit_df.groupby("workshop", dropna=False)["deviation_amount"]
                .sum()
                .sort_values(ascending=False)
            )
        else:
            ws = pd.Series(dtype=float)
        self.progress.emit(50, "计算物料大类排名...")
        # 物料大类排名
        if (
            "material_group" in audit_df.columns
            and "deviation_amount" in audit_df.columns
        ):
            mg = (
                audit_df.groupby("material_group", dropna=False)[
                    "deviation_amount"]
                .sum()
                .sort_values(ascending=False)
            )
        else:
            mg = pd.Series(dtype=float)
        self.progress.emit(70, "计算时间趋势...")
        # 时间趋势
        if "order_date" in audit_df.columns and "deviation_amount" in audit_df.columns:
            audit_df["order_date"] = pd.to_datetime(
                audit_df["order_date"], errors="coerce"
            )
            trend = (
                audit_df.groupby(audit_df["order_date"].dt.to_period("M"))[
                    "deviation_amount"
                ]
                .sum()
                .sort_index()
            )
        else:
            trend = pd.Series(dtype=float)
        self.progress.emit(90, "生成小结...")
        summary = self._generate_summary(ws, mg, trend, audit_df)
        return {
            "workshop_rank": ws,
            "material_group_rank": mg,
            "trend": trend,
            "summary": summary,
            "audit_df": audit_df,
        }

    def _generate_summary(self, ws, mg, trend, audit_df):
        lines = []
        if not ws.empty:
            top_ws = ws.head(3)
            lines.append(
                "车间偏差TOP3："
                + "，".join([f"{k}({v:,.0f})" for k, v in top_ws.items()])
            )
        if not mg.empty:
            top_mg = mg.head(3)
            lines.append(
                "物料大类偏差TOP3："
                + "，".join([f"{k}({v:,.0f})" for k, v in top_mg.items()])
            )
        total = (
            audit_df["deviation_amount"].sum()
            if "deviation_amount" in audit_df.columns
            else 0
        )
        lines.append(f"总偏差金额：{total:,.0f}")
        return "\n".join(lines)


class DashboardDialog(QDialog):
    """管理看板主对话框"""

    drill_down_signal = Signal(str, str)  # (维度类型, 维度值)

    def __init__(self, audit_df, material_df, parent=None):
        super().__init__(parent)
        self.audit_df = audit_df
        self.material_df = material_df
        self.analysis_result = None
        self._init_ui()
        self._start_analysis()

    def _init_ui(self):
        self.setWindowTitle("管理看板")
        self.setMinimumSize(1000, 700)
        layout = QVBoxLayout(self)
        # 顶部工具栏
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("维度："))
        self.dim_combo = QComboBox()
        self.dim_combo.addItems(["车间", "物料大类", "时间趋势"])
        self.dim_combo.currentTextChanged.connect(self._on_dim_changed)
        top_bar.addWidget(self.dim_combo)
        top_bar.addStretch()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._start_analysis)
        top_bar.addWidget(self.refresh_btn)
        layout.addLayout(top_bar)
        # Tab 页
        self.tabs = QTabWidget()
        self.tab_rank = QWidget()
        self.tab_trend = QWidget()
        self.tab_summary = QWidget()
        self.tabs.addTab(self.tab_rank, "排名")
        self.tabs.addTab(self.tab_trend, "趋势")
        self.tabs.addTab(self.tab_summary, "小结")
        layout.addWidget(self.tabs)
        # 排名页
        self._init_rank_tab()
        # 趋势页
        self._init_trend_tab()
        # 小结页
        self._init_summary_tab()
        # 关闭按钮
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

    def _init_rank_tab(self):
        layout = QVBoxLayout(self.tab_rank)
        # 图表区
        self.rank_fig = Figure(figsize=(6, 4), dpi=100)
        self.rank_canvas = FigureCanvas(self.rank_fig)
        self.rank_toolbar = NavigationToolbar(self.rank_canvas, self)
        layout.addWidget(self.rank_toolbar)
        layout.addWidget(self.rank_canvas)
        # 表格区
        self.rank_table = QTableWidget()
        layout.addWidget(self.rank_table)

    def _init_trend_tab(self):
        layout = QVBoxLayout(self.tab_trend)
        self.trend_fig = Figure(figsize=(6, 4), dpi=100)
        self.trend_canvas = FigureCanvas(self.trend_fig)
        self.trend_toolbar = NavigationToolbar(self.trend_canvas, self)
        layout.addWidget(self.trend_toolbar)
        layout.addWidget(self.trend_canvas)

    def _init_summary_tab(self):
        layout = QVBoxLayout(self.tab_summary)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        layout.addWidget(self.summary_text)
        self.ai_btn = QPushButton("AI 归因分析")
        self.ai_btn.clicked.connect(self._on_ai_analysis)
        layout.addWidget(self.ai_btn)

    def _start_analysis(self):
        self.worker = AnalysisWorker(self.audit_df, self.material_df)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.thread.start()

    def _on_analysis_done(self, result):
        self.analysis_result = result
        self._update_rank_tab(result)
        self._update_trend_tab(result)
        self._update_summary_tab(result)
        self.thread.quit()
        self.thread.wait()

    def _on_analysis_error(self, msg):
        QMessageBox.critical(self, "分析错误", msg)
        self.thread.quit()
        self.thread.wait()

    def _update_rank_tab(self, result):
        dim = self.dim_combo.currentText()
        self.rank_fig.clear()
        ax = self.rank_fig.add_subplot(111)
        if dim == "车间":
            sr = result["workshop_rank"]
        elif dim == "物料大类":
            sr = result["material_group_rank"]
        else:
            sr = pd.Series(dtype=float)
        if not sr.empty:
            sr.head(10).plot(kind="bar", ax=ax)
            ax.set_ylabel("偏差金额")
            ax.set_title(f"{dim}排名TOP10")
        else:
            ax.text(0.5, 0.5, "无数据", ha="center", va="center")
        self.rank_canvas.draw()
        # 表格
        self.rank_table.setRowCount(len(sr))
        self.rank_table.setColumnCount(2)
        self.rank_table.setHorizontalHeaderLabels(["名称", "偏差金额"])
        for i, (name, val) in enumerate(sr.items()):
            self.rank_table.setItem(i, 0, QTableWidgetItem(str(name)))
            self.rank_table.setItem(i, 1, QTableWidgetItem(f"{val:,.0f}"))

    def _update_trend_tab(self, result):
        self.trend_fig.clear()
        ax = self.trend_fig.add_subplot(111)
        trend = result["trend"]
        if not trend.empty:
            trend.plot(ax=ax, marker="o")
            ax.set_ylabel("偏差金额")
            ax.set_title("时间趋势")
        else:
            ax.text(0.5, 0.5, "无数据", ha="center", va="center")
        self.trend_canvas.draw()

    def _update_summary_tab(self, result):
        self.summary_text.setPlainText(result["summary"])

    def _on_dim_changed(self, text):
        if self.analysis_result:
            self._update_rank_tab(self.analysis_result)

    def _on_ai_analysis(self):
        QMessageBox.information(self, "AI 归因", "AI 归因分析功能开发中...")

    def get_analysis_result(self):
        return self.analysis_result
