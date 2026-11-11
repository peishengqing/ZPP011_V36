# -*- coding: utf-8 -*-
"""规则中心对话框：自动隔离 / 自动已读 / 阈值与提醒 三套配置 + 影子命中预览，四页一窗。

入口：菜单 审核 ▸ ⚙ 规则中心（隔离/已读/阈值）；工具栏「更多 ▸ 自动隔离规则」也指向
它（第四期E 入口收敛：那里不再单开一个旧版隔离规则窗口，直接跳到第 ① 页）。
每页各自保存自己的配置文件，底部「保存全部」一次收三页。
"""
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QVBoxLayout,
)

from gui_pyside6.dialogs.auto_quarantine_rule_dialog import AutoQuarantineRuleWidget
from gui_pyside6.dialogs.auto_read_rule_dialog import AutoReadRuleWidget
from gui_pyside6.dialogs.threshold_config_dialog import ThresholdConfigWidget
from gui_pyside6.widgets.rule_preview_widget import RulePreviewWidget


from gui_pyside6.components import dialog_chrome

class AutoRulesCenterDialog(QDialog):
    def __init__(self, parent=None, open_tab=0, df=None):
        super().__init__(parent)
        # 第四期C：条件卡 + 预览条要横向铺（240 列表 + 三组字段），按大型档给
        dialog_chrome.apply(self, dialog_chrome.TIER_LARGE,
                            "规则中心", "自动隔离 / 自动已读 / 阈值与提醒 / 命中预览")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tabs = QTabWidget(self)
        self.tab_quarantine = AutoQuarantineRuleWidget(self, df=df).wire_changed_signals()
        self.tab_read = AutoReadRuleWidget(self, df=df).wire_changed_signals()
        self.tab_threshold = ThresholdConfigWidget(self, df=df).wire_changed_signals()
        self.tabs.addTab(self.tab_quarantine, "① 自动隔离区")
        self.tabs.addTab(self.tab_read, "② 自动已读")
        self.tabs.addTab(self.tab_threshold, "③ 阈值与提醒")
        # v43.341 第四期：影子模式命中预览（只读，不参与保存）；第四期E 起顺延到第 ④ 页
        self.tab_preview = RulePreviewWidget(df, self)
        self.tabs.addTab(self.tab_preview, "④ 命中预览（影子）")
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
        # 三页各自的「保存」走同一条收窗路径，成功后把整个中心收掉
        self.tab_quarantine.saved.connect(self._on_widget_saved)
        self.tab_read.saved.connect(self._on_widget_saved)
        self.tab_threshold.saved.connect(self._on_widget_saved)

    def _on_widget_saved(self, ok):
        if ok:
            self.accept()

    def _on_accept(self):
        # ④ 命中预览是纯只读影子模式，没有任何可保存状态
        ok = [self.tab_quarantine.save(), self.tab_read.save(),
              self.tab_threshold.save()]
        if all(ok):
            self.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = AutoRulesCenterDialog()
    dlg.show()
    sys.exit(app.exec())
