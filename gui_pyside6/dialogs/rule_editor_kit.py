# -*- coding: utf-8 -*-
"""规则中心各 Tab 共用的外壳件（第四期C 抽出来，第四期D 复用）。

为什么要有这个文件：「自动隔离」和「自动已读」是同一个窗口的两页，设计稿只画了
一份形态（240px 规则列表 + 条件卡 + 底部真实命中预览条）。两边各抄一份 QSS，改
一处圆角/字号另一处必然漏 —— 正是设计稿改进点 4 点名的「两个真源」。所以尺寸常量、
全套 QSS（颜色一律令牌名、零 hex）、列表行控件、字段小工厂都放这里，各 Tab 只保留
本页特有的选择器。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gui_pyside6.components import dialog_chrome
from gui_pyside6.themes.tokens import FONT_NUM, FONT_PT, SIZE_PX
from gui_pyside6.utils.icons import get_icon
from utils.theme_manager import Thm

# ------------------------------------------------------------------ 尺寸（design-system.css 对应项）
LIST_W = 240            # .rule-list{width:240px;flex:0 0 240px}
NAME_H = 28             # .rule-top input[type=text]{height:28px}
FINPUT_H = 27           # .finput{height:27px}
FIELD_W = 78            # .frow>label{min-width:78px} / .finput.num-in{width:78px}
TOOL = 30               # .tool-btn{width:30px;height:30px}
TAG_H = 22              # .tag{height:22px}
DOT = 12                # .rule-item .chk{width:12px;height:12px}
BODY_MIN_H = 220        # .rule-body{flex:1;overflow:auto}：滚动区下限，卡片多了不撑外壳
LAYOUT_MIN_H = 430      # .rule-layout{min-height:430px}
ROW_GAP = 8             # .frow{gap:8px}
CARD_GAP = 9            # .cgroup-body{gap:9px}

RULE_TAB_QSS = f"""
QWidget#ruleTab {{ background: $surface; }}

/* —— 左列：规则列表 —— */
QFrame#ruleListPanel {{ background: $surface2; border-right: 1px solid $border; }}
QLabel#ruleListHead {{
    font-size: {FONT_PT["label"]}px; font-weight: 700; color: $textFaint;
}}
QListWidget#ruleList {{
    background: transparent; border: none; outline: none;
}}
QListWidget#ruleList::item {{ background: transparent; border: none; }}
QListWidget#ruleList::item:selected {{ background: transparent; }}
QWidget#ruleItem {{
    background: transparent;
    border-left: 3px solid transparent;
}}
QWidget#ruleItem:hover {{ background: $surface3; }}
QWidget#ruleItem[sel="true"] {{ background: $primarySoft; border-left: 3px solid $primary; }}
QLabel#ruleDot {{
    border: 1px solid $borderStrong; border-radius: 3px; background: $surface;
    min-width: {DOT}px; min-height: {DOT}px; max-width: {DOT}px; max-height: {DOT}px;
}}
QLabel#ruleDot[on="true"] {{ background: $primary; border-color: $primary; }}
QLabel#ruleName {{ font-size: {FONT_PT["note"]}px; font-weight: 600; color: $text; }}
QLabel#ruleMeta {{ font-size: {FONT_PT["aux"]}px; color: $textMuted; }}
QLabel#ruleMetaNum {{
    font-size: {FONT_PT["aux"]}px; font-family: {FONT_NUM}; font-weight: 600; color: $text;
}}
QLabel#ruleMetaNum[hit="true"] {{ color: $danger; }}
QLabel#ruleFoot {{ font-size: {FONT_PT["aux"]}px; color: $textFaint; }}
QCheckBox#masterCheck {{ font-size: {FONT_PT["note"]}px; color: $text; spacing: 6px; }}

/* —— 右列：编辑区 —— */
QWidget#ruleEditor {{ background: $surface; }}
QFrame#ruleTop {{ border-bottom: 1px solid $border; }}
QLineEdit#ruleNameEdit {{
    height: {NAME_H}px; padding: 0 9px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface; color: $text;
    selection-background-color: $primarySoft;
}}
QLineEdit#ruleNameEdit:focus {{ border-color: $primarySoftBd; }}
QCheckBox#ruleTopCheck {{ font-size: {FONT_PT["note"]}px; color: $text; spacing: 6px; }}
QLabel#ruleIdTag {{
    height: {TAG_H}px; padding: 0 8px; border-radius: {SIZE_PX["radiusSm"]}px;
    background: $surface2; border: 1px solid $border; color: $textMuted;
    font-family: {FONT_NUM}; font-size: {FONT_PT["aux"]}px;
}}
QToolButton#ruleTool {{
    min-width: {TOOL}px; max-width: {TOOL}px; min-height: {TOOL}px; max-height: {TOOL}px;
    border-radius: {SIZE_PX["radiusMd"]}px; border: 1px solid transparent;
    background: transparent; color: $textMuted;
}}
QToolButton#ruleTool:hover {{ background: $surface3; color: $text; border-color: $border; }}
QToolButton#ruleTool:disabled {{ color: $borderStrong; }}

