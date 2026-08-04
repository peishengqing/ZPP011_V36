# -*- coding: utf-8 -*-
"""自动已读规则配置 —— 可复用 Widget + 薄壳 Dialog。

支持「多条件 AND」：每条规则内含 conditions 数组，数组内所有条件同时满足才命中。
多条规则之间仍为 OR。
可被「规则中心」对话框以 Tab 形式嵌入；AutoReadRuleDialog 仅作为独立打开时的薄壳。
"""
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.auto_read_rules import (
    CONDITION_TYPES,
    build_rule_summary,
    load_auto_read_rules_config,
    save_auto_read_rules_config,
)

# 类型 combo 的显示顺序（与 CONDITION_TYPES 注册表一致）
_TYPE_ORDER = [
    "dev_qty_eq",
    "dev_qty_range",
    "dev_qty_gt",
    "dev_qty_lt",
    "dev_qty_gte",
    "dev_qty_lte",
    "actual_qty_eq",
    "actual_qty_gt",
    "actual_qty_gte",
    "actual_qty_lt",
    "actual_qty_lte",
    "mat_code_prefix",
    "mat_code_in",
    "mat_name_contains",
    "mat_type_eq",
]


def _default_params_for(t):
    """返回某条件类型的默认 params 字典。"""
    spec = CONDITION_TYPES[t]
    if spec["value_type"] == "range":
        d = spec["default"]
        return {"min": d.get("min", 0), "max": d.get("max", 1)}
    return {"value": spec["default"]}


