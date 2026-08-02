# -*- coding: utf-8 -*-
"""自动已读规则配置 —— 可复用 Widget + 薄壳 Dialog。

支持多条件类型（偏差数量=0 / 物料编码前缀 / 物料编码属于集合 / 物料名称包含 / 物料类型等于），
可被「规则中心」对话框以 Tab 形式嵌入；AutoReadRuleDialog 仅作为独立打开时的薄壳。
"""
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
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
    "mat_code_prefix",
    "mat_code_in",
    "mat_name_contains",
    "mat_type_eq",
]


class AutoReadRuleWidget(QWidget):
    """自动已读规则管理器：多规则并存、独立启停、排序、条件类型可选。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = load_auto_read_rules_config()  # {'enabled', 'rules'}
        self.current_index = 0
        # 防御：参数输入控件在 _load_rule_to_editor 中才创建。
        # 但 edit_name.setText / chk_rule_enabled.setChecked 会同步触发
        # textChanged / stateChanged → _refresh_summary → _read_param_value 提前访问它。
        # 先声明为 None，并由 _read_param_value 对 None 返回默认值，避免初始化期崩溃。
        self._param_input = None
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

        ht = QHBoxLayout()
        ht.addWidget(QLabel("条件类型："))
        self.combo_type = QComboBox()
        for t in _TYPE_ORDER:
            self.combo_type.addItem(CONDITION_TYPES[t]["label"], t)
        ht.addWidget(self.combo_type, 1)
        ev.addLayout(ht)

        # 参数输入区（按条件类型动态切换）
        hp = QHBoxLayout()
        hp.addWidget(QLabel("参数值："))
        self.param_container = QWidget()
        self.param_layout = QHBoxLayout(self.param_container)
        self.param_layout.setContentsMargins(0, 0, 0, 0)
        hp.addWidget(self.param_container, 1)
        ev.addLayout(hp)

        ev.addWidget(QLabel("当前规则预览："))
        self.lbl_summary = QLabel()
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet(
            "color:#555; padding:6px; background:#f5f5f5; border-radius:4px;")
        ev.addWidget(self.lbl_summary)

        root.addWidget(box)

        # 信号
        self.edit_name.textChanged.connect(self._refresh_summary)
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        self.chk_rule_enabled.stateChanged.connect(self._refresh_summary)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_del)
        self.btn_up.clicked.connect(self._on_up)
        self.btn_down.clicked.connect(self._on_down)

    # ---------------------------------------------------------------- 参数控件
    def _build_param_input(self, value_type, value):
        """根据 value_type 构造参数输入控件并返回。"""
        self._param_input = None
        if value_type == "number":
            w = QSpinBox()
            w.setRange(-999999, 999999)
            w.setValue(int(float(value)) if str(value).strip() not in ("", None) else 0)
            w.valueChanged.connect(self._refresh_summary)
            self._param_input = w
        else:  # text / textlist
            w = QLineEdit()
            w.setText("" if value is None else str(value))
            w.setPlaceholderText(CONDITION_TYPES[self._current_type()]["hint"])
            w.textChanged.connect(self._refresh_summary)
            self._param_input = w
        return w

    def _current_type(self):
        return self.combo_type.currentData() or "dev_qty_eq"

    def _read_param_value(self):
        spec = CONDITION_TYPES[self._current_type()]
        # 防御：参数控件尚未构建（如初始化期信号提前触发）时返回该类型默认值
        if self._param_input is None:
            return spec["default"]
        if spec["value_type"] == "number":
            return self._param_input.value()
        return self._param_input.text().strip()

    def _rebuild_param_input(self):
        # 清空旧控件
        while self.param_layout.count():
            item = self.param_layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.deleteLater()
        spec = CONDITION_TYPES[self._current_type()]
        val = spec["default"]
        w = self._build_param_input(spec["value_type"], val)
        self.param_layout.addWidget(w)

    # ---------------------------------------------------------------- 数据
    def _commit_editor(self):
        if not (0 <= self.current_index < len(self.cfg["rules"])):
            return
        r = self.cfg["rules"][self.current_index]
        r["name"] = self.edit_name.text().strip() or "未命名规则"
        r["enabled"] = self.chk_rule_enabled.isChecked()
        r["type"] = self._current_type()
        r["params"] = {"value": self._read_param_value()}

    def _load_rule_to_editor(self, idx):
        if not (0 <= idx < len(self.cfg["rules"])):
            return
        self.current_index = idx
        r = self.cfg["rules"][idx]
        self.edit_name.setText(r.get("name", ""))
        self.chk_rule_enabled.setChecked(bool(r.get("enabled", True)))
        # 类型
        t = r.get("type", "dev_qty_eq")
        if t not in CONDITION_TYPES:
            t = "dev_qty_eq"
        ti = self.combo_type.findData(t)
        if ti < 0:
            ti = 0
        self.combo_type.blockSignals(True)
        self.combo_type.setCurrentIndex(ti)
        self.combo_type.blockSignals(False)
        # 参数输入：先按类型重建，再填值
        spec = CONDITION_TYPES[t]
        while self.param_layout.count():
            item = self.param_layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.deleteLater()
        w = self._build_param_input(spec["value_type"], r.get("params", {}).get("value", spec["default"]))
        self.param_layout.addWidget(w)
        self._refresh_summary()

    def _on_type_changed(self, _idx):
        # 切换条件类型时，参数输入按新类型默认值重建
        self._rebuild_param_input()
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
            "type": "dev_qty_eq",
            "params": {"value": CONDITION_TYPES["dev_qty_eq"]["default"]},
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
            "type": self._current_type(),
            "params": {"value": self._read_param_value()},
        }
        self.lbl_summary.setText(build_rule_summary(preview))

    # ---------------------------------------------------------------- 保存
    def save(self):
        self._commit_editor()
        self.cfg["enabled"] = self.chk_master.isChecked()
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
        self.setMinimumWidth(580)
        self.setMinimumHeight(560)
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
