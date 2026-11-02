# -*- coding: utf-8 -*-
"""
AI 归因摘要面板（v1）
在审核对话框中展示相似案例和历史高频原因。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QScrollArea, QGroupBox, QPushButton
)
from PySide6.QtCore import Signal, Qt

from core.ai_reason_analyzer import AIReasonAnalyzer


class AIReasonPanel(QDialog):
    """AI 归因摘要面板"""

    # 信号：用户选择了一个原因
    reason_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.analyzer = AIReasonAnalyzer()
        self.setWindowTitle("AI 归因摘要")
        self.setMinimumSize(400, 500)

        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 基本信息标签
        self.info_label = QLabel("选择一条记录以显示历史原因")
        self.info_label.setStyleSheet("font-size: 12px; color: #666; padding: 10px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # 相似案例列表
        self.similar_list = QListWidget()
        self.similar_list.itemClicked.connect(self._on_similar_selected)
        layout.addWidget(self.similar_list)

        # 高频原因列表
        high_freq_group = QGroupBox("该物料的高频原因")
        high_freq_layout = QVBoxLayout(high_freq_group)
        self.high_freq_list = QListWidget()
        high_freq_layout.addWidget(self.high_freq_list)
        layout.addWidget(high_freq_group)

        # 重置按钮
        reset_btn = QPushButton("重置查询")
        reset_btn.clicked.connect(self._reset)
        reset_btn.setObjectName("secondaryBtn")
        layout.addWidget(reset_btn)

        # 设置边框和间距
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

    def set_context(self, material_code: str, factory: str, workshop: str):
        """设置上下文参数"""
        self.material_code = material_code
        self.factory = factory
        self.workshop = workshop
        self._load_history()

    def _load_history(self):
        """加载历史数据"""
        if not hasattr(self, 'material_code'):
            self.info_text = "未设置上下文参数"
            self.info_label.text(self.info_text)
            return

        # 加载相似案例
        cases = self.analyzer.get_similar_cases(
            self.material_code, self.factory, self.workshop
        )
        self.similar_list.clear()
        for case in cases:
            item = QListWidgetItem(
                f"{case['reason']} (出现 {case['count']} 次，最近 {case['last_seen']})"
            )
            item.setData(Qt.UserRole, case['reason'])
            self.similar_list.addItem(item)

        # 加载高频原因
        reasons = self.analyzer.get_top_reasons_for_material(self.material_code)
        self.high_freq_list.clear()
        for reason in reasons:
            self.high_freq_list.addItem(reason)

        # 设置说明文本
        self.info_label.setText(
            f"物料 {self.material_code} 在 {self.workshop} 的历史原因："
        )

    def _on_similar_selected(self, item):
        """点击相似案例"""
        reason = item.data(Qt.UserRole)
        self.reason_selected.emit(reason)

    def _reset(self):
        """重置查询"""
        self._load_history()
