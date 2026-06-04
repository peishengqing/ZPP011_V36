# -*- coding: utf-8 -*-
"""
历史对比对话框 (PySide6 版本)
支持选择两次历史分析，对比总行数、偏差率分布、审核完成率、备注填写率等
"""
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal

# history_db 模块需在 core/ 目录下存在
try:
    from core import history_db
except ImportError:
    history_db = None


class LoadHistoryWorker(QThread):
    """加载历史数据的工作线程"""
    finished = Signal(object, int)   # (DataFrame, analysis_id)
    error = Signal(str)

    def __init__(self, analysis_id, db_path):
        super().__init__()
        self.analysis_id = analysis_id
        self.db_path = db_path

    def run(self):
        try:
            if history_db is None:
                raise RuntimeError("history_db 模块未找到")
            df = history_db.get_analysis_data(self.analysis_id, db_path=self.db_path)
            self.finished.emit(df, self.analysis_id)
        except Exception as e:
            self.error.emit(str(e))


class HistoryCompareDialog(QDialog):
    def __init__(self, parent, db_path=None):
        super().__init__(parent)
        self.setWindowTitle("历史对比")
        self.resize(900, 600)
        self.db_path = db_path
        self.records = []
        self.left_df = None
        self.right_df = None
        self.left_id = None
        self.right_id = None

        self._build_ui()
        self._load_history_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 选择区域
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("对比左侧:"))
        self.left_combo = QComboBox()
        self.left_combo.setMinimumWidth(300)
        self.left_combo.currentIndexChanged.connect(self._on_left_selected)
        select_layout.addWidget(self.left_combo)

        select_layout.addWidget(QLabel("对比右侧:"))
        self.right_combo = QComboBox()
        self.right_combo.setMinimumWidth(300)
        self.right_combo.currentIndexChanged.connect(self._on_right_selected)
        select_layout.addWidget(self.right_combo)

        self.compare_btn = QPushButton("对比")
        self.compare_btn.clicked.connect(self._do_compare)
        select_layout.addWidget(self.compare_btn)
        layout.addLayout(select_layout)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # 结果标签页
        self.tab_widget = QTabWidget()
        self.result_table = QTableWidget()   # 指标对比表格
        self.tab_widget.addTab(self.result_table, "指标对比")
        self.detail_table = QTableWidget()   # 明细对比（暂不支持）
        self.tab_widget.addTab(self.detail_table, "明细对比（暂不支持）")
        layout.addWidget(self.tab_widget)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _load_history_list(self):
        """加载历史记录列表"""
        try:
            if history_db is None:
                QMessageBox.warning(self, "提示", "history_db 模块未加载，无法读取历史记录")
                self.left_combo.addItem("无数据")
                self.right_combo.addItem("无数据")
                return

            self.records = history_db.get_analysis_list(db_path=self.db_path, limit=50)
            if not self.records:
                QMessageBox.warning(self, "提示", "无历史分析记录")
                self.left_combo.addItem("无数据")
                self.right_combo.addItem("无数据")
                return

            self.left_combo.clear()
            self.right_combo.clear()
            for rec in self.records:
                display = f"{rec['id']}: {rec['timestamp'][:16]} - {rec['file_name']}"
                self.left_combo.addItem(display, rec['id'])
                self.right_combo.addItem(display, rec['id'])

            # 默认选择最近两条
            if len(self.records) >= 2:
                self.left_combo.setCurrentIndex(1)    # 倒数第二条
                self.right_combo.setCurrentIndex(0)   # 最新一条
            elif len(self.records) == 1:
                self.left_combo.setCurrentIndex(0)
                self.right_combo.setCurrentIndex(0)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载历史记录失败: {e}")

    def _on_left_selected(self, idx):
        if idx >= 0:
            self.left_id = self.left_combo.currentData()

    def _on_right_selected(self, idx):
        if idx >= 0:
            self.right_id = self.right_combo.currentData()

    def _do_compare(self):
        if self.left_id is None or self.right_id is None:
            QMessageBox.warning(self, "提示", "请选择两个历史记录")
            return
        if self.left_id == self.right_id:
            QMessageBox.warning(self, "提示", "请选择不同的历史记录")
            return

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)   # 不确定进度
        self.compare_btn.setEnabled(False)

        # 使用工作线程加载左侧数据
        self.left_worker = LoadHistoryWorker(self.left_id, self.db_path)
        self.left_worker.finished.connect(self._on_left_loaded)
        self.left_worker.error.connect(self._on_load_error)
        self.left_worker.start()

    def _on_left_loaded(self, df, aid):
        self.left_df = df
        self.left_id = aid
        # 加载右侧数据
        self.right_worker = LoadHistoryWorker(self.right_id, self.db_path)
        self.right_worker.finished.connect(self._on_right_loaded)
        self.right_worker.error.connect(self._on_load_error)
        self.right_worker.start()

    def _on_right_loaded(self, df, aid):
        self.right_df = df
        self.right_id = aid
        self.progress.setVisible(False)
        self.compare_btn.setEnabled(True)
        self._show_comparison()

    def _on_load_error(self, err):
        self.progress.setVisible(False)
        self.compare_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"加载历史数据失败: {err}")

    def _show_comparison(self):
        """计算并显示对比指标"""
        left_metrics = self._calculate_metrics(self.left_df)
        right_metrics = self._calculate_metrics(self.right_df)

        headers = ["指标", "左侧", "右侧", "变化"]
        self.result_table.setColumnCount(len(headers))
        self.result_table.setHorizontalHeaderLabels(headers)
        self.result_table.horizontalHeader().setStretchLastSection(True)

        rows = []
        all_keys = sorted(set(list(left_metrics.keys()) + list(right_metrics.keys())))
        for key in all_keys:
            left_val = left_metrics.get(key, 0)
            right_val = right_metrics.get(key, 0)
            if isinstance(left_val, (int, float)) and isinstance(right_val, (int, float)):
                change = right_val - left_val
                change_str = f"{change:+,.0f}" if isinstance(change, (int, float)) else "N/A"
                left_str = f"{left_val:,.0f}"
                right_str = f"{right_val:,.0f}"
            else:
                change_str = "N/A"
                left_str = str(left_val)
                right_str = str(right_val)
            rows.append([key, left_str, right_str, change_str])

        self.result_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if j == 3 and isinstance(val, str):
                    if val.startswith('-'):
                        item.setForeground(Qt.red)
                    elif val.startswith('+'):
                        item.setForeground(Qt.green())
                self.result_table.setItem(i, j, item)
        self.result_table.resizeColumnsToContents()

    def _calculate_metrics(self, df):
        """从 DataFrame 计算关键指标"""
        if df is None or df.empty:
            return {}
        metrics = {}
        metrics['总记录数'] = len(df)

        # 偏差率分布
        rate_col = None
        for col in ['偏差率(%)', '偏差率', 'dev_rate']:
            if col in df.columns:
                rate_col = col
                break
        if rate_col:
            rates = pd.to_numeric(df[rate_col], errors='coerce')
            metrics['偏差>10%行数'] = int((rates.abs() > 10).sum())
            metrics['偏差5-10%行数'] = int(((rates.abs() > 5) & (rates.abs() <= 10)).sum())

        # 审核完成率
        status_col = None
        for col in ['审核状态', 'audit_status']:
            if col in df.columns:
                status_col = col
                break
        if status_col:
            metrics['已审核行数'] = int((df[status_col] == '已审核').sum())
        elif 'audit_result' in df.columns:
            metrics['已审核行数'] = int(df['audit_result'].notna().sum())

        # 备注填写率
        remark_col = None
        for col in ['备注原因', '备注', 'remark']:
            if col in df.columns:
                remark_col = col
                break
        if remark_col:
            metrics['已填备注行数'] = int(df[remark_col].notna().sum())

        # 替代料相关
        if '替代料' in df.columns:
            metrics['替代料行数'] = int((df['替代料'] == '是').sum())

        return metrics
