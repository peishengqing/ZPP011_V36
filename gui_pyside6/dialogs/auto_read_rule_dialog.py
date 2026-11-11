# -*- coding: utf-8 -*-
"""自动已读规则配置 —— 规则中心 Tab②（第四期D：与 Tab① 同一套形态）

改造前什么样
------------
一条从上到下的长表单：总开关、两个全局排除开关、规则列表（每行只有「1. 名称（已停
用）」一句文字，看不出命中多少），再一个 QGroupBox 塞规则名、两个豁免复选框、动态条
件行和一句自然语言摘要。配完规则只知道「写了什么」，不知道「会读掉谁」，尤其不知道
**实际=0（未投料）的行默认会被一起读掉**。

现在什么样
----------
· 左列 240px 规则列表：每条显示「命中 N 条 · 占比 x.x%」（数字来自生产同一个匹配器），
  停用灰显，底部写清「规则之间是或关系，上下顺序不改变哪些行被读掉」；
· 右列编辑区：抬头（名称 / 启用 / 编号 / ↑ ↓ / 删除）+ 语义行（条件 AND × 规则 OR）
  + 三张卡（条件 / 全局排除 / 本条规则的豁免）在固定高度里滚动 + 底部真实命中预览条
  （命中几条、真跑实际读掉几条、其中几条未投料、前 3 条样例）；
· 条件仍可增删（组内 AND），每行收成「且 + 类型下拉 + 参数」，示例写在悬浮提示里。

四条硬约束
----------
1. **持久化 schema 一个键不动**：每条规则仍只有 ``name / enabled /
   ignore_exclude_unfed / ignore_exclude_units / conditions`` 五个键，
   ``config/auto_read_rules.json`` 不需要迁移。
2. **匹配语义不动**：条件组内 AND、规则之间 OR（**并集** —— 列表顺序不改变哪些行被
   读掉，``mark_read_batch`` 只记 ``read_source='auto'``，不记规则名）、全局两个排除
   开关可被逐条豁免、缺列保守不匹配 —— 判定全在 ``core/auto_read_rules.py``，本文件
   只做输入与展示。
3. **预览只读且与生产同源**：命中数走 ``compute_read_rule_hit_counts`` /
   ``describe_read_rule_hits``，试跑走 ``compute_auto_read_mask``，与真跑
   （``QuarantineManagerController._auto_read_by_rules``）同一个匹配器、同一份全局排
   除。「真跑会读掉几条」用 ``read_scope_mask``（未读 且 不在隔离区）算 —— 隔离区记录
   由「隔离区已读对账」专门管，规则中心不碰。
4. **实际=0 红线不许粉饰**：命中里含几条未投料，预览条与试跑弹窗都要正面说；没有
   「实际数量」列时说「无从判断」，不许把 0 说成「不含未投料」；主表没有 ``_read`` 列
   时不许断言「一条都没读掉」。界面上不出现任何「已处理」暗示。
"""
import pandas as pd

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

from core.auto_read_rules import (
    CONDITION_TYPES,
    build_rule_summary,
    compute_auto_read_mask,
    compute_read_rule_hit_counts,
    count_unfed_rows,
    describe_read_rule_hits,
    load_auto_read_rules_config,
    read_scope_mask,
    save_auto_read_rules_config,
)
from gui_pyside6.components import dialog_chrome, message_box
from gui_pyside6.dialogs.rule_editor_kit import (
    BODY_MIN_H,
    FINPUT_H,
    LAYOUT_MIN_H,
    LIST_W,
    ROW_GAP,
    RuleRow,
    card,
    fcheck,
    fhint,
    flabel,
    fline,
    fspin,
    style_tab,
)
from gui_pyside6.themes.tokens import FONT_PT, SIZE_PX
from gui_pyside6.utils.icons import get_icon

# 类型 combo 的显示顺序（与 CONDITION_TYPES 注册表一致）
_TYPE_ORDER = [
    "dev_qty_eq",
    "dev_qty_range",
    "dev_qty_gt",
    "dev_qty_lt",
    "dev_qty_gte",
    "dev_qty_lte",
    "dev_rate_eq",
    "dev_rate_range",
    "dev_rate_gt",
    "dev_rate_lt",
    "dev_rate_gte",
    "dev_rate_lte",
    "actual_qty_eq",
    "actual_qty_gt",
    "actual_qty_gte",
    "actual_qty_lt",
    "actual_qty_lte",
    "mat_code_prefix",
    "mat_code_in",
    "mat_name_contains",
    "mat_name_not_contains",
    "mat_type_eq",
]

