# -*- coding: utf-8 -*-
"""自动隔离规则配置对话框（可配置关键词/包材/负损）。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.auto_quarantine import (
    build_rule_summary,
    load_auto_quarantine_config,
    save_auto_quarantine_config,
)


class AutoQuarantineRuleDialog(QDialog):
    """让用户在不改代码的前提下调整自动隔离的匹配规则。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ 自动隔离规则")
        self.setMinimumWidth(480)
        self.cfg = load_auto_quarantine_config()
        self._build_ui()
        self._load_to_ui()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        self.chk_enabled = QCheckBox("启用自动隔离（取消勾选则完全关闭自动整理）")
        self.chk_enabled.stateChanged.connect(self._refresh_summary)
        root.addWidget(self.chk_enabled)

        root.addWidget(QLabel("物料名称包含（任一即命中，中英文逗号分隔）："))
        self.edit_keywords = QLineEdit()
        self.edit_keywords.setPlaceholderText("例如：箱, 手包袋, 塑料袋")
        self.edit_keywords.textChanged.connect(self._refresh_summary)
        root.addWidget(self.edit_keywords)

        h1 = QHBoxLayout()
        self.chk_cat = QCheckBox("要求属于类别：")
        self.chk_cat.stateChanged.connect(self._refresh_summary)
        self.edit_cat = QLineEdit()
        self.edit_cat.setFixedWidth(120)
        self.edit_cat.textChanged.connect(self._refresh_summary)
        h1.addWidget(self.chk_cat)
        h1.addWidget(self.edit_cat)
        h1.addStretch()
        root.addLayout(h1)

        self.chk_alt = QCheckBox("排除替代料（不隔离替代料记录）")
        self.chk_alt.stateChanged.connect(self._refresh_summary)
        root.addWidget(self.chk_alt)

        self.chk_loss = QCheckBox("要求负损（实际>0 且 实际<定额）")
        self.chk_loss.stateChanged.connect(self._refresh_summary)
        root.addWidget(self.chk_loss)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        root.addWidget(QLabel("当前规则预览："))
        self.lbl_summary = QLabel()
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet(
            "color:#555; padding:6px; background:#f5f5f5; border-radius:4px;")
        root.addWidget(self.lbl_summary)

        root.addStretch()

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

    # ---------------------------------------------------------------- data
    def _load_to_ui(self):
        self.chk_enabled.setChecked(bool(self.cfg.get('enabled', True)))
        self.edit_keywords.setText("，".join(self.cfg.get('name_keywords') or []))
        self.chk_cat.setChecked(bool(self.cfg.get('category_required', True)))
        self.edit_cat.setText(str(self.cfg.get('category_value', '包材')))
        self.chk_alt.setChecked(bool(self.cfg.get('exclude_alt', True)))
        self.chk_loss.setChecked(bool(self.cfg.get('negative_loss_required', True)))
        self._refresh_summary()

    def _collect(self) -> dict:
        # 关键词：支持中英文逗号，拆分去空
        raw = self.edit_keywords.text()
        kws = [k.strip() for k in raw.replace('，', ',').split(',') if k.strip()]
        return {
            "enabled": self.chk_enabled.isChecked(),
            "exclude_alt": self.chk_alt.isChecked(),
            "category_required": self.chk_cat.isChecked(),
            "category_value": self.edit_cat.text().strip() or "包材",
            "name_keywords": kws,
            "negative_loss_required": self.chk_loss.isChecked(),
        }

    def _refresh_summary(self):
        self.lbl_summary.setText(build_rule_summary(self._collect()))

    def _on_save(self):
        cfg = self._collect()
        try:
            save_auto_quarantine_config(cfg)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", "写入配置文件失败：%s" % e)
            return
        self.cfg = cfg
        self.accept()