/* —— 语义行 —— */
QLabel#semBox {{
    padding: 3px 8px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface2;
    font-family: {FONT_NUM}; font-size: {FONT_PT["aux"]}px; color: $textMuted;
}}
QLabel#semOp {{
    font-family: {FONT_NUM}; font-size: {FONT_PT["aux"]}px; font-weight: 700;
    color: $primaryHover; padding: 0 5px;
}}
QLabel#semX {{ font-size: {FONT_PT["aux"]}px; color: $textFaint; }}
QLabel#semNote {{ font-size: {FONT_PT["aux"]}px; color: $textFaint; }}

/* —— 条件卡 —— */
QScrollArea#ruleBody {{ background: $surface; border: none; }}
QFrame#cGroup {{
    border: 1px solid $border; border-radius: {SIZE_PX["radiusMd"]}px; background: $surface2;
}}
QFrame#cGroupHead {{ background: $surface3; border-bottom: 1px solid $border; }}
QLabel#cGroupTitle {{ font-size: {FONT_PT["note"]}px; font-weight: 600; color: $text; }}
QLabel#cGroupIcon {{ min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; }}
QLabel#cGroupLogic {{
    font-family: {FONT_NUM}; font-size: {FONT_PT["label"]}px; color: $textFaint;
}}
QLabel#fieldLabel {{ font-size: {FONT_PT["note"]}px; color: $textMuted; min-width: {FIELD_W}px; }}
QLabel#fieldHint {{ font-size: {FONT_PT["aux"]}px; color: $textFaint; }}
QCheckBox#fieldCheck {{ font-size: {FONT_PT["note"]}px; color: $text; spacing: 6px; }}
QLineEdit[finput="1"] {{
    height: {FINPUT_H}px; padding: 0 9px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface; color: $text;
}}
QLineEdit[finput="1"]:focus {{ border-color: $primarySoftBd; }}
QDoubleSpinBox[finput="1"] {{
    height: {FINPUT_H}px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface; color: $text;
    padding: 0 6px; font-family: {FONT_NUM};
}}
QDoubleSpinBox[finput="1"]:focus {{ border: 1px solid $primarySoftBd; }}
QPushButton[role="btn-outline"] {{
    height: {FINPUT_H}px; padding: 0 11px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $borderStrong; background: $surface; color: $text;
    font-size: {FONT_PT["note"]}px;
}}
QPushButton[role="btn-outline"]:hover {{
    border-color: $primarySoftBd; background: $primarySoft; color: $primaryHover;
}}
QPushButton[role="btn-primary"] {{
    height: {FINPUT_H}px; padding: 0 13px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $primary; background: $primary; color: $onPrimary;
    font-size: {FONT_PT["note"]}px; font-weight: 600;
}}
QPushButton[role="btn-primary"]:hover {{ background: $primaryHover; border-color: $primaryHover; }}
QPushButton[role="btn-danger"]:hover {{
    border-color: $danger; background: $dangerSoft; color: $danger;
}}

