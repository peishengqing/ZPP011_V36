# -*- coding: utf-8 -*-
"""自动隔离规则配置 —— 可复用 Widget + 薄壳 Dialog。

AutoQuarantineRuleWidget 承载全部 UI 与逻辑，可被「规则中心」对话框以 Tab 形式嵌入；
AutoQuarantineRuleDialog 仅作为独立打开时的薄壳（保留工具栏按钮原行为）。
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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.auto_quarantine import (
    DEFAULT_RULE,
    build_rule_summary,
    load_auto_quarantine_config,
    save_auto_quarantine_config,
)


class AutoQuarantineRuleWidget(QWidget):
    """规则管理器：支持多条规则并存、独立启停、排序。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = load_auto_quarantine_config()  # {'enabled', 'rules'}
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
        self.chk_master = QCheckBox("启用自动隔离（总开关，关闭则完全不整理）")
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

        # 编辑区（条件较多，放入滚动区避免小屏截断）
        box = QGroupBox("规则编辑")
        box_inner = QWidget()
        ev = QVBoxLayout(box_inner)
        ev.setSpacing(8)

        hn = QHBoxLayout()
        hn.addWidget(QLabel("规则名称："))
        self.edit_name = QLineEdit()
        hn.addWidget(self.edit_name)
        ev.addLayout(hn)

        self.chk_rule_enabled = QCheckBox("启用此规则")
        ev.addWidget(self.chk_rule_enabled)

        ev.addWidget(QLabel("物料名称包含（任一即命中，中英文逗号分隔）："))
        self.edit_keywords = QLineEdit()
        self.edit_keywords.setPlaceholderText("例如：箱, 手包袋, 塑料袋")
        ev.addWidget(self.edit_keywords)

        h1 = QHBoxLayout()
        self.chk_cat = QCheckBox("要求属于类别：")
        self.edit_cat = QLineEdit()
        self.edit_cat.setFixedWidth(120)
        h1.addWidget(self.chk_cat)
        h1.addWidget(self.edit_cat)
        h1.addStretch()
        ev.addLayout(h1)

        self.chk_alt = QCheckBox("排除替代料（不隔离替代料记录）")
        ev.addWidget(self.chk_alt)
        self.chk_loss = QCheckBox("要求负损（实际>0 且 实际<定额）")
        ev.addWidget(self.chk_loss)

        # —— 新增条件 ——
        ev.addWidget(QLabel("—— 偏差率 / 编码 / 车间 / 备注 等条件 ——"))

        h_rate = QHBoxLayout()
        self.chk_dev_rate = QCheckBox("要求偏差率落在范围(开区间)：")
        self.spin_dev_rate_min = QDoubleSpinBox()
        self.spin_dev_rate_min.setRange(-1000, 1000)
        self.spin_dev_rate_min.setDecimals(2)
        self.spin_dev_rate_min.setValue(10)
        self.spin_dev_rate_max = QDoubleSpinBox()
        self.spin_dev_rate_max.setRange(-1000, 1000)
        self.spin_dev_rate_max.setDecimals(2)
        self.spin_dev_rate_max.setValue(100)
        h_rate.addWidget(self.chk_dev_rate)
        h_rate.addWidget(QLabel("下限"))
        h_rate.addWidget(self.spin_dev_rate_min)
        h_rate.addWidget(QLabel("上限"))
        h_rate.addWidget(self.spin_dev_rate_max)
        h_rate.addStretch()
        ev.addLayout(h_rate)

        ev.addWidget(QLabel("物料编码前缀（逗号分隔多值 OR，例如 40,41）："))
        self.edit_mat_prefix = QLineEdit()
        self.edit_mat_prefix.setPlaceholderText("例如 40,41 表示编码以40或41开头")
        ev.addWidget(self.edit_mat_prefix)

        h_ws = QHBoxLayout()
        self.chk_workshop = QCheckBox("要求属于车间：")
        self.edit_workshop = QLineEdit()
        self.edit_workshop.setFixedWidth(160)
        h_ws.addWidget(self.chk_workshop)
        h_ws.addWidget(self.edit_workshop)
        h_ws.addStretch()
        ev.addLayout(h_ws)

        h_rem = QHBoxLayout()
        h_rem.addWidget(QLabel("备注要求："))
        self.combo_remark = QComboBox()
        self.combo_remark.addItems(["全部", "有备注", "无备注"])
        h_rem.addWidget(self.combo_remark)
        h_rem.addStretch()
        ev.addLayout(h_rem)

        ev.addWidget(QLabel("物料名称不含（逗号分隔，任一命中即排除）："))
        self.edit_name_exclude = QLineEdit()
        self.edit_name_exclude.setPlaceholderText("例如 彩箱,定制 表示名称含这些词的不隔离")
        ev.addWidget(self.edit_name_exclude)

        h_dq = QHBoxLayout()
        self.chk_dev_qty = QCheckBox("要求偏差数量落在范围(开区间)：")
        self.spin_dev_qty_min = QDoubleSpinBox()
        self.spin_dev_qty_min.setRange(-1000000, 1000000)
        self.spin_dev_qty_min.setDecimals(2)
        self.spin_dev_qty_min.setValue(0)
        self.spin_dev_qty_max = QDoubleSpinBox()
        self.spin_dev_qty_max.setRange(-1000000, 1000000)
        self.spin_dev_qty_max.setDecimals(2)
        self.spin_dev_qty_max.setValue(1)
        h_dq.addWidget(self.chk_dev_qty)
        h_dq.addWidget(QLabel("下限"))
        h_dq.addWidget(self.spin_dev_qty_min)
        h_dq.addWidget(QLabel("上限"))
        h_dq.addWidget(self.spin_dev_qty_max)
        h_dq.addStretch()
        ev.addLayout(h_dq)

        ev.addWidget(QLabel("当前规则预览："))
        self.lbl_summary = QLabel()
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet(
            "color:#555; padding:6px; background:#f5f5f5; border-radius:4px;")
        ev.addWidget(self.lbl_summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box_inner)
        box_v = QVBoxLayout(box)
        box_v.addWidget(scroll)
        root.addWidget(box, 2)

        # 信号
        for w in (self.edit_name, self.edit_keywords, self.edit_cat,
                  self.edit_mat_prefix, self.edit_workshop, self.edit_name_exclude):
            w.textChanged.connect(self._refresh_summary)
        for w in (self.chk_rule_enabled, self.chk_cat, self.chk_alt, self.chk_loss,
                  self.chk_dev_rate, self.chk_workshop, self.chk_dev_qty):
            w.stateChanged.connect(self._refresh_summary)
        for w in (self.spin_dev_rate_min, self.spin_dev_rate_max,
                  self.spin_dev_qty_min, self.spin_dev_qty_max):
            w.valueChanged.connect(self._refresh_summary)
        self.combo_remark.currentIndexChanged.connect(self._refresh_summary)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_del)
        self.btn_up.clicked.connect(self._on_up)
        self.btn_down.clicked.connect(self._on_down)

    # ---------------------------------------------------------------- 数据
    def _commit_editor(self):
        """把编辑区当前内容写回 self.cfg['rules'][current_index]。"""
        if not (0 <= self.current_index < len(self.cfg["rules"])):
            return
        r = self.cfg["rules"][self.current_index]
        r["name"] = self.edit_name.text().strip() or "未命名规则"
        r["enabled"] = self.chk_rule_enabled.isChecked()
        raw = self.edit_keywords.text()
        r["name_keywords"] = [
            k.strip() for k in raw.replace("，", ",").replace("、", ",").split(",") if k.strip()
        ]
        r["category_required"] = self.chk_cat.isChecked()
        r["category_value"] = self.edit_cat.text().strip() or "包材"
        r["exclude_alt"] = self.chk_alt.isChecked()
        r["negative_loss_required"] = self.chk_loss.isChecked()
        # —— 新增条件回写 ——
        r["dev_rate_required"] = self.chk_dev_rate.isChecked()
        r["dev_rate_min"] = self.spin_dev_rate_min.value()
        r["dev_rate_max"] = self.spin_dev_rate_max.value()
        r["mat_code_prefix"] = self.edit_mat_prefix.text().strip()
        r["workshop_required"] = self.chk_workshop.isChecked()
        r["workshop_value"] = self.edit_workshop.text().strip()
        r["remark_mode"] = ["off", "has", "none"][self.combo_remark.currentIndex()]
        r["name_exclude_keywords"] = self.edit_name_exclude.text().strip()
        r["dev_qty_required"] = self.chk_dev_qty.isChecked()
        r["dev_qty_min"] = self.spin_dev_qty_min.value()
        r["dev_qty_max"] = self.spin_dev_qty_max.value()

    def _load_rule_to_editor(self, idx):
        if not (0 <= idx < len(self.cfg["rules"])):
            return
        self.current_index = idx
        r = self.cfg["rules"][idx]
        self.edit_name.setText(r.get("name", ""))
        self.chk_rule_enabled.setChecked(bool(r.get("enabled", True)))
        self.edit_keywords.setText("，".join(r.get("name_keywords") or []))
        self.chk_cat.setChecked(bool(r.get("category_required", True)))
        self.edit_cat.setText(str(r.get("category_value", "包材")))
        self.chk_alt.setChecked(bool(r.get("exclude_alt", True)))
        self.chk_loss.setChecked(bool(r.get("negative_loss_required", True)))
        # —— 新增条件回填 ——
        self.chk_dev_rate.setChecked(bool(r.get("dev_rate_required", False)))
        self.spin_dev_rate_min.setValue(float(r.get("dev_rate_min", 10)))
        self.spin_dev_rate_max.setValue(float(r.get("dev_rate_max", 100)))
        self.edit_mat_prefix.setText(str(r.get("mat_code_prefix", "")))
        self.chk_workshop.setChecked(bool(r.get("workshop_required", False)))
        self.edit_workshop.setText(str(r.get("workshop_value", "")))
        self.combo_remark.setCurrentIndex(
            ["off", "has", "none"].index(str(r.get("remark_mode", "off")).strip())
            if str(r.get("remark_mode", "off")).strip() in ("off", "has", "none") else 0)
        self.edit_name_exclude.setText(str(r.get("name_exclude_keywords", "")))
        self.chk_dev_qty.setChecked(bool(r.get("dev_qty_required", False)))
        self.spin_dev_qty_min.setValue(float(r.get("dev_qty_min", 0)))
        self.spin_dev_qty_max.setValue(float(r.get("dev_qty_max", 1)))
        self._refresh_summary()

    def _refresh_list(self):
        self.list_rules.blockSignals(True)
        self.list_rules.clear()
        for i, r in enumerate(self.cfg["rules"]):
            name = r.get("name", "未命名规则")
            tag = "（已停用）" if not r.get("enabled", True) else ""
            self.list_rules.addItem(QListWidgetItem("%d. %s%s" % (i + 1, name, tag)))
        # setCurrentRow 必须在 blockSignals 内，否则会触发 _on_select_rule -> _commit_editor
        # 用空/旧编辑区覆盖当前规则
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
        new_rule = dict(DEFAULT_RULE)
        new_rule["name"] = "新规则%d" % (len(self.cfg["rules"]) + 1)
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
        r = self._collect_preview()
        self.lbl_summary.setText(build_rule_summary(r))

    def _collect_preview(self):
        return {
            "enabled": self.chk_rule_enabled.isChecked(),
            "exclude_alt": self.chk_alt.isChecked(),
            "category_required": self.chk_cat.isChecked(),
            "category_value": self.edit_cat.text().strip() or "包材",
            "name_keywords": [
                k.strip()
                for k in self.edit_keywords.text().replace("，", ",").replace("、", ",").split(",")
                if k.strip()
            ],
            "negative_loss_required": self.chk_loss.isChecked(),
            # —— 新增条件预览源 ——
            "dev_rate_required": self.chk_dev_rate.isChecked(),
            "dev_rate_min": self.spin_dev_rate_min.value(),
            "dev_rate_max": self.spin_dev_rate_max.value(),
            "mat_code_prefix": self.edit_mat_prefix.text().strip(),
            "workshop_required": self.chk_workshop.isChecked(),
            "workshop_value": self.edit_workshop.text().strip(),
            "remark_mode": ["off", "has", "none"][self.combo_remark.currentIndex()],
            "name_exclude_keywords": self.edit_name_exclude.text().strip(),
            "dev_qty_required": self.chk_dev_qty.isChecked(),
            "dev_qty_min": self.spin_dev_qty_min.value(),
            "dev_qty_max": self.spin_dev_qty_max.value(),
        }

    # ---------------------------------------------------------------- 保存
    def save(self):
        """提交编辑区并写盘，成功返回 True。"""
        self._commit_editor()
        self.cfg["enabled"] = self.chk_master.isChecked()
        try:
            save_auto_quarantine_config(self.cfg)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", "写入配置文件失败：%s" % e)
            return False
        return True


class AutoQuarantineRuleDialog(QDialog):
    """独立打开时的薄壳：承载 Widget + OK/Cancel。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ 自动隔离规则")
        self.setMinimumWidth(580)
        self.setMinimumHeight(680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.widget = AutoQuarantineRuleWidget(self)
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
    dlg = AutoQuarantineRuleDialog()
    dlg.show()
    sys.exit(app.exec())
