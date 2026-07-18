# -*- coding: utf-8 -*-
"""自动隔离规则配置对话框（多规则管理：列表 + 编辑 + 新增/删除/排序）。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.auto_quarantine import (
    DEFAULT_RULE,
    build_all_summary,
    build_rule_summary,
    load_auto_quarantine_config,
    save_auto_quarantine_config,
)


class AutoQuarantineRuleDialog(QDialog):
    """规则管理器：支持多条规则并存、独立启停、排序。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ 自动隔离规则")
        self.setMinimumWidth(580)
        self.setMinimumHeight(560)
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

        ev.addWidget(QLabel("当前规则预览："))
        self.lbl_summary = QLabel()
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet(
            "color:#555; padding:6px; background:#f5f5f5; border-radius:4px;")
        ev.addWidget(self.lbl_summary)

        root.addWidget(box)

        # 底部按钮
        btns = QHBoxLayout()
        btns.addStretch()
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("保存")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_save)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)
        root.addLayout(btns)

        # 信号
        for w in (self.edit_name, self.edit_keywords, self.edit_cat):
            w.textChanged.connect(self._refresh_summary)
        for w in (self.chk_rule_enabled, self.chk_cat, self.chk_alt, self.chk_loss):
            w.stateChanged.connect(self._refresh_summary)
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
            k.strip() for k in raw.replace("，", ",").split(",") if k.strip()
        ]
        r["category_required"] = self.chk_cat.isChecked()
        r["category_value"] = self.edit_cat.text().strip() or "包材"
        r["exclude_alt"] = self.chk_alt.isChecked()
        r["negative_loss_required"] = self.chk_loss.isChecked()

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
                for k in self.edit_keywords.text().replace("，", ",").split(",")
                if k.strip()
            ],
            "negative_loss_required": self.chk_loss.isChecked(),
        }

    def _on_save(self):
        self._commit_editor()
        self.cfg["enabled"] = self.chk_master.isChecked()
        try:
            save_auto_quarantine_config(self.cfg)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", "写入配置文件失败：%s" % e)
            return
        self.accept()