/* —— 真实命中预览条 —— */
QFrame#rulePreview {{ background: $primarySoft; border-top: 1px solid $border; }}
QLabel#pvMain {{ font-size: {FONT_PT["note"]}px; color: $text; }}
QLabel#pvMainNum {{
    font-family: {FONT_NUM}; font-size: {FONT_PT["heading"]}px; font-weight: 600;
    color: $primaryHover;
}}
QLabel#pvSample {{ font-size: {FONT_PT["aux"]}px; color: $textMuted; }}
"""


def repolish(widget):
    """动态属性变了要让 QSS 重算，否则 [sel="true"] 这类选择器不生效。"""
    st = widget.style()
    st.unpolish(widget)
    st.polish(widget)


class RuleRow(QWidget):
    """列表里的一行（对应 .rule-item）：状态方块 + 名称 + 命中摘要。

    命中数的口径由调用方决定，这里的文案只说「计不计命中」的原因，不骗人：
    没选表、总开关关着，都不能写成「命中 0 条」（那等于说规则失效了）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ruleItem")
        outer = QVBoxLayout(self)
        # .rule-item{padding:9px 12px}：选中时左侧 3px 蓝边已算进边框，正文起点恒为 12px
        outer.setContentsMargins(12, 7, 12, 7)
        outer.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.dot = QLabel()
        self.dot.setObjectName("ruleDot")
        self.lbl_name = QLabel()
        self.lbl_name.setObjectName("ruleName")
        top.addWidget(self.dot)
        top.addWidget(self.lbl_name, 1)
        outer.addLayout(top)

        meta = QHBoxLayout()
        meta.setSpacing(3)
        self.lbl_pre = QLabel()
        self.lbl_pre.setObjectName("ruleMeta")
        self.lbl_num = QLabel()
        self.lbl_num.setObjectName("ruleMetaNum")
        self.lbl_post = QLabel()
        self.lbl_post.setObjectName("ruleMeta")
        for w in (self.lbl_pre, self.lbl_num, self.lbl_post):
            meta.addWidget(w)
        meta.addStretch(1)
        outer.addLayout(meta)

        self._sel = None
        self._on = None

    def set_state(self, name, enabled, hits, total, master_on=True, no_data=False):
        self.lbl_name.setText(name)
        on = bool(enabled)
        self.dot.setProperty("on", "true" if on else "false")
        if no_data:
            self.lbl_pre.setText("主表无数据 · 不计命中")
            self.lbl_num.setText("")
            self.lbl_post.setText("")
        elif not master_on:
            self.lbl_pre.setText("总开关已关 · 不计命中")
            self.lbl_num.setText("")
            self.lbl_post.setText("")
        elif not on:
            self.lbl_pre.setText("已停用 · 命中")
            self.lbl_num.setText("—")
            self.lbl_post.setText("条")
        elif hits:
            self.lbl_pre.setText("命中")
            self.lbl_num.setText(str(hits))
            self.lbl_post.setText("条 · 占比 %.1f%%" % (100.0 * hits / total if total else 0.0))
        else:
            self.lbl_pre.setText("命中 0 条")
            self.lbl_num.setText("")
            self.lbl_post.setText("")
        self.lbl_num.setProperty("hit", "true" if (on and master_on and hits) else "false")
        if on != self._on:
            self._on = on
            repolish(self.dot)
        repolish(self.lbl_num)

    def set_selected(self, selected):
        selected = bool(selected)
        if selected == self._sel:
            return
        self._sel = selected
        self.setProperty("sel", "true" if selected else "false")
        repolish(self)


def card(icon_name, title, tone="primary", logic="组内 OR"):
    """一张条件卡（.cgroup）：返回 (卡片控件, 供塞字段的 body 布局)。

    右上角 logic 写清这组内部的逻辑关系，别让用户从字段顺序里猜。
    """
    box = QFrame()
    box.setObjectName("cGroup")
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)

    head = QFrame()
    head.setObjectName("cGroupHead")
    hl = QHBoxLayout(head)
    hl.setContentsMargins(11, 7, 11, 7)
    hl.setSpacing(8)
    ic = QLabel()
    ic.setObjectName("cGroupIcon")
    ink = Thm.color("danger") if tone == "danger" else (
        Thm.color("warn") if tone == "warn" else Thm.color("primary"))
    ic.setPixmap(get_icon(icon_name, 14, ink).pixmap(14, 14))
    hl.addWidget(ic)
    title_lbl = QLabel(title)
    title_lbl.setObjectName("cGroupTitle")
    hl.addWidget(title_lbl)
    hl.addStretch(1)
    logic_lbl = QLabel(logic)
    logic_lbl.setObjectName("cGroupLogic")
    hl.addWidget(logic_lbl)
    v.addWidget(head)

    body = QWidget()
    bl = QVBoxLayout(body)
    bl.setContentsMargins(11, 10, 11, 10)
    bl.setSpacing(CARD_GAP)
    v.addWidget(body)
    return box, bl


def flabel(text):
    lbl = QLabel(text)
    lbl.setObjectName("fieldLabel")
    return lbl


def fhint(text):
    lbl = QLabel(text)
    lbl.setObjectName("fieldHint")
    return lbl


def fline(placeholder=""):
    edit = QLineEdit()
    edit.setProperty("finput", "1")
    edit.setPlaceholderText(placeholder)
    return edit


def fspin(lo, hi, value, width=FIELD_W):
    sp = QDoubleSpinBox()
    sp.setProperty("finput", "1")
    sp.setRange(lo, hi)
    sp.setDecimals(2)
    sp.setValue(value)
    sp.setFixedWidth(width)
    sp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    sp.setButtonSymbols(QDoubleSpinBox.NoButtons)
    return sp


def fcheck(text):
    cb = QCheckBox(text)
    cb.setObjectName("fieldCheck")
    return cb


def style_tab(widget, extra_qss=""):
    """给一个 Tab 上令牌 QSS（+ 本页特有的补充选择器）。"""
    dialog_chrome.style_with_tokens(widget, RULE_TAB_QSS + extra_qss)
    return widget
