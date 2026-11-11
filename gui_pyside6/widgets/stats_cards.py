# -*- coding: utf-8 -*-
"""审核概览 KPI 带 — v43.349 第五期D：照抄设计稿 `.kpi-bar`。

设计稿的概览不是「标题行 + 一排圆角卡片」，而是一根 54px 的等高带：
- 7 格等宽平铺（min-width 118px），格间 1px 竖线，整条带只有下边框，无圆角无边框；
- 每格上行「6px 语义圆点 + 11px 灰标签」，下行「等宽字体数值 + 11px 灰单位」；
- 可点的格右端一枚朝右小三角（CSS 用 ::after，Qt 换成 10px 线性图标）。

「本次分析概览」标题行连同里面的「隐藏」按钮一起删除：概览显隐早在操作栏
（v43.349 第五期B 把「概览」请回视图开关位），带内再放一颗是重复入口。
纯信息展示，不涉及操作入口。
"""
import re

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QEvent
import pandas as pd

from gui_pyside6.themes.tokens import SIZE_PX
from gui_pyside6.utils.icons import get_icon
from utils.theme_manager import Thm
from core import threshold_config as _thr

# 圆点取色（pass/unread/anomaly/alt/changed/quarantine/deviation 七键）的唯一权威
# 在两套 QSS 的 QFrame[kpiAccent="..."] 规则，此处只传键，零内联样式。
# 语义对应设计稿：通过率=ok、未读=info、真异常=danger、替代料=violet、
# 审核后变更=warn、隔离区=textFaint、偏差率预警=warn。

_VALUE_RE = re.compile(r"^([-+]?\d[\d,.]*)(.*)$")


def _split_value(text: str):
    """把「92%」「24组  ¥1.2万」拆成数值主体与单位尾巴（设计稿 small 的那截）。"""
    m = _VALUE_RE.match(text)
    if not m:
        return text, ""
    return m.group(1), " ".join(m.group(2).split())


def _make_card(parent, value_text, label_text, accent: str, tooltip: str) -> QFrame:
    """创建单格 KPI（上行圆点+标签，下行数值+单位，右端可点三角）。"""
    card = QFrame(parent)
    card.setObjectName("statsCard")
    card.setToolTip(tooltip)
    card.setMinimumWidth(118)  # 设计稿 .kpi{min-width:118px}
    # 高度不设最小值：整条带固定 54px（StatsCardsWidget.setFixedHeight），
    # 不存在被压扁的空间了 —— 旧版 52px 兜底是给会随表格伸缩的卡片用的。
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    # QSS 的 hover 底色要生效必须开 styled background，否则 hover 规则画不出来
    card.setAttribute(Qt.WA_StyledBackground, True)

    # 外层横向：左边内容列吃满，右边三角垂直居中（对应 ::after 的 top:50%）
    row = QHBoxLayout(card)
    # 设计稿 .kpi{padding:7px 12px 8px}；上下收 1px 是因为 Qt 的字体行高比 CSS
    # line-height 胖，54px 带（含 1px 下边框）里按 7/8 排会把数字裁掉一截。
    row.setContentsMargins(12, 6, 12, 6)
    row.setSpacing(4)

    col = QVBoxLayout()
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(1)  # .kpi-top{margin-bottom:1px}

    # 上行：6px 圆点 + 11px 标签
    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(5)  # .kpi-top{gap:5px}
    dot = QFrame(card)
    dot.setObjectName("kpiDot")
    dot.setProperty("kpiAccent", accent)
    dot.setFixedSize(6, 6)
    dot.setAttribute(Qt.WA_StyledBackground, True)
    top.addWidget(dot, 0, Qt.AlignVCenter)
    name_label = QLabel(label_text, card)
    name_label.setObjectName("kpiLabel")
    top.addWidget(name_label, 0, Qt.AlignVCenter)
    top.addStretch(1)
    col.addLayout(top)

    # 下行：等宽数值 + 小号单位
    val_row = QHBoxLayout()
    val_row.setContentsMargins(0, 0, 0, 0)
    val_row.setSpacing(2)  # .kpi-val small{margin-left:2px}
    val_label = QLabel(card)
    val_label.setObjectName("kpiValue")
    unit_label = QLabel(card)
    unit_label.setObjectName("kpiUnit")
    val_row.addWidget(val_label, 0, Qt.AlignVCenter)
    val_row.addWidget(unit_label, 0, Qt.AlignVCenter)
    val_row.addStretch(1)
    col.addLayout(val_row)
    row.addLayout(col, 1)

    more = QLabel(card)
    more.setObjectName("kpiMore")
    more.setFixedSize(10, 10)
    more.setVisible(False)
    row.addWidget(more, 0, Qt.AlignVCenter)

    card._kpi_val = val_label
    card._kpi_unit = unit_label
    card._kpi_more = more
    _set_card_value(card, value_text)
    return card