# 兜底：core 侧 CONDITION_TYPES 新增条件类型（如 v43.110 的 factory_eq）时自动纳入 combo，
# 避免「对话框类型清单与 core 注册表不同步 → 加载含该类型的规则时 findData 返回 -1 降级 index0，
# combo(dev_qty_eq/number) 与实建 text 控件错位 → _read_params 调 .value() 撞 QLineEdit 崩」。
# 追加在末尾不影响既有分组显示顺序。
for _t in CONDITION_TYPES:
    if _t not in _TYPE_ORDER:
        _TYPE_ORDER.append(_t)

#: 本页特有的选择器：条件下拉、行首「且」、预览条的红线那一行。规则列表 / 条件卡 /
#: 命中预览条那一整套在 ``rule_editor_kit.RULE_TAB_QSS``，Tab① 共用同一份。
_EXTRA_QSS = f"""
QComboBox#condType {{
    height: {FINPUT_H}px; padding: 0 8px; border-radius: {SIZE_PX["radiusSm"]}px;
    border: 1px solid $border; background: $surface; color: $text;
    font-size: {FONT_PT["note"]}px;
}}
QComboBox#condType:hover, QComboBox#condType:focus {{ border-color: $primarySoftBd; }}
QComboBox#condType::drop-down {{ border: none; width: 18px; }}
QLabel#condAnd {{
    font-size: {FONT_PT["aux"]}px; font-weight: 700; color: $primaryHover;
    min-width: 22px;
}}
QLabel#pvRed {{ font-size: {FONT_PT["aux"]}px; color: $warn; }}
QWidget#condHolder {{ background: transparent; }}
"""


def _default_params_for(t):
    """返回某条件类型的默认 params 字典。"""
    spec = CONDITION_TYPES[t]
    if spec["value_type"] == "range":
        d = spec["default"]
        return {"min": d.get("min", 0), "max": d.get("max", 1)}
    return {"value": spec["default"]}


def _default_condition():
    return {"type": "dev_qty_eq", "params": _default_params_for("dev_qty_eq")}


