# -*- coding: utf-8 -*-
"""自动隔离规则配置 —— 规则中心 Tab①（设计稿 v43.333 rules.html 的新形态）

改造前什么样
------------
一条线性长表单：18 个字段从上到下平铺，「要求属于类别」「要求属于单位」各挂一个
动态显隐的复选框容器 —— 勾一下整张表单从 680px 长到 1180px，下面的字段被推走、
滚动位置丢失；20 个单位复选框直接吃掉半屏；组间关系靠一行
「—— 偏差率 / 编码 / 车间 / 备注 等条件 ——」文本假装说了；预览只有一句自然语言
摘要，配完规则不知道会不会误伤。（设计稿 rules.html 现状诊断 1~4 点，逐条对应。）

现在什么样
----------
· 左列 240px 规则列表：每条显示「命中 N 条 · 占比 x.x%」，停用灰显，底部固定写
  「规则按从上到下依次匹配，命中即停」；
· 右列编辑区：抬头（名称 / 启用 / 编号 / 上移·下移·删除）+ 语义行（组内 OR
  × AND × 组间全部满足）+ 三张条件卡（物料维度 / 数值维度 / 组织与状态）在固定
  区域内滚动 + 底部真实命中预览条（试跑 / 保存）；
· 类别、单位改用 TagMultiSelect（第四期A 那个可搜索多选标签控件）。

四条硬约束
----------
1. **持久化 schema 一个字不动**：编辑区仍然只写 ``DEFAULT_RULE`` 的那 16 个键，
   ``config/auto_quarantine_config.json`` 不需要迁移。设计稿第三张卡画的
   「半成品分类」不是新字段 —— 匹配器把「半成品重分类」列当作 ``category_value``
   的**优先匹配源**（v43.97），所以半成品值直接进「类别」多选的候选；单独立一行
   等于两个控件抢写同一个键。
2. **匹配语义不动**：组内 OR、组间 AND、多规则 OR、靠前规则优先、缺列保守不匹配，
   全部由 ``core/auto_quarantine.py`` 决定，本文件只做输入与展示；「实际=0（未投料）」
   按口径永远进不了自动隔离，界面上也不得暗示它已被处理。
3. **预览只读**：命中数走第四期B 的 ``describe_rule_hits`` / ``compute_rule_hit_counts``
   （与生产隔离同一个 ``_match_single_rule``）。「试跑」只是把草稿替换进 cfg 再算一遍，
   不写配置、不改数据、不碰隔离区。
4. **配色零 hex、尺寸走档位**：QSS 交给 ``dialog_chrome.style_with_tokens``，颜色一律
   是令牌名，圆角/字号取 ``SIZE_PX`` / ``FONT_PT``。设计稿的 11.5px / 12.5px 这类
   半档在 Qt 侧并到档位（11 / 12 / 13）上 —— 差的零点几像素换来的是亮暗能跟随。
"""
import re

import pandas as pd

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.auto_quarantine import (
    DEFAULT_RULE,
    build_all_summary,
    build_rule_reason,
    build_rule_summary,
    compute_auto_quarantine_ids,
    compute_rule_hit_counts,
    describe_rule_hits,
    load_auto_quarantine_config,
    save_auto_quarantine_config,
)
from gui_pyside6.components import dialog_chrome, message_box
from gui_pyside6.themes.tokens import FONT_NUM, FONT_PT, SIZE_PX
from gui_pyside6.utils.icons import get_icon
from gui_pyside6.widgets.tag_multi_select import TagMultiSelect
from utils.theme_manager import Thm

# ------------------------------------------------------------------ 尺寸（design-system.css 对应项）
_LIST_W = 240           # .rule-list{width:240px;flex:0 0 240px}
_NAME_H = 28            # .rule-top input[type=text]{height:28px}
_FINPUT_H = 27          # .finput{height:27px}
_FIELD_W = 78           # .frow>label{min-width:78px} / .finput.num-in{width:78px}
_TOOL = 30              # .tool-btn{width:30px;height:30px}
_TAG_H = 22             # .tag{height:22px}
_DOT = 12               # .rule-item .chk{width:12px;height:12px}
_BODY_MIN_H = 220       # .rule-body{flex:1;overflow:auto}：滚动区下限，卡片多了不撑外壳
_LAYOUT_MIN_H = 430     # .rule-layout{min-height:430px}
_ROW_GAP = 8            # .frow{gap:8px}
_CARD_GAP = 9           # .cgroup-body{gap:9px}

#: 「单位」候选（内置常用 + 现有规则里出现过的）；与旧 _known_units 同一份枚举。
_BUILTIN_UNITS = [
    "个", "箱", "瓶", "罐", "袋", "包", "卷", "米", "kg", "吨",
    "套", "件", "盒", "桶", "只", "对", "支", "根", "张", "片",
]
#: 「类别」候选：数据里「组件物料类型描述」实测值（v43.98 不臆造分类）。
#: 后两项同时是「半成品重分类」列的取值 —— 匹配器把它们当 category_value 的优先
#: 精确匹配源，所以在这一个多选里出现就够了，不再单列「半成品分类」行。
_BUILTIN_CATEGORIES = ["包材", "原辅料", "广宣", "食品半成品", "饮料半成品"]