class _ConditionRow(QWidget):
    """单条条件编辑行：类型下拉 + 参数输入 + 删除按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_widget = parent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.combo_type = QComboBox()
        for t in _TYPE_ORDER:
            self.combo_type.addItem(CONDITION_TYPES[t]["label"], t)
        layout.addWidget(self.combo_type, 0)

        self.param_container = QWidget()
        self.param_layout = QHBoxLayout(self.param_container)
        self.param_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.param_container, 1)

        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedWidth(28)
        self.btn_del.setToolTip("删除此条件")
        layout.addWidget(self.btn_del, 0)

        self._param_widget = None
        # 类型切换 → 重建参数输入
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        self.btn_del.clicked.connect(self._on_del_clicked)

    # ---- 参数控件
    def _build_param_widget(self, t, params):
        # 清旧
        while self.param_layout.count():
            item = self.param_layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.deleteLater()
        self._param_widget = None
        spec = CONDITION_TYPES[t]
        vt = spec["value_type"]
        if vt == "range":
            mn = QDoubleSpinBox()
            mn.setRange(-999999, 999999)
            mn.setDecimals(2)
            mn.setValue(float(params.get("min", 0)))
            mn.setPrefix("(")
            mx = QDoubleSpinBox()
            mx.setRange(-999999, 999999)
            mx.setDecimals(2)
            mx.setValue(float(params.get("max", 1)))
            mx.setPrefix(", ")
            mx.setSuffix(")")
            mn.valueChanged.connect(self._on_param_changed)
            mx.valueChanged.connect(self._on_param_changed)
            self.param_layout.addWidget(QLabel("偏差数量在"))
            self.param_layout.addWidget(mn)
            self.param_layout.addWidget(mx)
            self._param_widget = (mn, mx)
        elif vt == "number":
            w = QDoubleSpinBox()
            w.setRange(-999999, 999999)
            w.setDecimals(2)
            w.setValue(float(params.get("value", 0)))
            w.valueChanged.connect(self._on_param_changed)
            self.param_layout.addWidget(w)
            self._param_widget = w
        else:  # text / textlist
            w = QLineEdit()
            w.setText("" if params.get("value") is None else str(params.get("value")))
            w.setPlaceholderText(spec.get("hint", ""))
            w.textChanged.connect(self._on_param_changed)
            self.param_layout.addWidget(w)
            self._param_widget = w

    def _current_type(self):
        return self.combo_type.currentData() or "dev_qty_eq"

    def _read_params(self):
        t = self._current_type()
        spec = CONDITION_TYPES[t]
        vt = spec["value_type"]
        if vt == "range":
            mn, mx = self._param_widget
            return {"min": mn.value(), "max": mx.value()}
        if vt == "number":
            return {"value": self._param_widget.value()}
        return {"value": self._param_widget.text().strip()}

    def set_condition(self, cond):
        """用 dict 填充此行。"""
        t = cond.get("type") or "dev_qty_eq"
        if t not in CONDITION_TYPES:
            t = "dev_qty_eq"
        ti = self.combo_type.findData(t)
        if ti < 0:
            ti = 0
        self.combo_type.blockSignals(True)
        self.combo_type.setCurrentIndex(ti)
        self.combo_type.blockSignals(False)
        params = cond.get("params", _default_params_for(t))
        self._build_param_widget(t, params)

    def get_condition(self):
        return {"type": self._current_type(), "params": self._read_params()}

    # ---- 信号
    def _on_type_changed(self, _idx):
        t = self._current_type()
        self._build_param_widget(t, _default_params_for(t))
        self._notify_changed()

    def _on_param_changed(self, *_a):
        self._notify_changed()

    def _on_del_clicked(self):
        if self._parent_widget is not None:
            self._parent_widget._remove_condition_row(self)

    def _notify_changed(self):
        if self._parent_widget is not None:
            self._parent_widget._refresh_summary()


class AutoReadRuleWidget(QWidget):
    """自动已读规则管理器：多规则并存、独立启停、排序、每条规则多条件 AND。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = load_auto_read_rules_config()  # {'enabled', 'rules'}
        self.current_index = 0
        self._build_ui()
        self._refresh_list()
        self._load_rule_to_editor(0)

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # 总开关
        self.chk_master = QCheckBox("启用自动已读（总开关，关闭则完全不自动已读）")
        self.chk_master.setChecked(self.cfg.get("enabled", True))
        root.addWidget(self.chk_master)

        # 全局「排除未投料（实际数量=0）」开关
        self.chk_exclude_unfed = QCheckBox(
            "自动已读时排除未投料（实际数量=0）的行　"
            "⚠ 开启后默认挡掉所有实际=0 的行，可在下方逐规则勾选「包含未投料」豁免")
        self.chk_exclude_unfed.setChecked(self.cfg.get("exclude_unfed", False))
        self.chk_exclude_unfed.setToolTip(
            "未投料（实际数量=0）通常是替代料/非耗用，需要审计；开启此开关可避免它们被自动已读掉。"
            "600 等你确认保留的规则请勾选下方的「包含未投料」豁免。")
        root.addWidget(self.chk_exclude_unfed)

        # 规则列表 + 工具条
        head = QHBoxLayout()
        head.addWidget(QLabel("规则列表："))
        head.addStretch()
        self.btn_add = QPushButton("➕ 新增")
        self.btn_del = QPushButton("🗑 删除")
        self.btn_up = QPushButton("↑ 上移")
        self.btn_down = QPushButton("↓ 下移")
        for b in (self.btn_add, self.btn_del, self.btn_up, self.btn_down):
            head.addWidget(b)
        root.addLayout(head)

        self.list_rules = QListWidget()
        self.list_rules.currentRowChanged.connect(self._on_select_rule)
        root.addWidget(self.list_rules, 1)

        # 编辑区
        box = QGroupBox("规则编辑")
        ev = QVBoxLayout(box)
        ev.setSpacing(8)

        hn = QHBoxLayout()
        hn.addWidget(QLabel("规则名称："))
        self.edit_name = QLineEdit()
        hn.addWidget(self.edit_name)
        ev.addLayout(hn)

        self.chk_rule_enabled = QCheckBox("启用此规则")
        ev.addWidget(self.chk_rule_enabled)

        self.chk_ignore_exclude_unfed = QCheckBox(
            "本规则包含未投料（不受上面的「排除未投料」开关影响）")
        self.chk_ignore_exclude_unfed.setToolTip(
            "勾选后，即使全局开启了「排除未投料」，本条规则命中的实际=0 行仍会被自动已读。"
            "例如 600 物料你想保留未投料也自动已读，就勾这个。")
        ev.addWidget(self.chk_ignore_exclude_unfed)

        # 条件列表（多条件 AND）
        ev.addWidget(QLabel("条件（全部满足＝且关系，多条规则之间为或关系）："))
        self.cond_list = QVBoxLayout()
        self.cond_list.setSpacing(6)
        self.cond_widget = QWidget()
        self.cond_widget.setLayout(self.cond_list)
        ev.addWidget(self.cond_widget)

        h_add = QHBoxLayout()
        self.btn_add_cond = QPushButton("➕ 添加条件")
        h_add.addWidget(self.btn_add_cond)
        h_add.addStretch()
        ev.addLayout(h_add)

        ev.addWidget(QLabel("当前规则预览："))
        self.lbl_summary = QLabel()
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet(
            "color:#555; padding:6px; background:#f5f5f5; border-radius:4px;")
        ev.addWidget(self.lbl_summary)

        root.addWidget(box)

        # 信号
        self.edit_name.textChanged.connect(self._refresh_summary)
        self.chk_rule_enabled.stateChanged.connect(self._refresh_summary)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_del)
        self.btn_up.clicked.connect(self._on_up)
        self.btn_down.clicked.connect(self._on_down)
        self.btn_add_cond.clicked.connect(self._on_add_condition)

    # ---------------------------------------------------------------- 条件行管理
    def _clear_condition_rows(self):
        while self.cond_list.count():
            item = self.cond_list.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_condition_row(self, cond=None):
        row = _ConditionRow(self)
        if cond is not None:
            row.set_condition(cond)
        else:
            row.set_condition({"type": "dev_qty_eq", "params": _default_params_for("dev_qty_eq")})
        self.cond_list.addWidget(row)
        return row

    def _remove_condition_row(self, row_widget):
        # 至少保留 1 个条件
        if self.cond_list.count() <= 1:
            QMessageBox.information(self, "提示", "每条规则至少保留一个条件。")
            return
        idx = self.cond_list.indexOf(row_widget)
        if idx < 0:
            return
        item = self.cond_list.takeAt(idx)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        self._refresh_summary()

    def _read_conditions(self):
        conds = []
        for i in range(self.cond_list.count()):
            w = self.cond_list.itemAt(i).widget()
            if isinstance(w, _ConditionRow):
                conds.append(w.get_condition())
        return conds

    # ---------------------------------------------------------------- 数据
    def _commit_editor(self):
        if not (0 <= self.current_index < len(self.cfg["rules"])):
            return
        r = self.cfg["rules"][self.current_index]
        r["name"] = self.edit_name.text().strip() or "未命名规则"
        r["enabled"] = self.chk_rule_enabled.isChecked()
        r["ignore_exclude_unfed"] = self.chk_ignore_exclude_unfed.isChecked()
        r["conditions"] = self._read_conditions()

    def _load_rule_to_editor(self, idx):
        if not (0 <= idx < len(self.cfg["rules"])):
            return
        self.current_index = idx
        r = self.cfg["rules"][idx]
        self.edit_name.setText(r.get("name", ""))
        self.chk_rule_enabled.setChecked(bool(r.get("enabled", True)))
        self.chk_ignore_exclude_unfed.setChecked(bool(r.get("ignore_exclude_unfed", False)))
        # 条件列表
        self._clear_condition_rows()
        conds = r.get("conditions") or []
        if not conds:
            conds = [{"type": "dev_qty_eq", "params": _default_params_for("dev_qty_eq")}]
        for c in conds:
            self._add_condition_row(c)
        self._refresh_summary()

    def _on_add_condition(self):
        self._add_condition_row({"type": "dev_qty_eq", "params": _default_params_for("dev_qty_eq")})
        self._refresh_summary()

    def _refresh_list(self):
        self.list_rules.blockSignals(True)
        self.list_rules.clear()
        for i, r in enumerate(self.cfg["rules"]):
            name = r.get("name", "未命名规则")
            tag = "（已停用）" if not r.get("enabled", True) else ""
            self.list_rules.addItem(QListWidgetItem("%d. %s%s" % (i + 1, name, tag)))
        if 0 <= self.current_index < self.list_rules.count():
            self.list_rules.setCurrentRow(self.current_index)
        self.list_rules.blockSignals(False)

    def _on_select_rule(self, idx):
        if idx < 0 or idx >= len(self.cfg["rules"]):
            return
        self._commit_editor()
        self._load_rule_to_editor(idx)

    def _on_add(self):
        self._commit_editor()
        new_rule = {
            "name": "新规则%d" % (len(self.cfg["rules"]) + 1),
            "enabled": True,
            "conditions": [{"type": "dev_qty_eq", "params": _default_params_for("dev_qty_eq")}],
        }
        self.cfg["rules"].append(new_rule)
        self.current_index = len(self.cfg["rules"]) - 1
        self._refresh_list()
        self._load_rule_to_editor(self.current_index)

    def _on_del(self):
        if len(self.cfg["rules"]) <= 1:
            QMessageBox.information(self, "提示", "至少保留一条规则，无法删除。")
            return
        self._commit_editor()
        self.cfg["rules"].pop(self.current_index)
        self.current_index = min(self.current_index, len(self.cfg["rules"]) - 1)
        self._refresh_list()
        self._load_rule_to_editor(self.current_index)

    def _on_up(self):
        if self.current_index > 0:
            self._commit_editor()
            (self.cfg["rules"][self.current_index - 1],
             self.cfg["rules"][self.current_index]) = \
                (self.cfg["rules"][self.current_index],
                 self.cfg["rules"][self.current_index - 1])
            self.current_index -= 1
            self._refresh_list()
            self._load_rule_to_editor(self.current_index)

    def _on_down(self):
        if self.current_index < len(self.cfg["rules"]) - 1:
            self._commit_editor()
            (self.cfg["rules"][self.current_index + 1],
             self.cfg["rules"][self.current_index]) = \
                (self.cfg["rules"][self.current_index],
                 self.cfg["rules"][self.current_index + 1])
            self.current_index += 1
            self._refresh_list()
            self._load_rule_to_editor(self.current_index)

    def _refresh_summary(self):
        preview = {
            "name": self.edit_name.text().strip() or "未命名规则",
            "enabled": self.chk_rule_enabled.isChecked(),
            "conditions": self._read_conditions(),
        }
        self.lbl_summary.setText(build_rule_summary(preview))

    # ---------------------------------------------------------------- 保存
    def save(self):
        self._commit_editor()
        self.cfg["enabled"] = self.chk_master.isChecked()
        self.cfg["exclude_unfed"] = self.chk_exclude_unfed.isChecked()
        try:
            save_auto_read_rules_config(self.cfg)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", "写入配置文件失败：%s" % e)
            return False
        return True


class AutoReadRuleDialog(QDialog):
    """独立打开时的薄壳：承载 Widget + OK/Cancel。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ 自动已读规则")
        self.setMinimumWidth(620)
        self.setMinimumHeight(600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.widget = AutoReadRuleWidget(self)
        layout.addWidget(self.widget, 1)
        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok, parent=self)
        self.btn_box.button(QDialogButtonBox.Ok).setText("保存")
        self.btn_box.button(QDialogButtonBox.Cancel).setText("取消")
        self.btn_box.accepted.connect(self._on_accept)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)

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