class _ConditionRow(QWidget):
    """一条条件：行首「且」+ 类型下拉 + 参数输入 + 删除按钮。

    改动通过宿主 ``_on_editor_changed()`` 上报而不是自己发 Signal：条件行是动态增删
    的，宿主接线那一刻它们还不存在，逐个连线必然漏掉后加的行。
    """

    def __init__(self, host, cond=None):
        super().__init__(host)
        self._host = host
        self._param = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.lbl_and = QLabel("且")
        self.lbl_and.setObjectName("condAnd")
        self.lbl_and.setToolTip("同一条规则内的条件要**全部满足**才算命中本条规则")
        lay.addWidget(self.lbl_and)

        self.combo_type = QComboBox()
        self.combo_type.setObjectName("condType")
        for t in _TYPE_ORDER:
            self.combo_type.addItem(CONDITION_TYPES[t]["label"], t)
        self.combo_type.setMinimumWidth(148)
        self.combo_type.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        lay.addWidget(self.combo_type)

        self.param_container = QWidget()
        self._param_layout = QHBoxLayout(self.param_container)
        self._param_layout.setContentsMargins(0, 0, 0, 0)
        self._param_layout.setSpacing(6)
        lay.addWidget(self.param_container, 1)
        lay.addStretch(1)

        self.btn_del = QToolButton()
        self.btn_del.setObjectName("ruleTool")
        self.btn_del.setIcon(get_icon("close", 12))
        self.btn_del.setToolTip("删除此条件（每条规则至少保留一个条件）")
        lay.addWidget(self.btn_del)

        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        self.btn_del.clicked.connect(lambda _c=False: self._host._remove_condition_row(self))
        self.set_condition(cond or _default_condition())

    def set_index(self, i):
        """首行写「若」、后续行写「且」，让 AND 关系从行首就能读出来。"""
        self.lbl_and.setText("若" if i == 0 else "且")

    # ---- 参数控件
    def _clear_params(self):
        while self._param_layout.count():
            item = self._param_layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.deleteLater()
        self._param = None

    def _build_param_widget(self, t, params):
        self._clear_params()
        spec = CONDITION_TYPES[t]
        vt = spec["value_type"]
        hint = str(spec.get("hint", ""))
        if vt == "range":
            d = spec["default"]
            mn = fspin(-999999, 999999, float(params.get("min", d.get("min", 0))))
            mx = fspin(-999999, 999999, float(params.get("max", d.get("max", 1))))
            for w in (mn, mx):
                w.valueChanged.connect(self._on_param_changed)
                w.setToolTip(hint)
            self._param_layout.addWidget(flabel(spec.get("param_label", "范围在")))
            self._param_layout.addWidget(mn)
            self._param_layout.addWidget(fhint("~"))
            self._param_layout.addWidget(mx)
            self._param_layout.addWidget(fhint("开区间，不含端点"))
            self._param = (mn, mx)
        elif vt == "number":
            sp = fspin(-999999, 999999, float(params.get("value", spec["default"])), width=96)
            sp.valueChanged.connect(self._on_param_changed)
            sp.setToolTip(hint)
            self._param_layout.addWidget(sp)
            if t.startswith("dev_rate"):
                self._param_layout.addWidget(fhint("%"))
            self._param = sp
        else:  # text / textlist
            edit = fline(hint)
            edit.setText("" if params.get("value") is None else str(params.get("value")))
            edit.setMinimumWidth(170)
            edit.textChanged.connect(self._on_param_changed)
            edit.setToolTip(hint)
            self._param_layout.addWidget(edit)
            self._param = edit
        # 参数一律左靠：QHBoxLayout 在没有可伸缩项时会把剩余空间摊到控件之间，
        # 数字类条件（只有一个 spinbox）就会被推到中间，看着像缺了个字段。
        self._param_layout.addStretch(1)

    def _current_type(self):
        return self.combo_type.currentData() or "dev_qty_eq"

    def _read_params(self):
        spec = CONDITION_TYPES[self._current_type()]
        vt = spec["value_type"]
        if vt == "range":
            mn, mx = self._param
            return {"min": mn.value(), "max": mx.value()}
        if vt == "number":
            return {"value": self._param.value()}
        return {"value": self._param.text().strip()}

    def set_condition(self, cond):
        """用 dict 填充此行（回填期不上报改动）。"""
        cond = cond if isinstance(cond, dict) else {}
        t = cond.get("type")
        if t not in CONDITION_TYPES:
            t = "dev_qty_eq"
        params = cond.get("params") if isinstance(cond.get("params"), dict) \
            else _default_params_for(t)
        self.combo_type.blockSignals(True)
        self.combo_type.setCurrentIndex(max(0, self.combo_type.findData(t)))
        self.combo_type.blockSignals(False)
        self.combo_type.setToolTip(str(CONDITION_TYPES[t].get("hint", "")))
        self._build_param_widget(t, params)

    def get_condition(self):
        return {"type": self._current_type(), "params": self._read_params()}

    def _on_type_changed(self, _idx):
        t = self._current_type()
        self.combo_type.setToolTip(str(CONDITION_TYPES[t].get("hint", "")))
        self._build_param_widget(t, _default_params_for(t))
        self._host._on_editor_changed()

    def _on_param_changed(self, *_a):
        self._host._on_editor_changed()