#: 备注要求三态（remark_mode），顺序即按钮顺序
_REMARK_MODES = [("off", "全部"), ("has", "有备注"), ("none", "无备注")]

_CSS = f"""
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
    min-width: {_DOT}px; min-height: {_DOT}px; max-width: {_DOT}px; max-height: {_DOT}px;
}}
QLabel#ruleDot[on="true"] {{ background: $primary; border-color: $primary; }}
QLabel#ruleName {{ font-size: {FONT_PT["note"]}px; font-weight: 600; color: $text; }}
QLabel#ruleMeta {{ font-size: {FONT_PT["aux"]}px; color: $textMuted; }}
QLabel#ruleMetaNum {{ font-size: {FONT_PT["aux"]}px; font-family: {FONT_NUM}; font-weight: 600; color: $text; }}
QLabel#ruleMetaNum[hit="true"] {{ color: $danger; }}
QLabel#ruleFoot {{ font-size: {FONT_PT["aux"]}px; color: $textFaint; }}
QCheckBox#masterCheck {{ font-size: {FONT_PT["note"]}px; color: $text; spacing: 6px; }}

/* —— 右列：编辑区 —— */
QWidget#ruleEditor {{ background: $surface; }}
QFrame#ruleTop {{ border-bottom: 1px solid $border; }}
QLineEdit#ruleNameEdit {{
    height: {_NAME_H}px; padding: 0 9px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface; color: $text;
    selection-background-color: $primarySoft;
}}
QLineEdit#ruleNameEdit:focus {{ border-color: $primarySoftBd; }}
QCheckBox#ruleTopCheck {{ font-size: {FONT_PT["note"]}px; color: $text; spacing: 6px; }}
QLabel#ruleIdTag {{
    height: {_TAG_H}px; padding: 0 8px; border-radius: {SIZE_PX["radiusSm"]}px;
    background: $surface2; border: 1px solid $border; color: $textMuted;
    font-family: {FONT_NUM}; font-size: {FONT_PT["aux"]}px;
}}
QToolButton#ruleTool {{
    min-width: {_TOOL}px; max-width: {_TOOL}px; min-height: {_TOOL}px; max-height: {_TOOL}px;
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
QLabel#fieldLabel {{ font-size: {FONT_PT["note"]}px; color: $textMuted; min-width: {_FIELD_W}px; }}
QLabel#fieldHint {{ font-size: {FONT_PT["aux"]}px; color: $textFaint; }}
QCheckBox#fieldCheck {{ font-size: {FONT_PT["note"]}px; color: $text; spacing: 6px; }}
QLineEdit[finput="1"] {{
    height: {_FINPUT_H}px; padding: 0 9px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface; color: $text;
}}
QLineEdit[finput="1"]:focus {{ border-color: $primarySoftBd; }}
QDoubleSpinBox[finput="1"] {{
    height: {_FINPUT_H}px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface; color: $text;
    padding: 0 6px; font-family: {FONT_NUM};
}}
QDoubleSpinBox[finput="1"]:focus {{ border: 1px solid $primarySoftBd; }}
QPushButton[role="btn-outline"] {{
    height: {_FINPUT_H}px; padding: 0 11px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $borderStrong; background: $surface; color: $text;
    font-size: {FONT_PT["note"]}px;
}}
QPushButton[role="btn-outline"]:hover {{
    border-color: $primarySoftBd; background: $primarySoft; color: $primaryHover;
}}
QPushButton[role="btn-primary"] {{
    height: {_FINPUT_H}px; padding: 0 13px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $primary; background: $primary; color: $onPrimary;
    font-size: {FONT_PT["note"]}px; font-weight: 600;
}}
QPushButton[role="btn-primary"]:hover {{ background: $primaryHover; border-color: $primaryHover; }}
QPushButton[role="btn-danger"]:hover {{
    border-color: $danger; background: $dangerSoft; color: $danger;
}}
QPushButton#remarkSeg {{
    height: {_TAG_H}px; padding: 0 9px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface; color: $textMuted;
    font-size: {FONT_PT["aux"]}px;
}}
QPushButton#remarkSeg:hover {{ border-color: $primarySoftBd; color: $primaryHover; }}
QPushButton#remarkSeg:checked {{
    background: $primarySoft; border-color: $primarySoftBd;
    color: $primaryHover; font-weight: 600;
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


def _repolish(widget):
    """动态属性变了要让 QSS 重算，否则 [sel="true"] 这类选择器不生效。"""
    st = widget.style()
    st.unpolish(widget)
    st.polish(widget)


class _RuleRow(QWidget):
    """列表里的一行（对应 .rule-item）：状态方块 + 名称 + 命中摘要。"""

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
            # 还没选表就说「命中 0 条」，等于骗人说规则失效了
            self.lbl_pre.setText("主表无数据 · 不计命中")
            self.lbl_num.setText("")
            self.lbl_post.setText("")
        elif not master_on:
            # 总开关关着时谁都跑，同理不能写成「命中 0 条」
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
            _repolish(self.dot)
        _repolish(self.lbl_num)

    def set_selected(self, selected):
        selected = bool(selected)
        if selected == self._sel:
            return
        self._sel = selected
        self.setProperty("sel", "true" if selected else "false")
        _repolish(self)


class AutoQuarantineRuleWidget(QWidget):
    """规则中心 Tab①：左列规则列表 + 右列三张条件卡 + 底部真实命中预览。"""

    #: 保存成功/失败（供宿主对话框收尾：中心对话框据此 accept，薄壳据此提示）
    saved = Signal(bool)

    def __init__(self, parent=None, df=None):
        super().__init__(parent)
        self.setObjectName("ruleTab")
        self.cfg = load_auto_quarantine_config()      # {'enabled','rules'}
        self.df = df if df is not None else pd.DataFrame()
        self.current_index = 0
        self._loading = False                          # 回填期屏蔽「草稿已改」重算
        self._build_ui()
        dialog_chrome.style_with_tokens(self, _CSS)
        self._load_rule_to_editor(0)
        self._refresh_list()

    # ---------------------------------------------------------------- UI 骨架
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setMinimumHeight(_LAYOUT_MIN_H)
        root.addWidget(self._build_list_panel())
        root.addWidget(self._build_editor(), 1)

    def _build_list_panel(self):
        panel = QFrame()
        panel.setObjectName("ruleListPanel")
        panel.setFixedWidth(_LIST_W)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QFrame()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 10, 12, 8)
        hl.setSpacing(6)
        title = QLabel("规则列表")
        title.setObjectName("ruleListHead")
        self.btn_add = QPushButton("+ 新增")
        self.btn_add.setProperty("role", "btn-outline")
        self.btn_add.setFixedHeight(24)
        self.btn_add.setToolTip("在列表末尾追加一条规则（沿用默认条件）")
        hl.addWidget(title)
        hl.addStretch(1)
        hl.addWidget(self.btn_add)
        lay.addWidget(head)

        self.chk_master = QCheckBox("启用自动隔离（总开关）")
        self.chk_master.setObjectName("masterCheck")
        self.chk_master.setChecked(bool(self.cfg.get("enabled", True)))
        self.chk_master.setToolTip(
            "关闭后：分析完成时不做任何自动隔离，下面每条规则的命中数也不再计入")
        mw = QHBoxLayout()
        mw.setContentsMargins(12, 6, 12, 8)
        mw.addWidget(self.chk_master)
        lay.addLayout(mw)

        self.list_rules = QListWidget()
        self.list_rules.setObjectName("ruleList")
        self.list_rules.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_rules.setSelectionBehavior(QListWidget.SelectRows)
        self.list_rules.setSelectionMode(QListWidget.SingleSelection)
        self.list_rules.setUniformItemSizes(True)
        self._rows = []                                 # index -> _RuleRow
        self.list_rules.currentRowChanged.connect(self._on_select_rule)
        lay.addWidget(self.list_rules, 1)

        foot = QLabel("规则按<b>从上到下</b>依次匹配，命中即停；"
                      "排序请用编辑区上方的 ↑ ↓。")
        foot.setObjectName("ruleFoot")
        foot.setTextFormat(Qt.RichText)
        foot.setWordWrap(True)
        fw = QHBoxLayout()
        fw.setContentsMargins(12, 10, 12, 10)
        fw.addWidget(foot)
        lay.addLayout(fw)
        return panel

    def _build_editor(self):
        editor = QWidget()
        editor.setObjectName("ruleEditor")
        lay = QVBoxLayout(editor)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_top())
        lay.addWidget(self._build_sem())
        lay.addWidget(self._build_body(), 1)
        lay.addWidget(self._build_preview())
        return editor

    def _build_top(self):
        top = QFrame()
        top.setObjectName("ruleTop")
        hl = QHBoxLayout(top)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(10)

        self.edit_name = QLineEdit()
        self.edit_name.setObjectName("ruleNameEdit")
        self.edit_name.setPlaceholderText("规则名称")
        self.edit_name.setMinimumWidth(180)
        hl.addWidget(self.edit_name, 1)

        self.chk_rule_enabled = QCheckBox("启用此规则")
        self.chk_rule_enabled.setObjectName("ruleTopCheck")
        hl.addWidget(self.chk_rule_enabled)

        self.lbl_id = QLabel("编号 R-001")
        self.lbl_id.setObjectName("ruleIdTag")
        hl.addWidget(self.lbl_id)

        self.btn_up = QToolButton()
        self.btn_up.setObjectName("ruleTool")
        self.btn_up.setToolTip("把本条规则往前移一位（匹配优先级升高）")
        self.btn_down = QToolButton()
        self.btn_down.setObjectName("ruleTool")
        self.btn_down.setToolTip("把本条规则往后移一位")
        self.btn_del = QPushButton("删除")
        self.btn_del.setProperty("role", "btn-outline")
        self.btn_del.setToolTip("删除本条规则（至少保留一条）")
        for w in (self.btn_up, self.btn_down, self.btn_del):
            hl.addWidget(w)
        return top

    def _build_sem(self):
        """语义行：把「组内 OR × 组间 AND」这句人话写出来，而不是让用户猜。"""
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(14, 8, 14, 6)
        hl.setSpacing(0)
        for text, obj in (("组内 任一满足", "semBox"), ("OR", "semOp"), ("×", "semX"),
                          ("AND", "semOp"), ("×", "semX"), ("组间 全部满足", "semBox")):
            lbl = QLabel(text)
            lbl.setObjectName(obj)
            hl.addWidget(lbl)
        hl.addStretch(1)
        note = QLabel("三组全部命中才算命中此规则")
        note.setObjectName("semNote")
        hl.addWidget(note)
        return row

    # ---------------------------------------------------------------- 条件卡
    def _card(self, icon_name, title, tone="primary"):
        """一张条件卡（.cgroup）：返回 (卡片控件, 供塞字段的 body 布局)。"""
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
        logic = QLabel("组内 OR")
        logic.setObjectName("cGroupLogic")
        hl.addWidget(logic)
        v.addWidget(head)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(11, 10, 11, 10)
        bl.setSpacing(_CARD_GAP)
        v.addWidget(body)
        return box, bl

    def _flabel(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _fhint(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("fieldHint")
        return lbl

    def _line(self, placeholder=""):
        edit = QLineEdit()
        edit.setProperty("finput", "1")
        edit.setPlaceholderText(placeholder)
        return edit

    def _spin(self, lo, hi, value, width=_FIELD_W):
        sp = QDoubleSpinBox()
        sp.setProperty("finput", "1")
        sp.setRange(lo, hi)
        sp.setDecimals(2)
        sp.setValue(value)
        sp.setFixedWidth(width)
        sp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sp.setButtonSymbols(QDoubleSpinBox.NoButtons)
        return sp

    def _check(self, text):
        cb = QCheckBox(text)
        cb.setObjectName("fieldCheck")
        return cb

    def _build_body(self):
        scroll = QScrollArea()
        scroll.setObjectName("ruleBody")
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(_BODY_MIN_H)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(10)

        # —— 组 1：物料维度 ——
        g1, b1 = self._card("box", "物料维度")
        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        r.addWidget(self._flabel("名称包含"))
        self.edit_keywords = self._line("例如：箱, 手包袋, 塑料袋")
        r.addWidget(self.edit_keywords, 1)
        r.addWidget(self._fhint("逗号分隔，任一命中"))
        b1.addLayout(r)

        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        r.addWidget(self._flabel("名称排除"))
        self.edit_name_exclude = self._line("例如：彩箱, 定制")
        r.addWidget(self.edit_name_exclude, 1)
        r.addWidget(self._fhint("任一命中即排除"))
        b1.addLayout(r)

        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        r.addWidget(self._flabel("编码前缀"))
        self.edit_mat_prefix = self._line("例如 40,41")
        self.edit_mat_prefix.setMinimumWidth(_FIELD_W)
        r.addWidget(self.edit_mat_prefix)
        r.addWidget(self._fhint("多值 OR；留空不限制"))
        r.addStretch(1)
        b1.addLayout(r)

        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        # AlignTop 只给字段标签用：整行设 AlignTop 会让 Qt 按 minimumSizeHint 给
        # TagMultiSelect 定高，标签换到第二行时不再撑高行 → 下一行字段被压住。
        self.chk_cat = self._check("限定类别")
        r.addWidget(self.chk_cat, 0, Qt.AlignTop)
        self.tag_cat = TagMultiSelect()
        r.addWidget(self.tag_cat, 1)
        b1.addLayout(r)

        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        self.chk_unit = self._check("限定单位")
        r.addWidget(self.chk_unit, 0, Qt.AlignTop)
        self.tag_unit = TagMultiSelect()
        r.addWidget(self.tag_unit, 1)
        r2 = QHBoxLayout()
        r2.addWidget(self._fhint("可搜索多选，20 项不再平铺"))
        r2.addStretch(1)
        b1.addLayout(r)
        b1.addLayout(r2)
        v.addWidget(g1)

        # —— 组 2：数值维度 ——
        g2, b2 = self._card("chart", "数值维度", tone="danger")
        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        self.chk_dev_rate = self._check("偏差率")
        r.addWidget(self.chk_dev_rate)
        self.spin_dev_rate_min = self._spin(-1000, 1000, 10)
        self.spin_dev_rate_max = self._spin(-1000, 1000, 100)
        r.addWidget(self.spin_dev_rate_min)
        r.addWidget(self._fhint("% ~"))
        r.addWidget(self.spin_dev_rate_max)
        r.addWidget(self._fhint("%（开区间，不含端点）"))
        r.addStretch(1)
        b2.addLayout(r)

        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        self.chk_dev_qty = self._check("偏差数量")
        r.addWidget(self.chk_dev_qty)
        self.spin_dev_qty_min = self._spin(-1000000, 1000000, 0)
        self.spin_dev_qty_max = self._spin(-1000000, 1000000, 1)
        r.addWidget(self.spin_dev_qty_min)
        r.addWidget(self._fhint("~"))
        r.addWidget(self.spin_dev_qty_max)
        r.addWidget(self._fhint("开区间"))
        r.addStretch(1)
        b2.addLayout(r)

        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        r.addWidget(self._flabel("方向条件"))
        self.chk_loss = self._check("要求负损（0 < 实际 < 定额）")
        self.chk_alt = self._check("排除替代料")
        r.addWidget(self.chk_loss)
        r.addWidget(self.chk_alt)
        r.addStretch(1)
        b2.addLayout(r)

        warn = self._fhint("「实际=0（未投料）」按口径永远不进自动隔离，须留在隔离区人工审计")
        warn.setWordWrap(True)
        b2.addWidget(warn)
        v.addWidget(g2)

        # —— 组 3：组织与状态 ——
        g3, b3 = self._card("factory", "组织与状态", tone="warn")
        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        self.chk_workshop = self._check("车间")
        r.addWidget(self.chk_workshop)
        self.edit_workshop = self._line("例如：一车间（留空不限制）")
        self.edit_workshop.setMinimumWidth(160)
        r.addWidget(self.edit_workshop, 1)
        r.addWidget(self._fhint("单个取值，精确匹配"))
        b3.addLayout(r)

        r = QHBoxLayout()
        r.setSpacing(6)
        r.addWidget(self._flabel("备注要求"))
        self._remark_btns = []
        self.remark_group = QButtonGroup(self)
        self.remark_group.setExclusive(True)
        for mode, text in _REMARK_MODES:
            btn = QPushButton(text)
            btn.setObjectName("remarkSeg")
            btn.setCheckable(True)
            btn.setProperty("remarkMode", mode)
            btn.setToolTip("只按「备注」列是否为空判断，不读备注内容")
            self.remark_group.addButton(btn)
            self._remark_btns.append(btn)
            r.addWidget(btn)
        # buttonClicked 只在真人点击时发；idClicked / toggled 在 _set_remark_mode
        # 回填时也会发，会把「回填」误报成「用户改动」
        self.remark_group.buttonClicked.connect(lambda _b: self._on_editor_changed())
        r.addStretch(1)
        b3.addLayout(r)

        r = QHBoxLayout()
        r.setSpacing(_ROW_GAP)
        r.addWidget(self._flabel("半成品分类"))
        hint = self._fhint("「食品半成品 / 饮料半成品」已并入上方「限定类别」候选 —— "
                           "匹配器把「半成品重分类」列当作类别取值的首选匹配源（v43.97），"
                           "所以不另设字段")
        hint.setWordWrap(True)
        r.addWidget(hint, 1)
        b3.addLayout(r)
        v.addWidget(g3)

        v.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _build_preview(self):
        bar = QFrame()
        bar.setObjectName("rulePreview")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(14)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(3)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.pv_pre = QLabel("真实数据实测：命中")
        self.pv_pre.setObjectName("pvMain")
        self.pv_num = QLabel("—")
        self.pv_num.setObjectName("pvMainNum")
        self.pv_post = QLabel("条")
        self.pv_post.setObjectName("pvMain")
        for w in (self.pv_pre, self.pv_num, self.pv_post):
            row.addWidget(w)
        row.addStretch(1)
        lv.addLayout(row)
        self.pv_sample = QLabel("主表无数据时不计算命中")
        self.pv_sample.setObjectName("pvSample")
        self.pv_sample.setWordWrap(True)
        lv.addWidget(self.pv_sample)
        hl.addWidget(left, 1)

        self.btn_trial = QPushButton("试跑（只预览不落库）")
        self.btn_trial.setProperty("role", "btn-outline")
        self.btn_trial.setToolTip(
            "用当前草稿替换本条规则，对主表再算一遍归属（含多规则优先级）。\n"
            "只读：不写配置、不改数据、不真的隔离。")
        self.btn_save = QPushButton("保存规则")
        self.btn_save.setProperty("role", "btn-primary")
        hl.addWidget(self.btn_trial)
        hl.addWidget(self.btn_save)
        return bar

    # ---------------------------------------------------------------- 事件接线
    def _on_editor_changed(self):
        """草稿变了就重算预览（回填期除外，避免逐字段回填时反复算）。"""
        if self._loading:
            return
        self._refresh_preview()

    def wire_changed_signals(self):
        """把全部输入控件接到草稿预览重算上。

        拆成公开方法是为了让宿主对话框（规则中心）在**构造完**再连线：构造期
        ``_load_rule_to_editor`` 会逐字段回填，回填完之后再连，既省掉十几次无谓
        重算，也不会把「回填」误当成「用户改动」。
        """
        for w in (self.edit_name, self.edit_keywords, self.edit_name_exclude,
                  self.edit_mat_prefix, self.edit_workshop):
            w.textChanged.connect(self._on_editor_changed)
        for w in (self.chk_rule_enabled, self.chk_cat, self.chk_unit, self.chk_alt,
                  self.chk_loss, self.chk_dev_rate, self.chk_dev_qty,
                  self.chk_workshop, self.chk_master):
            w.stateChanged.connect(self._on_editor_changed)
        for w in (self.spin_dev_rate_min, self.spin_dev_rate_max,
                  self.spin_dev_qty_min, self.spin_dev_qty_max):
            w.valueChanged.connect(self._on_editor_changed)
        self.tag_cat.changed.connect(self._on_editor_changed)
        self.tag_unit.changed.connect(self._on_editor_changed)
        # 总开关动的是整列的「计不计命中」文案，光重算预览不够
        self.chk_master.toggled.connect(lambda _on: self._refresh_list())
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_del)
        self.btn_up.clicked.connect(self._on_up)
        self.btn_down.clicked.connect(self._on_down)
        self.btn_trial.clicked.connect(self._on_trial_run)
        self.btn_save.clicked.connect(self._on_save_clicked)
        return self

    # ---------------------------------------------------------------- 草稿 <-> 控件
    def _split(self, raw):
        """逗号（中英文、顿号都算）分隔 → 去空列表。"""
        return [p.strip() for p in re.split(r"[，,、]", str(raw or "")) if p.strip()]

    def _collect_preview(self):
        """把编辑区当前内容收成一条完整规则字典（不落盘，供预览/试跑用）。

        必须逐键覆盖 ``DEFAULT_RULE``：少写一个键，预览就是拿残缺条件在算，
        显示的命中数与真跑必然不一致。
        """
        return {
            "name": self.edit_name.text().strip() or "未命名规则",
            "enabled": self.chk_rule_enabled.isChecked(),
            "exclude_alt": self.chk_alt.isChecked(),
            "category_required": self.chk_cat.isChecked(),
            "category_value": "，".join(self.tag_cat.selected()),
            "name_keywords": self._split(self.edit_keywords.text()),
            "negative_loss_required": self.chk_loss.isChecked(),
            "dev_rate_required": self.chk_dev_rate.isChecked(),
            "dev_rate_min": self.spin_dev_rate_min.value(),
            "dev_rate_max": self.spin_dev_rate_max.value(),
            "mat_code_prefix": self.edit_mat_prefix.text().strip(),
            "workshop_required": self.chk_workshop.isChecked(),
            "workshop_value": self.edit_workshop.text().strip(),
            "remark_mode": self._remark_mode(),
            "name_exclude_keywords": self.edit_name_exclude.text().strip(),
            "dev_qty_required": self.chk_dev_qty.isChecked(),
            "dev_qty_min": self.spin_dev_qty_min.value(),
            "dev_qty_max": self.spin_dev_qty_max.value(),
            "unit_required": self.chk_unit.isChecked(),
            "unit_value": "，".join(self.tag_unit.selected()),
        }

    def _remark_mode(self):
        for btn in self._remark_btns:
            if btn.isChecked():
                return str(btn.property("remarkMode") or "off")
        return "off"

    def _set_remark_mode(self, mode):
        mode = str(mode or "off").strip()
        if mode not in ("off", "has", "none"):
            mode = "off"
        for btn in self._remark_btns:
            btn.setChecked(str(btn.property("remarkMode")) == mode)

    def _commit_editor(self):
        """把编辑区写回 ``self.cfg['rules'][current_index]``（仍在内存，未落盘）。

        用 ``update`` 而不是整体替换：配置里若有本编辑器不认识的历史键（旧版本
        写入的备注、外部工具加的字段），整体替换会把它们静默删掉。
        """
        if not (0 <= self.current_index < len(self.cfg["rules"])):
            return
        self.cfg["rules"][self.current_index].update(self._collect_preview())

    def _load_rule_to_editor(self, idx):
        rules = self.cfg.get("rules", []) or []
        if not (0 <= idx < len(rules)):
            return
        self.current_index = idx
        r = dict(DEFAULT_RULE)
        r.update(rules[idx])
        self._loading = True
        try:
            self.edit_name.setText(str(r.get("name", "")))
            self.chk_rule_enabled.setChecked(bool(r.get("enabled", True)))
            self.lbl_id.setText("编号 R-%03d" % (idx + 1))
            self.edit_keywords.setText("，".join(r.get("name_keywords") or []))
            self.edit_name_exclude.setText(str(r.get("name_exclude_keywords", "")))
            self.edit_mat_prefix.setText(str(r.get("mat_code_prefix", "")))
            self.chk_cat.setChecked(bool(r.get("category_required", True)))
            self.tag_cat.setValues(self._known_categories())
            self.tag_cat.setSelected(self._split(r.get("category_value", "")))
            self.chk_unit.setChecked(bool(r.get("unit_required", False)))
            self.tag_unit.setValues(self._known_units())
            self.tag_unit.setSelected(self._split(r.get("unit_value", "")))
            self.chk_alt.setChecked(bool(r.get("exclude_alt", True)))
            self.chk_loss.setChecked(bool(r.get("negative_loss_required", True)))
            self.chk_dev_rate.setChecked(bool(r.get("dev_rate_required", False)))
            self.spin_dev_rate_min.setValue(float(r.get("dev_rate_min", 10)))
            self.spin_dev_rate_max.setValue(float(r.get("dev_rate_max", 100)))
            self.chk_dev_qty.setChecked(bool(r.get("dev_qty_required", False)))
            self.spin_dev_qty_min.setValue(float(r.get("dev_qty_min", 0)))
            self.spin_dev_qty_max.setValue(float(r.get("dev_qty_max", 1)))
            self.chk_workshop.setChecked(bool(r.get("workshop_required", False)))
            self.edit_workshop.setText(str(r.get("workshop_value", "")))
            self._set_remark_mode(r.get("remark_mode", "off"))
        finally:
            self._loading = False
        self._refresh_preview()

    def _known_categories(self):
        """类别候选：内置实测值 + 现有规则里出现过的取值（旧配置手填的不丢）。"""
        return self._merge_enum(_BUILTIN_CATEGORIES, "category_value")

    def _known_units(self):
        """单位候选：内置常用 + 现有规则里出现过的取值。"""
        return self._merge_enum(_BUILTIN_UNITS, "unit_value")

    def _merge_enum(self, builtin, key):
        out, seen = [], set()
        for v in list(builtin):
            if v not in seen:
                seen.add(v)
                out.append(v)
        for r in (self.cfg.get("rules") or []):
            for part in self._split(r.get(key, "")):
                if part not in seen:
                    seen.add(part)
                    out.append(part)
        return out

    # ---------------------------------------------------------------- 列表
    def _refresh_list(self):
        """重建左列行控件并刷新每条的命中数（数字来自生产同一匹配器）。

        开关状态取复选框而不是 ``self.cfg['enabled']``：勾上/取消总开关时配置还没
        保存，列表若读 cfg 就会「勾了没反应」，与底部预览条（读复选框）自相矛盾。
        """
        rules = self.cfg.get("rules", []) or []
        master_on = bool(self.chk_master.isChecked())
        stats = {}
        for s in compute_rule_hit_counts(self.df, {"enabled": master_on, "rules": rules}):
            stats[s["index"] - 1] = s
        total = 0 if self.df is None else len(self.df)

        self.list_rules.blockSignals(True)
        self.list_rules.clear()
        self._rows = []
        for i, r in enumerate(rules):
            item = QListWidgetItem()
            row = _RuleRow()
            st = stats.get(i, {})
            row.set_state(
                str(r.get("name", "未命名规则")),
                bool(r.get("enabled", True)),
                int(st.get("hits", 0)),
                total,
                master_on=master_on,
                no_data=(total == 0),
            )
            item.setSizeHint(row.sizeHint())
            self.list_rules.addItem(item)
            self.list_rules.setItemWidget(item, row)
            self._rows.append(row)
        if 0 <= self.current_index < self.list_rules.count():
            self.list_rules.setCurrentRow(self.current_index)
        self.list_rules.blockSignals(False)
        self._refresh_row_selection()
        self.btn_up.setEnabled(self.current_index > 0)
        self.btn_down.setEnabled(self.current_index < len(rules) - 1)
        self.btn_del.setEnabled(len(rules) > 1)

    def _refresh_row_selection(self):
        cur = self.list_rules.currentRow()
        for i, row in enumerate(self._rows):
            row.set_selected(i == cur)

    def _on_select_rule(self, idx):
        if idx < 0 or idx >= len(self.cfg.get("rules", []) or []):
            return
        self._commit_editor()
        self._load_rule_to_editor(idx)
        self._refresh_row_selection()
        self._refresh_list()

    # ---------------------------------------------------------------- 增删排序
    def _on_add(self):
        self._commit_editor()
        new_rule = dict(DEFAULT_RULE)
        new_rule["name"] = "新规则%d" % (len(self.cfg["rules"]) + 1)
        self.cfg["rules"].append(new_rule)
        self.current_index = len(self.cfg["rules"]) - 1
        self._load_rule_to_editor(self.current_index)
        self._refresh_list()

    def _on_del(self):
        if len(self.cfg["rules"]) <= 1:
            message_box.info(self, "无法删除", "至少保留一条规则。",
                             ok="知道了")
            return
        name = str(self.cfg["rules"][self.current_index].get("name", "未命名规则"))
        if not message_box.confirm(
                self, "删除规则",
                "删除「%s」？" % name,
                detail="只从配置里移除这条规则，已经隔离的记录不受影响。",
                yes="删除", no="取消"):
            return
        self._commit_editor()
        self.cfg["rules"].pop(self.current_index)
        self.current_index = min(self.current_index, len(self.cfg["rules"]) - 1)
        self._load_rule_to_editor(self.current_index)
        self._refresh_list()

    def _move(self, delta):
        i = self.current_index
        j = i + delta
        rules = self.cfg["rules"]
        if not (0 <= j < len(rules)):
            return
        self._commit_editor()
        rules[i], rules[j] = rules[j], rules[i]
        self.current_index = j
        self._load_rule_to_editor(j)
        self._refresh_list()
        self._refresh_preview()

    def _on_up(self):
        self._move(-1)

    def _on_down(self):
        self._move(1)

    # ---------------------------------------------------------------- 预览
    def set_df(self, df):
        """换主表（主表刷新后宿主可再调），命中数随之重算。"""
        self.df = df if df is not None else pd.DataFrame()
        self._refresh_list()
        self._refresh_preview()

    def _refresh_preview(self):
        """底部预览条：本条草稿规则在真实主表上的命中数 + 前 3 条样例。"""
        draft = self._collect_preview()
        got = describe_rule_hits(self.df, draft)
        hits = int(got["hits"])
        total = len(self.df)
        self.pv_num.setText(str(hits) if total else "—")
        extra = "条 · 占全表 %.1f%% · 涉及金额 %s" % (100.0 * got["ratio"], got["amount_text"])
        if not self.chk_master.isChecked():
            extra += " · 总开关已关，真跑时一条都不隔离"
        if not draft.get("enabled", True):
            extra += " · 本条已停用"
        self.pv_post.setText(extra if total else "条")
        if hits:
            self.pv_sample.setText("样例：" + " · ".join(got["samples"]))
        elif not total:
            self.pv_sample.setText("当前主表无数据：先「选表」再回来配规则")
        else:
            self.pv_sample.setText("当前主表 0 条命中 —— 条件太窄，或该列在这份数据里不存在")
        # 一句话摘要（旧版「当前规则预览」的信息量，挪进悬浮提示）
        self.setToolTip(build_rule_summary(draft))

    def _on_trial_run(self):
        """试跑：草稿替换进 cfg 后按「多规则优先级」真算一遍归属，仍不落库。"""
        draft = self._collect_preview()
        rules = [dict(r) for r in (self.cfg.get("rules") or [])]
        if 0 <= self.current_index < len(rules):
            rules[self.current_index] = draft
        probe = {"enabled": self.chk_master.isChecked(), "rules": rules}
        hit_ids = compute_auto_quarantine_ids(self.df, probe)
        reason = build_rule_reason(draft, self.current_index + 1)
        own = sum(1 for v in hit_ids.values() if v == reason)
        got = describe_rule_hits(self.df, draft, samples=5)
        total = 0 if self.df is None else len(self.df)
        self.pv_num.setText(str(got["hits"]))
        self.pv_post.setText(
            "条（试跑：全表净隔离 %d 条 · 本条归属 %d 条 · 占全表 %.1f%% · 涉及金额 %s）"
            % (len(hit_ids), own, 100.0 * got["ratio"], got["amount_text"]))
        self.pv_sample.setText(
            "试跑样例（最多 5 条）：" + " · ".join(got["samples"])
            if got["samples"] else
            ("当前主表无数据，试跑未执行" if not total else "试跑完成：本条草稿 0 条命中"))
        if total == 0:
            return
        message_box.info(
            self, "试跑完成（未落库）",
            "本条命中 %d 条 · 归属本条 %d 条 · 全表净隔离 %d 条"
            % (got["hits"], own, len(hit_ids)),
            ok="知道了")

    # ---------------------------------------------------------------- 保存
    def _on_save_clicked(self):
        self.saved.emit(self.save())

    def save(self):
        """提交编辑区并写盘，成功返回 True。"""
        self._commit_editor()
        self.cfg["enabled"] = self.chk_master.isChecked()
        try:
            save_auto_quarantine_config(self.cfg)
        except Exception as e:  # noqa: BLE001
            message_box.error(self, "保存失败", "写入配置文件失败。", exc=e)
            return False
        self._refresh_list()
        return True

    def summary_text(self):
        """全部启用规则的一句话摘要（宿主提示用，与 tooltip 同源）。"""
        return build_all_summary(self.cfg)


class AutoQuarantineRuleDialog(QDialog):
    """独立打开时的薄壳：承载 Widget + OK/Cancel（入口在第四期E 收敛到规则中心）。"""

    def __init__(self, parent=None, df=None):
        super().__init__(parent)
        dialog_chrome.apply(self, dialog_chrome.TIER_LARGE,
                            "自动隔离规则", "规则列表 / 三组条件 / 真实命中预览")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.widget = AutoQuarantineRuleWidget(self, df=df).wire_changed_signals()
        layout.addWidget(self.widget, 1)
        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok, parent=self)
        self.btn_box.button(QDialogButtonBox.Ok).setText("保存")
        self.btn_box.button(QDialogButtonBox.Cancel).setText("取消")
        self.btn_box.accepted.connect(self._on_accept)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)
        self.widget.saved.connect(self._on_widget_saved)

    def _on_widget_saved(self, ok):
        if ok:
            self.accept()

    def _on_accept(self):
        if self.widget.save():
            self.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = AutoQuarantineRuleDialog()
    dlg.show()
    sys.exit(app.exec())