def _set_card_value(card: QFrame, text: str):
    """写数值：主体进等宽大字标签，单位尾巴进小号灰标签。"""
    main, unit = _split_value(str(text))
    card._kpi_val.setText(main)
    card._kpi_unit.setText(unit)


class StatsCardsWidget(QWidget):
    """54px KPI 带：AI 通过率 / 未读 / 真异常 / 替代料 / 审核后变更 / 隔离区 / 偏差率预警"""

    # 点击某格时发出的信号，携带格子标识
    card_clicked = Signal(str)  # "anomaly" | "unread" | "changed" | "quarantine" | "deviation"
    # 整条带显隐变化（True=显示, False=隐藏）
    visibility_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_hidden = False  # 用户手动折叠概览
        self._marker_cards = []    # 带三角标记的可点格（主题切换时要重新取色）
        self.setVisible(False)  # 初始隐藏，有数据再显示
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("statsCardsWidget")
        self.setFixedHeight(SIZE_PX["boardKpiBar"])  # 设计稿 .kpi-bar{height:54px}

        # ── KPI 带（v43.349：格间 1px 竖线，不再用 8px 卡片间隙）──
        self.cards_container = QWidget(self)
        self.cards_container.setObjectName("statsCardsContainer")
        self.cards_container.setAttribute(Qt.WA_StyledBackground, True)
        band = QHBoxLayout(self.cards_container)
        band.setContentsMargins(0, 0, 0, 0)
        band.setSpacing(0)

        # 7 格（标签与顺序照抄设计稿，accent 键 → QSS 圆点色）
        self.card_pass = _make_card(self.cards_container, "--", "AI 通过率", "pass",
                                     "AI审核结果为「合格」的占比")
        self.card_unread = _make_card(self.cards_container, "--", "未读", "unread",
                                       "你还没看过的记录数")
        self.card_anomaly = _make_card(self.cards_container, "--", "真异常", "anomaly",
                                        "非替代料中 |偏差率| 超真异常阈值的条数（刷新时按当前阈值写进提示）")
        self.card_alt = _make_card(self.cards_container, "--", "替代料", "alt",
                                    "替代料配对组数 + 净偏差抵消总金额")
        self.card_changed = _make_card(self.cards_container, "--", "审核后变更", "changed",
                                        "已审核记录被私自修改的次数（数量/金额/率变动）")
        self.card_quarantine = _make_card(self.cards_container, "--", "隔离区", "quarantine",
                                           "疑难待处理、暂存隔离区的数据条数（点击打开隔离区）")
        self.card_deviation = _make_card(self.cards_container, "--", "偏差率预警", "deviation",
                                         "偏差率绝对值超预警阈值的记录数（点击打开偏差率预警看板；"
                                         "阈值在规则中心「阈值与提醒」，刷新时按当前值写进提示）")

        cards = [self.card_pass, self.card_unread, self.card_anomaly,
                 self.card_alt, self.card_changed, self.card_quarantine,
                 self.card_deviation]
        # 设计稿 .kpi{flex:1 1 0}：等宽平铺，最后一格不画右竖线
        for i, card in enumerate(cards):
            if i:
                sep = QFrame(self.cards_container)
                sep.setObjectName("kpiDivider")
                sep.setFixedWidth(1)
                band.addWidget(sep, 0)
            band.addWidget(card, 1)

        for card, key in ((self.card_anomaly, "anomaly"),
                          (self.card_unread, "unread"),
                          (self.card_changed, "changed"),
                          (self.card_quarantine, "quarantine"),
                          (self.card_deviation, "deviation")):
            self._mark_clickable(card, key)
        self._tint_markers()
        Thm.on_change(self._tint_markers)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.cards_container)

    def _mark_clickable(self, card: QFrame, card_type: str):
        """可点格：事件过滤器 + cardType + 手型 + 右端朝右三角（设计稿 .kpi.clickable）。"""
        card.installEventFilter(self)
        card.setProperty("cardType", card_type)
        card.setCursor(Qt.PointingHandCursor)
        card._kpi_more.setVisible(True)
        self._marker_cards.append(card)

    def _tint_markers(self, _dark=False):
        """三角标记取当前主题 textFaint 令牌（图标走 QPainter，吃不到 QSS）。"""
        pm = get_icon("chevron-right", 10, Thm.color("textFaint")).pixmap(10, 10)
        for card in self._marker_cards:
            card._kpi_more.setPixmap(pm)

    def _toggle_cards(self, visible):
        """操作栏「概览」开关：隐藏后整条带消失，高度全部让给表格"""
        self._user_hidden = not visible
        self.cards_container.setVisible(visible)
        self.setVisible(visible)
        self.visibility_changed.emit(visible)

    def show_panel(self):
        """外部调用：显示整条 KPI 带"""
        self._user_hidden = False
        self.cards_container.setVisible(True)
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
        """根据 DataFrame 刷新 KPI 带数值；用户手动隐藏后保持隐藏"""
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
        self._update_deviation(df)

        self.setVisible(not self._user_hidden)
        self.cards_container.setVisible(not self._user_hidden)
        self.visibility_changed.emit(not self._user_hidden)

    # ── 内部计算 ──

    def _update_pass_rate(self, df: pd.DataFrame):
        """AI 通过率：合格 / 已审核。判据（列探测 + 分母口径）在 threshold_config。

        改造前这里只认英文列 ``audit_result``，而「阈值与提醒」页的预览认
        ``审核结果``/``audit_result`` 两种 —— 于是同一张表里 KPI 说「--」、
        预览说「67%」。列探测统一交给 ``_thr.ai_pass_rate``。
        """
        rate = _thr.ai_pass_rate(df)
        if rate is None:
            _set_card_value(self.card_pass, "--")
            return
        floor = _thr.get_thresholds()["ai_pass_rate_min_pct"]
        # 低于下限时把「低于 xx%」挂在数值后面（KPI 带固定 54px，unit 位是唯一
        # 不加新样式就能表态的地方）；下限值来自「阈值与提醒」页，不是写死的 80
        _set_card_value(self.card_pass,
                        f"{rate:.0f}% 低于{floor:.0f}%" if rate < floor else f"{rate:.0f}%")

    def _update_unread(self, df: pd.DataFrame):
        """未读：_read 列为 0 或不存在该列的记录数"""
        if '_read' not in df.columns:
            _set_card_value(self.card_unread, str(len(df)))
            return
        unread = (df['_read'] == 0).sum()
        _set_card_value(self.card_unread, str(unread))

    def _update_anomaly(self, df: pd.DataFrame):
        """真异常条数：|偏差率| > 阈值 且 非替代料，判据在 core.threshold_config。

        口径与改造前逐字一致（只排替代料，不排 SAP 钳位与未投料）—— 本期换的是
        「谁说了算」，不是「怎么算」。
        """
        if _thr.rate_series(df) is None:
            _set_card_value(self.card_anomaly, "--")
            return
        self.card_anomaly.setToolTip(
            "非替代料中 |偏差率| > %g%% 的条数（阈值在规则中心「阈值与提醒」改）"
            % _thr.get_thresholds()["anomaly_dev_rate_pct"])
        _set_card_value(self.card_anomaly, str(_thr.count_anomalies(df)))

    def _update_alt(self, df: pd.DataFrame):
        """替代料：组数 + 净偏差抵消金额"""
        group_col = None
        for col in ['_替代料组', '替代料组']:
            if col in df.columns:
                group_col = col
                break

        if group_col is None or group_col not in df.columns:
            _set_card_value(self.card_alt, "0组")
            return

        groups = df[df[group_col].notna() & (df[group_col].astype(str).str.strip() != '')]
        if groups.empty:
            _set_card_value(self.card_alt, "0组")
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

        _set_card_value(self.card_alt, text)

    def _update_changed(self, df: pd.DataFrame):
        """审核后变更：_post_audit_changed 列为 1 的条数"""
        if '_post_audit_changed' not in df.columns:
            _set_card_value(self.card_changed, "--")
            return
        cnt = int((df['_post_audit_changed'] == 1).sum())
        _set_card_value(self.card_changed, str(cnt) if cnt else "0")

    def _update_quarantine(self, df: pd.DataFrame):
        """隔离区：_quarantined 列为 1 的条数"""
        if '_quarantined' not in df.columns:
            _set_card_value(self.card_quarantine, "--")
            return
        cnt = int((df['_quarantined'] == 1).sum())
        _set_card_value(self.card_quarantine, str(cnt) if cnt else "0")

    def _update_deviation(self, df: pd.DataFrame):
        """偏差率预警条数：判据在 core.threshold_config，与主表橙色高亮 / 颜色筛选 /
        偏差率预警看板 / 未读汇总同一条（改造前这里是第四处 >= 10 字面量）。"""
        if _thr.rate_series(df) is None:
            _set_card_value(self.card_deviation, "--")
            return
        cfg = _thr.get_thresholds()
        # 提示里的数字跟着配置走：阈值改成 15 还写「≥10%」就是另一处「两种红」
        self.card_deviation.setToolTip(
            "偏差率绝对值 ≥ %g%% 的记录数（点击打开偏差率预警看板，阈值在规则中心"
            "「阈值与提醒」改）" % cfg["alert_dev_rate_pct"])
        cnt = _thr.count_dev_alerts(df, cfg)
        _set_card_value(self.card_deviation, str(cnt) if cnt else "0")
