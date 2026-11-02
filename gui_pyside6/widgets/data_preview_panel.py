# -*- coding: utf-8 -*-
"""
下拉预览面板 - 快速了解数据详情

主要功能：
- 行数据预览
- 统计信息展示
- 关联信息查看
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QGroupBox, QFormLayout, QScrollArea, QSplitter, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

import pandas as pd


# 当前预览的数据行
current_preview_row = None


class DataViewWidget(QWidget):
    """数据视图组件"""
    
    selected = Signal(int)  # 行索引被选中
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 头部统计卡片
        header_layout = QHBoxLayout()
        
        self.stat_card = QGroupBox("数据统计")
        stat_layout = QFormLayout(self.stat_card)
        
        self.stat_fields = [
            ('工厂', ''), ('车间', ''), ('物料名称', ''),
            ('实际', ''), ('备注', ''), ('偏差率', ''),
            ('审核状态', ''), ('已读状态', '')
        ]
        
        self.stat_labels = {}
        for field, default in self.stat_fields:
            label = QLabel(default)
            label.setStyleSheet("""
                QLabel {
                    color: #6B7280;
                    font-size: 13px;
                }
            """)
            self.stat_labels[field] = label
            stat_layout.addRow(field + ":", label)
        
        header_layout.addWidget(self.stat_card)
        
        # 添加预览按钮
        self.btn_preview = QPushButton("📊 下拉预览")
        self.btn_preview.setMinimumWidth(150)
        self.btn_preview.setStyleSheet("""
            QPushButton {
                background-color: #262521;
                color: white;
                padding: 10px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3a3935;
            }
        """)
        header_layout.addWidget(self.btn_preview)
        
        layout.addLayout(header_layout)
        
        # 主区域
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧数据详情
        left_panel = QGroupBox("数据详情")
        left_layout = QVBoxLayout(left_panel)
        
        # 全屏文本预览
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.text_preview.setFont(QFont("Consolas", 10))
        
        left_layout.addWidget(self.text_preview)
        
        splitter.addWidget(left_panel)
        
        # 右侧时间线/操作历史
        right_panel = QGroupBox("审核历史记录")
        right_layout = QVBoxLayout(right_panel)
        
        self.time_line_edit = QTextEdit()
        self.time_line_edit.setReadOnly(True)
        self.time_line_edit.setMaximumWidth(300)
        
        right_layout.addWidget(self.time_line_edit)
        
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 300])
        layout.addWidget(splitter)
        
        # 连接信号
        self.btn_preview.clicked.connect(self.on_preview_clicked)
    
    def set_data(self, row):
        """
        设置当前显示的数据行
        :param row: 数据行（DataFrame row）
        """
        global current_preview_row
        current_preview_row = row
        
        # 更新统计信息
        self._update_stats(row)
        
        # 更新文本预览
        self._update_text_preview(row)
    
    def _update_stats(self, row):
        """更新统计信息"""
        for field, label in self.stat_labels.items():
            if field in row.index:
                value = row[field]
                # 特殊处理
                if field == '偏差率' and pd.notna(value):
                    value = f"{float(value)*100:.2f}%"
                label.setText(str(value))
                label.setStyleSheet("""
                    QLabel {
                        color: #4B5563;
                        font-size: 14px;
                        font-weight: 500;
                    }
                """)
            else:
                label.setText("-")
    
    def _update_text_preview(self, row):
        """更新文本预览"""
        # 转换为 JSON 格式的 JSON 字符串
        import json
        row_dict = row.to_dict()
        
        # 格式化数值
        for key, value in row_dict.items():
            if isinstance(value, (int, float)):
                row_dict[key] = f"{value:.4f}"
            elif pd.isna(value):
                row_dict[key] = None
        
        text = json.dumps(row_dict, indent=2, ensure_ascii=False)
        self.text_preview.setPlainText(text)
    
    def on_preview_clicked(self):
        """预览按钮被点击"""
        if current_preview_row is None:
            return
        
        # 获取审核历史记录
        from gui_pyside6.services.audit_service import audit_service
        data_id = current_preview_row['data_id']
        history = audit_service.get_audit_history(data_id)
        
        # 更新时间线
        if history:
            timeline_text = "审核时间线:\n"
            for log in history:
                timeline_text += f"{log['time']}: {log['comment']}\n"
        else:
            timeline_text = "暂无审核记录"
        
        self.time_line_edit.setPlainText(timeline_text)


class DataPreviewService:
    """数据预览服务"""
    
    def __init__(self):
        self.preview_widgets = {}
    
    def create_preview_widget(self, data_id: str) -> DataViewWidget:
        """创建预览部件"""
        widget = DataViewWidget()
        widget.dataset_id = data_id  # type: ignore
        self.preview_widgets[data_id] = widget
        return widget


# 全局实例
data_preview_service = DataPreviewService()
