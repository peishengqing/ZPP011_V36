# -*- coding: utf-8 -*-
"""
审核统计桌面卡片 — 4张卡片显示本批次核心指标
纯信息展示，不涉及操作入口
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QLabel, QSizePolicy, QToolButton,
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QFont
import pandas as pd


def _make_card(parent, value_text, label_text, color: str, tooltip: str) -> QFrame:
    """创建单张卡片"""
    card = QFrame(parent)
    card.setObjectName("statsCard")
    card.setProperty("class", "statsCard")
    card.setToolTip(tooltip)
    card.setCursor(Qt.PointingHandCursor)
    card.setMinimumWidth(120)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(2)

    val_label = QLabel(str(value_text))
    val_label.setProperty("class", "statsCardVal")
    val_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(val_label)

    desc_label = QLabel(label_text)
    desc_label.setProperty("class", "statsCardDesc")
    desc_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(desc_label)

    return card


class StatsCardsWidget(QWidget):
    """4 张统计卡片：AI通过率 / 未读 / 真异常 / 替代料"""

    # 点击某张卡片时发出的信号，携带卡片标识
    card_clicked = Signal(str)  # "anomaly" | "unread" | "alt" | "changed" | "quarantine"
    # 面板整体显隐变化（True=显示, False=隐藏）
    visibility_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_hidden = False  # 用户手动折叠卡片区
        self.setVisible(False)  # 初始隐藏，有数据再显示
        self._build_ui()
        self._click_card = None  # 记录哪个卡片被点击

    def _build_ui(self):
        self.setObjectName("statsCardsWidget")

        # ── 标题栏 ──
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(4, 0, 4, 0)

        title = QLabel("📊 本次分析概览")
        title.setProperty("class", "statsCardTitle")
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 折叠/显示按钮
        self.toggle_btn = QToolButton(self)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.setText("隐藏")
        self.toggle_btn.setToolTip("隐藏本次分析概览卡片")
        self.toggle_btn.setStyleSheet("QToolButton { border: none; color: #666; font-size: 12px; padding: 2px 6px; }\n"
                                      "QToolButton:hover { color: #333; background: #eee; }")
        self.toggle_btn.toggled.connect(self._toggle_cards)
        title_layout.addWidget(self.toggle_btn)

        # ── 卡片区 ──
        self.cards_container = QWidget(self)
        self.cards_container.setObjectName("statsCardsContainer")
        cards_layout = QHBoxLayout(self.cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)
        cards_layout.setAlignment(Qt.AlignLeft)

        # 4 张卡片
        self.card_pass = _make_card(self, "--", "AI通过", "#4caf50",
                                     "AI审核结果为「合格」的占比")
        self.card_unread = _make_card(self, "--", "未读", "#ff9800",
                                       "你还没看过的记录数")
        self.card_anomaly = _make_card(self, "--", "真异常", "#f44336",
                                        "非替代料中偏差率 > 30% 的条数")
        self.card_alt = _make_card(self, "--", "替代料", "#9c27b0",
                                    "替代料配对组数 + 净偏差抵消总金额")
        self.card_changed = _make_card(self, "--", "审核后变更", "#e53935",
                                        "已审核记录被私自修改的次数（数量/金额/率变动）")
        self.card_quarantine = _make_card(self, "--", "隔离区", "#f9a825",
                                           "疑难待处理、暂存隔离区的数据条数（点击仅显示隔离行）")

        # 给可点击的卡片安装事件过滤器
        self.card_anomaly.installEventFilter(self)
        self.card_anomaly.setProperty("cardType", "anomaly")
        self.card_unread.installEventFilter(self)
        self.card_unread.setProperty("cardType", "unread")
        self.card_changed.installEventFilter(self)
        self.card_changed.setProperty("cardType", "changed")
        self.card_quarantine.installEventFilter(self)
        self.card_quarantine.setProperty("cardType", "quarantine")

        cards_layout.addWidget(self.card_pass)
        cards_layout.addWidget(self.card_unread)
        cards_layout.addWidget(self.card_anomaly)
        cards_layout.addWidget(self.card_alt)
        cards_layout.addWidget(self.card_changed)
        cards_layout.addWidget(self.card_quarantine)
        cards_layout.addStretch()

        # ── 组装 ──
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 2)
        main_layout.setSpacing(4)
        main_layout.addLayout(title_layout)
        main_layout.addWidget(self.cards_container)

    def _toggle_cards(self, visible):
        """标题栏隐藏按钮：点击隐藏后整个面板消失"""
        self._user_hidden = not visible
        self.cards_container.setVisible(visible)
        self.toggle_btn.setText("隐藏" if visible else "显示")
        self.toggle_btn.setToolTip("隐藏本次分析概览卡片" if visible else "显示本次分析概览卡片")
        self.setVisible(visible)
        self.visibility_changed.emit(visible)

    def show_panel(self):
        """外部调用：显示整个概览面板"""
        self._user_hidden = False
        self.cards_container.setVisible(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.setText("隐藏")
        self.toggle_btn.setToolTip("隐藏本次分析概览卡片")
        self.setVisible(True)
        self.visibility_changed.emit(True)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            card_type = obj.property("cardType")
            if card_type:
                self.card_clicked.emit(card_type)
                return True
        return super().eventFilter(obj, event)

    # ── 公开方法 ──

    def refresh(self, df: pd.DataFrame):
        """根据 DataFrame 刷新所有卡片统计；用户手动隐藏后保持隐藏"""
        if df is None or df.empty:
            self.setVisible(False)
            self.visibility_changed.emit(False)
            return

        # 始终更新数值，再按用户隐藏状态决定是否展示
        self._update_pass_rate(df)
        self._update_unread(df)
        self._update_anomaly(df)
        self._update_alt(df)
        self._update_changed(df)
        self._update_quarantine(df)

        self.setVisible(not self._user_hidden)
        self.cards_container.setVisible(not self._user_hidden)
        self.toggle_btn.setChecked(not self._user_hidden)
        self.toggle_btn.setText("隐藏" if not self._user_hidden else "显示")
        self.toggle_btn.setToolTip("隐藏本次分析概览卡片" if not self._user_hidden else "显示本次分析概览卡片")
        self.visibility_changed.emit(not self._user_hidden)

    # ── 内部计算 ──

    def _update_pass_rate(self, df: pd.DataFrame):
        """AI通过率：audit_result == '合格' / 有审核结果的记录数"""
        if 'audit_result' not in df.columns:
            self._set_card_value(self.card_pass, "--")
            return
        # 已审核且audit_result非空
        result_col = '审核结果' if '审核结果' in df.columns else 'audit_result'
        reviewed = df[df[result_col].notna() & (df[result_col].astype(str).str.strip() != '')]
        if reviewed.empty:
            self._set_card_value(self.card_pass, "--")
            return
        pass_count = (reviewed[result_col].astype(str).str.strip() == '合格').sum()
        rate = pass_count / len(reviewed) * 100
        self._set_card_value(self.card_pass, f"{rate:.0f}%")

    def _update_unread(self, df: pd.DataFrame):
        """未读：_read 列为 0 或不存在该列的记录数"""
        if '_read' not in df.columns:
            self._set_card_value(self.card_unread, str(len(df)))
            return
        unread = (df['_read'] == 0).sum()
        self._set_card_value(self.card_unread, str(unread))

    def _update_anomaly(self, df: pd.DataFrame):
        """真异常：非替代料 且 |偏差率| > 30% 的条数"""
        # 替代料列探测
        alt_col = None
        for col in ['是否替代料', 'is_alt', '_替代料组', '替代料组']:
            if col in df.columns:
                alt_col = col
                break

        # 偏差率列探测
        rate_col = None
        for col in ['偏差率(%)', '偏差率', 'dev_rate']:
            if col in df.columns:
                rate_col = col
                break

        if rate_col is None:
            self._set_card_value(self.card_anomaly, "--")
            return

        rates = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)

        if alt_col and alt_col in df.columns and alt_col in ['是否替代料', 'is_alt']:
            # 布尔/字符串型替代料标记
            is_alt = df[alt_col].astype(str).str.strip().isin(['是', 'True', 'true', '1'])
            anomaly = (~is_alt) & (rates.abs() > 30)
        elif alt_col and alt_col in ['_替代料组', '替代料组']:
            # 替代料组非空 = 是替代料
            has_alt = df[alt_col].notna() & (df[alt_col].astype(str).str.strip() != '')
            anomaly = (~has_alt) & (rates.abs() > 30)
        else:
            # 没有替代料列，全部算进去
            anomaly = rates.abs() > 30

        self._set_card_value(self.card_anomaly, str(int(anomaly.sum())))

    def _update_alt(self, df: pd.DataFrame):
        """替代料：组数 + 净偏差抵消金额"""
        group_col = None
        for col in ['_替代料组', '替代料组']:
            if col in df.columns:
                group_col = col
                break

        if group_col is None or group_col not in df.columns:
            self._set_card_value(self.card_alt, "0组")
            return

        groups = df[df[group_col].notna() & (df[group_col].astype(str).str.strip() != '')]
        if groups.empty:
            self._set_card_value(self.card_alt, "0组")
            return

        n_groups = groups[group_col].nunique()

        # 净偏差金额
        amt_col = None
        for col in ['净偏差金额', '偏差金额(含税)', '偏差金额']:
            if col in df.columns:
                amt_col = col
                break

        if amt_col and amt_col in groups.columns:
            total = pd.to_numeric(groups[amt_col], errors='coerce').fillna(0).sum()
            text = f"{n_groups}组"
            if abs(total) >= 10000:
                text += f"  ¥{total / 10000:.1f}万"
            elif abs(total) >= 1:
                text += f"  ¥{total:.0f}"
            else:
                text += f"  ¥{total:.2f}"
        else:
            text = f"{n_groups}组"

        self._set_card_value(self.card_alt, text)

    def _update_changed(self, df: pd.DataFrame):
        """审核后变更：_post_audit_changed 列为 1 的条数"""
        if '_post_audit_changed' not in df.columns:
            self._set_card_value(self.card_changed, "--")
            return
        cnt = int((df['_post_audit_changed'] == 1).sum())
        self._set_card_value(self.card_changed, str(cnt) if cnt else "0")

    def _update_quarantine(self, df: pd.DataFrame):
        """隔离区：_quarantined 列为 1 的条数"""
        if '_quarantined' not in df.columns:
            self._set_card_value(self.card_quarantine, "--")
            return
        cnt = int((df['_quarantined'] == 1).sum())
        self._set_card_value(self.card_quarantine, str(cnt) if cnt else "0")

    @staticmethod
    def _set_card_value(card: QFrame, text: str):
        """设置卡片的值文本（第一个 QLabel）"""
        layout = card.layout()
        if layout and layout.count() > 0:
            label = layout.itemAt(0).widget()
            if isinstance(label, QLabel):
                label.setText(str(text))
