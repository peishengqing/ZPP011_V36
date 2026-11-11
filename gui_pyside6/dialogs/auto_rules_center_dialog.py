# -*- coding: utf-8 -*-
"""规则中心对话框：把「自动隔离区」与「自动已读」两套规则放在一个对话框的两个 Tab 里，
用 Tab 点击区分，底部共享「保存 / 取消」。两页各自独立保存配置。

入口：菜单 审核 ▸ ⚙ 规则中心（隔离/已读）；工具栏「自动隔离规则」按钮也指向它。
"""
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QVBoxLayout,
)

from gui_pyside6.dialogs.auto_quarantine_rule_dialog import AutoQuarantineRuleWidget
from gui_pyside6.dialogs.auto_read_rule_dialog import AutoReadRuleWidget
from gui_pyside6.widgets.rule_preview_widget import RulePreviewWidget


from gui_pyside6.components import dialog_chrome

class AutoRulesCenterDialog(QDialog):
    def __init__(self, parent=None, open_tab=0, df=None):
        super().__init__(parent)
        # 第四期C：条件卡 + 预览条要横向铺（240 列表 + 三组字段），按大型档给
        dialog_chrome.apply(self, dialog_chrome.TIER_LARGE,
                            "规则中心", "自动隔离 / 自动已读 / 命中预览")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tabs = QTabWidget(self)
        self.tab_quarantine = AutoQuarantineRuleWidget(self, df=df).wire_changed_signals()
        self.tab_read = AutoReadRuleWidget(self)
        self.tabs.addTab(self.tab_quarantine, "① 自动隔离区")
        self.tabs.addTab(self.tab_read, "② 自动已读")
        # v43.341 第四期：影子模式命中预览（只读，不参与保存）
        self.tab_preview = RulePreviewWidget(df, self)
        self.tabs.addTab(self.tab_preview, "③ 命中预览（影子）")
        if 0 <= open_tab < self.tabs.count():
            self.tabs.setCurrentIndex(open_tab)
        layout.addWidget(self.tabs, 1)

        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok, parent=self)
        self.btn_box.button(QDialogButtonBox.Ok).setText("保存全部")
        self.btn_box.button(QDialogButtonBox.Cancel).setText("取消")
        self.btn_box.accepted.connect(self._on_accept)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)
        # Tab① 自带的「保存规则」走同一条保存路径，成功后把整个中心收掉
        self.tab_quarantine.saved.connect(self._on_widget_saved)

    def _on_widget_saved(self, ok):
        if ok:
            self.accept()

    def _on_accept(self):
        # 只保存前两页；③ 命中预览是纯只读影子模式，没有任何可保存状态
        ok_q = self.tab_quarantine.save()
        ok_r = self.tab_read.save()
        if ok_q and ok_r:
            self.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = AutoRulesCenterDialog()
    dlg.show()
    sys.exit(app.exec())