class AutoReadRuleWidget(QWidget):
    """规则中心 Tab②：左列规则列表 + 右列条件卡 / 全局排除 / 豁免 + 真实命中预览。"""

    #: 保存成功/失败（供宿主对话框收尾：中心对话框据此 accept，薄壳据此提示）
    saved = Signal(bool)

    def __init__(self, parent=None, df=None):
        super().__init__(parent)
        self.setObjectName("ruleTab")
        self.cfg = load_auto_read_rules_config()   # {'enabled','rules','exclude_*'}
        self.df = df if df is not None else pd.DataFrame()
        self.current_index = 0
        self._loading = False                       # 回填期屏蔽「草稿已改」重算
        self._rows_cond = []                        # 当前编辑中的条件行
        self._build_ui()
        style_tab(self, _EXTRA_QSS)
        self._load_rule_to_editor(0)
        self._refresh_list()

    # ---------------------------------------------------------------- UI 骨架
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setMinimumHeight(LAYOUT_MIN_H)
        root.addWidget(self._build_list_panel())
        root.addWidget(self._build_editor(), 1)

    def _build_list_panel(self):
        panel = QFrame()
        panel.setObjectName("ruleListPanel")
        panel.setFixedWidth(LIST_W)
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
        self.btn_add.setToolTip("在列表末尾追加一条规则（默认一个条件：偏差数量等于 0）")
        hl.addWidget(title)
        hl.addStretch(1)
        hl.addWidget(self.btn_add)
        lay.addWidget(head)

        self.chk_master = QCheckBox("启用自动已读（总开关）")
        self.chk_master.setObjectName("masterCheck")
        self.chk_master.setChecked(bool(self.cfg.get("enabled", True)))
        self.chk_master.setToolTip(
            "关闭后：分析完成时不做任何自动已读，下面每条规则的命中数也不再计入")
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
        self._rows = []                             # index -> RuleRow
        self.list_rules.currentRowChanged.connect(self._on_select_rule)
        lay.addWidget(self.list_rules, 1)

        foot = QLabel("规则之间是<b>或</b>关系：命中任意一条即自动已读。"
                      "<b>上下顺序不改变哪些行被读掉</b>，排序只影响这里的阅读顺序。")
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
        self.btn_up.setIcon(get_icon("chevron-up", 14))
        self.btn_up.setToolTip("把本条规则往前挪一位（只改这里的阅读顺序，不影响命中）")
        self.btn_down = QToolButton()
        self.btn_down.setObjectName("ruleTool")
        self.btn_down.setIcon(get_icon("chevron-down", 14))
        self.btn_down.setToolTip("把本条规则往后挪一位")
        self.btn_del = QPushButton("删除")
        self.btn_del.setProperty("role", "btn-outline")
        self.btn_del.setToolTip("删除本条规则（至少保留一条）")
        for w in (self.btn_up, self.btn_down, self.btn_del):
            hl.addWidget(w)
        return top

    def _build_sem(self):
        """语义行：把「条件 AND、规则 OR」这句人话写出来，而不是让用户猜。"""
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(14, 8, 14, 6)
        hl.setSpacing(0)
        for text, obj in (("条件 全部满足", "semBox"), ("AND", "semOp"), ("×", "semX"),
                          ("OR", "semOp"), ("×", "semX"), ("规则 任一命中", "semBox")):
            lbl = QLabel(text)
            lbl.setObjectName(obj)
            hl.addWidget(lbl)
        hl.addStretch(1)
        note = QLabel("任一规则命中即自动已读")
        note.setObjectName("semNote")
        hl.addWidget(note)
        return row

    def _build_body(self):
        scroll = QScrollArea()
        scroll.setObjectName("ruleBody")
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(BODY_MIN_H)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(10)

        # —— 卡 1：条件（组内 AND）——
        g1, b1 = card("sliders", "条件", logic="组内 AND")
        self.cond_rows = QVBoxLayout()
        self.cond_rows.setContentsMargins(0, 0, 0, 0)
        self.cond_rows.setSpacing(6)
        holder = QWidget()
        holder.setObjectName("condHolder")
        holder.setLayout(self.cond_rows)
        b1.addWidget(holder)

        r = QHBoxLayout()
        r.setSpacing(ROW_GAP)
        self.btn_add_cond = QPushButton("+ 添加条件")
        self.btn_add_cond.setProperty("role", "btn-outline")
        self.btn_add_cond.setToolTip("再加一条条件：本条规则要同时满足所有条件")
        r.addWidget(self.btn_add_cond)
        r.addStretch(1)
        b1.addLayout(r)

        tip = fhint("每种条件类型的示例与含义写在控件悬浮提示里。数据里没有对应的列时，"
                    "该条件按不命中处理（保守，不会误读）。")
        tip.setWordWrap(True)
        b1.addWidget(tip)
        v.addWidget(g1)

        # —— 卡 2：全局排除（所有规则共用）——
        g2, b2 = card("shield", "全局排除（所有规则共用）", tone="warn", logic="开关")
        self.chk_exclude_unfed = fcheck("排除未投料（实际数量=0）的行")
        self.chk_exclude_unfed.setToolTip(
            "开着：实际=0 的行即使条件命中也不自动已读，留在未读里等人工看。\n"
            "关着：条件命中就会把它们一起读掉 —— 默认是关着。")
        b2.addWidget(self.chk_exclude_unfed)
        h = fhint("两个排除开关默认都是<b>关</b>：关着时只要条件命中，实际=0（未投料）的行"
                  "也会被一起读掉。底部预览条会照实报「其中几条未投料」。")
        h.setTextFormat(Qt.RichText)
        h.setWordWrap(True)
        b2.addWidget(h)

        self.chk_exclude_units = fcheck("排除指定单位（留给我重点看）")
        self.chk_exclude_units.setToolTip(
            "开着：单位命中下方清单的行不自动已读（如 G、个 这类你想重点看的）。")
        b2.addWidget(self.chk_exclude_units)

        r = QHBoxLayout()
        r.setSpacing(ROW_GAP)
        r.addWidget(flabel("排除单位清单"))
        self.edit_excluded_units = fline("逗号分隔，例如 G,个（中英文逗号均可）")
        r.addWidget(self.edit_excluded_units, 1)
        b2.addLayout(r)
        h2 = fhint("忽略大小写。清单为空、或这份数据里没有「单位」列时，这个开关不起作用"
                   "（不会把所有行都排掉）。")
        h2.setWordWrap(True)
        b2.addWidget(h2)
        v.addWidget(g2)

        # —— 卡 3：本条规则的豁免 ——
        g3, b3 = card("unlock", "本条规则的豁免", logic="可选")
        self.chk_ignore_unfed = fcheck("本条包含未投料（不受上面「排除未投料」影响）")
        b3.addWidget(self.chk_ignore_unfed)
        h = fhint("只有你确认「即使没投料也直接已读」的才勾。勾上后预览条会写"
                  "「其中 N 条实际=0（未投料）—— 现在会被一起自动已读」，不藏着。")
        h.setWordWrap(True)
        b3.addWidget(h)

        self.chk_ignore_units = fcheck("本条包含排除清单里的单位（不受上面「排除单位」影响）")
        b3.addWidget(self.chk_ignore_units)
        h = fhint("默认规则「物料600开头」带着两个豁免（历史配置迁移时自动补上），"
                  "取消勾选就改回跟随全局开关。")
        h.setWordWrap(True)
        b3.addWidget(h)
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

        self.pv_red = QLabel()
        self.pv_red.setObjectName("pvRed")
        self.pv_red.setWordWrap(True)
        self.pv_red.setVisible(False)
        lv.addWidget(self.pv_red)

        self.pv_sample = QLabel("主表无数据时不计算命中")
        self.pv_sample.setObjectName("pvSample")
        self.pv_sample.setWordWrap(True)
        lv.addWidget(self.pv_sample)
        hl.addWidget(left, 1)

        self.btn_trial = QPushButton("试跑（只预览不落库）")
        self.btn_trial.setProperty("role", "btn-outline")
        self.btn_trial.setToolTip(
            "把当前草稿换进规则列表，按生产同一套匹配器再算一遍。\n"
            "只读：不写配置、不标已读、不碰隔离区。")
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
        ``_load_rule_to_editor`` 会逐字段回填，回填完之后再连，既省掉无谓重算，
        也不会把「回填」误当成「用户改动」。条件行自己调 ``_on_editor_changed``，
        所以这里不用管它们。
        """
        for w in (self.edit_name, self.edit_excluded_units):
            w.textChanged.connect(self._on_editor_changed)
        for w in (self.chk_rule_enabled, self.chk_master, self.chk_exclude_unfed,
                  self.chk_exclude_units, self.chk_ignore_unfed, self.chk_ignore_units):
            w.stateChanged.connect(self._on_editor_changed)
        # 总开关与两个全局开关动的是整列的「计不计命中」口径，光重算预览不够
        self.chk_master.toggled.connect(lambda _on: self._refresh_list())
        self.chk_exclude_unfed.toggled.connect(lambda _on: self._refresh_list())
        self.chk_exclude_units.toggled.connect(lambda _on: self._refresh_list())
        self.edit_excluded_units.textChanged.connect(lambda _t: self._refresh_list())
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_del)
        self.btn_up.clicked.connect(self._on_up)
        self.btn_down.clicked.connect(self._on_down)
        self.btn_add_cond.clicked.connect(self._on_add_condition)
        self.btn_trial.clicked.connect(self._on_trial_run)
        self.btn_save.clicked.connect(self._on_save_clicked)
        return self

    # ---------------------------------------------------------------- 草稿 <-> 控件
    def _collect_preview(self):
        """把编辑区当前内容收成一条完整规则字典（不落盘，供预览/试跑用）。

        必须给满这 5 个键：``conditions`` 残缺，预览就是拿半条规则在算；两个
        ``ignore_*`` 残缺，全局排除开关就会在预览里错误地生效或失效。
        """
        return {
            "name": self.edit_name.text().strip() or "未命名规则",
            "enabled": self.chk_rule_enabled.isChecked(),
            "ignore_exclude_unfed": self.chk_ignore_unfed.isChecked(),
            "ignore_exclude_units": self.chk_ignore_units.isChecked(),
            "conditions": self._read_conditions(),
        }

    def _globals_draft(self):
        """当前草稿的全局口径（取复选框而不是 ``self.cfg``：改动还没保存）。

        预览与试跑都要按这个算，否则会出现「开关刚勾上、数字还是老的」。
        """
        return {
            "enabled": bool(self.chk_master.isChecked()),
            "exclude_unfed": bool(self.chk_exclude_unfed.isChecked()),
            "exclude_units": bool(self.chk_exclude_units.isChecked()),
            "excluded_units": self.edit_excluded_units.text().strip(),
        }

    def _cfg_draft(self, rules=None):
        cfg = dict(self._globals_draft())
        cfg["rules"] = rules if rules is not None else (self.cfg.get("rules") or [])
        return cfg

    def _commit_editor(self):
        """把编辑区写回 ``self.cfg['rules'][current_index]``（仍在内存，未落盘）。

        用 ``update`` 而不是整体替换：配置里若有本编辑器不认识的历史键（旧版本写入的
        ``type`` / ``params`` 之类），整体替换会把它们静默删掉。
        """
        if not (0 <= self.current_index < len(self.cfg["rules"])):
            return
        self.cfg["rules"][self.current_index].update(self._collect_preview())

    def _load_rule_to_editor(self, idx):
        rules = self.cfg.get("rules", []) or []
        if not (0 <= idx < len(rules)):
            return
        self.current_index = idx
        r = rules[idx]
        self._loading = True
        try:
            self.edit_name.setText(str(r.get("name", "")))
            self.chk_rule_enabled.setChecked(bool(r.get("enabled", True)))
            self.lbl_id.setText("编号 R-%03d" % (idx + 1))
            self.chk_ignore_unfed.setChecked(bool(r.get("ignore_exclude_unfed", False)))
            self.chk_ignore_units.setChecked(bool(r.get("ignore_exclude_units", False)))
            self._clear_condition_rows()
            conds = [c for c in (r.get("conditions") or []) if isinstance(c, dict)]
            for c in (conds or [_default_condition()]):
                self._add_condition_row(c)
        finally:
            self._loading = False
        self._refresh_preview()

    # ---------------------------------------------------------------- 条件行
    def _clear_condition_rows(self):
        while self.cond_rows.count():
            item = self.cond_rows.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._rows_cond = []

    def _add_condition_row(self, cond=None):
        row = _ConditionRow(self, cond or _default_condition())
        self.cond_rows.addWidget(row)
        self._rows_cond.append(row)
        self._reindex_cond_rows()
        return row

    def _remove_condition_row(self, row_widget):
        if len(self._rows_cond) <= 1:
            message_box.info(self, "无法删除", "每条规则至少保留一个条件。")
            return
        if row_widget in self._rows_cond:
            self._rows_cond.remove(row_widget)
        idx = self.cond_rows.indexOf(row_widget)
        if idx >= 0:
            item = self.cond_rows.takeAt(idx)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._reindex_cond_rows()
        self._on_editor_changed()
        self._refresh_list()

    def _reindex_cond_rows(self):
        for i, row in enumerate(self._rows_cond):
            row.set_index(i)

    def _read_conditions(self):
        return [w.get_condition() for w in self._rows_cond]

    def _on_add_condition(self):
        self._add_condition_row()
        self._on_editor_changed()
        self._refresh_list()

    # ---------------------------------------------------------------- 列表
    def _refresh_list(self):
        """重建左列行控件并刷新每条的命中数（数字来自生产同一匹配器）。

        开关状态取复选框而不是 ``self.cfg``：勾上/取消总开关或全局排除时配置还没
        保存，列表若读 cfg 就会「勾了没反应」，与底部预览条（读复选框）自相矛盾。
        """
        rules = self.cfg.get("rules", []) or []
        master_on = bool(self.chk_master.isChecked())
        probe = self._cfg_draft()
        stats = {}
        for s in compute_read_rule_hit_counts(self.df, probe):
            stats[s["index"] - 1] = s
        total = 0 if self.df is None else len(self.df)

        self.list_rules.blockSignals(True)
        self.list_rules.clear()
        self._rows = []
        for i, r in enumerate(rules):
            item = QListWidgetItem()
            row = RuleRow()
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
        new_rule = {
            "name": "新规则%d" % (len(self.cfg["rules"]) + 1),
            "enabled": True,
            "ignore_exclude_unfed": False,
            "ignore_exclude_units": False,
            "conditions": [_default_condition()],
        }
        self.cfg["rules"].append(new_rule)
        self.current_index = len(self.cfg["rules"]) - 1
        self._load_rule_to_editor(self.current_index)
        self._refresh_list()

    def _on_del(self):
        if len(self.cfg["rules"]) <= 1:
            message_box.info(self, "无法删除", "至少保留一条规则。")
            return
        name = str(self.cfg["rules"][self.current_index].get("name", "未命名规则"))
        if not message_box.confirm(
                self, "删除规则",
                "删除「%s」？" % name,
                detail="只从配置里移除这条规则，已经标过已读的行不受影响。",
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
        """底部预览条：本条草稿在真实主表上的命中数、真跑实际读掉几条、其中几条未投料。

        长短句分工是按宽度算的：主行（pv_post）不换行、参与最小宽度计算，所以只放
        「条 · 占全表 x% · 真跑实际读掉 P 条」；口径解释、停用/总开关/无已读列这些
        需要说清的话全放进会换行的红线行（pv_red）。都塞主行会把这一页的最小宽度顶到
        1078px，撑破 large 档位（960px）。
        """
        draft = self._collect_preview()
        globals_ = self._globals_draft()
        got = describe_read_rule_hits(self.df, draft, globals_)
        total = len(self.df)
        hits = int(got["hits"])
        self.pv_num.setText(str(hits) if total else "—")

        main = "条"
        if total:
            main = "条 · 占全表 %.1f%%" % (100.0 * got["ratio"])

        red = []
        if hits:
            red.append(str(got["unfed_text"]))
        if got["blocked_by"]:
            red.append("已被全局开关挡掉：" + "、".join(got["blocked_by"]))
        if not total:
            pass
        elif not globals_["enabled"]:
            red.append("总开关已关，真跑时一条都不会读")
        elif not draft["enabled"]:
            red.append("本条已停用，真跑时它一条都不读")
        elif not got["pending_known"]:
            red.append("主表还没有「已读」列，说不准真跑会读掉几条")
        else:
            main += " · 真跑实际读掉 %d 条" % got["pending_hits"]
            skipped = hits - int(got["pending_hits"])
            if skipped:
                red.append("真跑实际读掉 %d 条：另外 %d 条已读过或在隔离区"
                           "（隔离区记录由「隔离区已读对账」专门管理）"
                           % (got["pending_hits"], skipped))
        self.pv_post.setText(main)
        self.pv_post.setToolTip(
            "「真跑实际读掉」= 命中本条规则、且当前未读、且不在隔离区的行数")
        self.pv_red.setText("　".join(red))
        self.pv_red.setVisible(bool(red))

        if not total:
            self.pv_sample.setText("当前主表无数据：先「选表」再回来配规则")
        elif hits:
            self.pv_sample.setText("样例：" + " · ".join(got["samples"]))
        else:
            self.pv_sample.setText("当前主表 0 条命中 —— 条件太窄，或该条件对应的列在这份数据里不存在")
        self.setToolTip(build_rule_summary(draft))

    def _on_trial_run(self):
        """试跑：草稿换进规则列表后按生产同一套匹配器算总数，仍不落库。"""
        draft = self._collect_preview()
        rules = [dict(r) for r in (self.cfg.get("rules") or [])]
        if 0 <= self.current_index < len(rules):
            rules[self.current_index] = draft
        probe = self._cfg_draft(rules)
        total = 0 if self.df is None else len(self.df)
        if not total or "data_id" not in self.df.columns:
            self._refresh_preview()
            message_box.info(self, "试跑未执行", "当前主表没有数据（或缺 data_id）。",
                             ok="知道了")
            return

        union, _per_rule = compute_auto_read_mask(self.df, probe)
        scope = read_scope_mask(self.df)
        got = describe_read_rule_hits(self.df, draft, probe, samples=5)
        n_own = int(got["hits"])
        n_would = int(union.sum())
        n_will = int((union & scope).sum()) if scope is not None else n_would
        unfed = count_unfed_rows(self.df, union)

        self.pv_num.setText(str(n_own))
        self.pv_post.setText("条（试跑：合计符合 %d · 实际读掉 %d）" % (n_would, n_will))
        self.pv_sample.setText(
            "试跑样例（最多 5 条）：" + " · ".join(got["samples"]) if got["samples"]
            else "试跑完成：本条草稿 0 条命中")

        main = "本条草稿命中 %d 条 · 合计符合 %d 条 · 真跑会读掉 %d 条" % (
            n_own, n_would, n_will)
        lines = ["试跑只算不写：不写配置、不标已读、不碰隔离区。"]
        if unfed is None:
            lines.append("这份数据里没有「实际数量」列，未投料（实际=0）有几条无从判断。")
        elif unfed:
            lines.append("合计命中的行里有 %d 条实际=0（未投料），真跑会被一起标为已读。"
                         "想留住它们请勾「排除未投料」，或把对应单位列进「排除单位清单」。"
                         % unfed)
        else:
            lines.append("合计命中的行里没有实际=0（未投料）行。")
        lines.append("「真跑会读掉」= 符合规则 且 当前未读 且 不在隔离区；隔离区记录由"
                     "「隔离区已读对账」专门管理，规则中心不碰。"
                     if scope is not None else
                     "主表还没有「已读」列（尚未分析完成），「真跑会读掉」暂按符合规则的条数给上限。")
        detail = "\n".join(lines)
        if unfed:
            message_box.warn(self, "试跑完成（未落库）", main, detail=detail, ok="知道了")
        else:
            message_box.info(self, "试跑完成（未落库）", main, ok="知道了")

    # ---------------------------------------------------------------- 保存
    def _on_save_clicked(self):
        self.saved.emit(self.save())

    def save(self):
        """提交编辑区与全局设置并写盘，成功返回 True。"""
        self._commit_editor()
        self.cfg["enabled"] = self.chk_master.isChecked()
        self.cfg["exclude_unfed"] = self.chk_exclude_unfed.isChecked()
        self.cfg["exclude_units"] = self.chk_exclude_units.isChecked()
        self.cfg["excluded_units"] = self.edit_excluded_units.text().strip()
        try:
            save_auto_read_rules_config(self.cfg)
        except Exception as e:  # noqa: BLE001
            message_box.error(self, "保存失败", "写入配置文件失败。", exc=e)
            return False
        self._refresh_list()
        return True


class AutoReadRuleDialog(QDialog):
    """独立打开时的薄壳：承载 Widget + OK/Cancel（入口在第四期E 收敛到规则中心）。"""

    def __init__(self, parent=None, df=None):
        super().__init__(parent)
        dialog_chrome.apply(self, dialog_chrome.TIER_LARGE,
                            "自动已读规则", "条件清单 / 全局排除 / 真实命中预览")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.widget = AutoReadRuleWidget(self, df=df).wire_changed_signals()
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
    dlg = AutoReadRuleDialog()
    dlg.show()
    sys.exit(app.exec())
