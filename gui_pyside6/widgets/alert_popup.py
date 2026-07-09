# -*- coding: utf-8 -*-
"""
预警通知弹窗
非模态，显示超阈值偏差提醒，可跳转查看详情
裴哥 | 2026-06-04
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QEventLoop
from PySide6.QtGui import QFont, QPalette, QColor


class AlertPopup(QWidget):
    """非模态预警通知弹窗"""

    def __init__(self, alerts_df, parent=None):
        super().__init__(parent)
        self.alerts_df = alerts_df
        self.parent = parent

        # 窗口属性：无边框 + 置顶 + 工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(400, 280)
        self._set_stylesheet()

        self._setup_ui()
        self._move_to_bottom_right()
        self._start_auto_close()

    def _set_stylesheet(self):
        self.setObjectName("alertPopup")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title = QLabel("⚠️ 新预警通知")
        title.setObjectName("title")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel(f"发现 {len(self.alerts_df)} 条新超阈值偏差")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # 明细（最多显示5条）
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(120)
        self.detail.setObjectName("alertDetail")
        lines = []
        cols = [c for c in ['物料编码', '物料名称', '偏差率(%)', '偏差率'] if c in self.alerts_df.columns]
        rate_col = '偏差率(%)' if '偏差率(%)' in self.alerts_df.columns else ('偏差率' if '偏差率' in self.alerts_df.columns else None)
        net_rate_col = '净偏差率(%)' if '净偏差率(%)' in self.alerts_df.columns else ('净偏差率' if '净偏差率' in self.alerts_df.columns else None)
        for _, row in self.alerts_df.head(5).iterrows():
            code = row.get('物料编码', '')
            name = row.get('物料名称', '')
            rate = row[rate_col] if rate_col else ''
            net_rate = row[net_rate_col] if net_rate_col else ''
            lines.append(f"• {code} {name}  偏差率: {rate}%  净偏差率: {net_rate}%")
        self.detail.setPlainText("\n".join(lines))
        layout.addWidget(self.detail)

        # 按钮行
        btn_layout = QHBoxLayout()
        detail_btn = QPushButton("查看详情")
        detail_btn.clicked.connect(self._show_detail)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(detail_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _move_to_bottom_right(self):
        """移动到屏幕右下角"""
        screen = self.screen()
        if screen:
            sg = screen.availableGeometry()
            x = sg.x() + sg.width() - self.width() - 20
            y = sg.y() + sg.height() - self.height() - 60
            self.move(x, y)

    def _start_auto_close(self):
        """15 秒后自动关闭"""
        QTimer.singleShot(15000, self.close)

    def _show_detail(self):
        """跳转主窗口对应行（高亮超阈值行）"""
        if self.parent and hasattr(self.parent, 'table_view'):
            # 先切换到第一页（如果有分页）
            # 直接把超阈值的行筛选出来
            try:
                rate_col = next(
                    (c for c in ['偏差率(%)', '偏差率'] if c in self.alerts_df.columns),
                    None
                )
                if rate_col and self.parent.audit_data is not None:
                    threshold = 10  # 和 AlertMonitor 默认阈值一致
                    highlight = self.parent.audit_data[
                        self.parent.audit_data[rate_col].abs() > threshold
                    ].index
                    # 选中第一行
                    if not highlight.empty:
                        idx = self.parent.proxy_model.mapFromSource(
                            self.parent.source_model.index(highlight[0], 0)
                        )
                        if idx.isValid():
                            self.parent.table_view.selectRow(idx.row())
                            self.parent.table_view.scrollTo(idx)
            except Exception:
                pass
        self.close()
