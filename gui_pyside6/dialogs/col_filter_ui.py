# -*- coding: utf-8 -*-
"""看板对话框「列头筛选」共用组件 — v43.264 抽取自 6 处重复代码。

此前 `alert_dialog / deviation_warning_dialog / neg_loss_dashboard_dialog /
pos_loss_dashboard_dialog / quarantine_dialog / semi_dashboard_dialog` 各自
复制了一份 7 行的按钮构造 + 「🔽 列头筛选✓」状态文本逻辑（quarantine 有两个
按钮共 4 处），改文案/改图标要动 6 个文件。现收敛到本模块：

- make_col_filter_button(owner, handler)：线性 funnel 图标 + 「列头筛选」文字；
- set_col_filter_button_on(btn, on)：勾选态文字（图标不变，✓ 语义由文字承担）；
- make_col_filter_hint_label()：状态提示标签（琥珀色，右键有清除菜单）。

对象名保持 btn_col_filter / colFilterHint，既有测试与样式引用不受影响。
"""
from PySide6.QtWidgets import QPushButton, QLabel
from PySide6.QtCore import Qt

from gui_pyside6.utils.icons import get_icon

_BTN_TEXT = "列头筛选"


def make_col_filter_button(owner, handler, object_name: str = "btn_col_filter") -> QPushButton:
    """创建列头筛选开关按钮（checkable，funnel 线性图标）。"""
    btn = QPushButton(_BTN_TEXT, owner)
    btn.setIcon(get_icon("funnel-lines", 14))
    btn.setCheckable(True)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip("开启后点列头弹取值勾选浮层（Excel式筛选）；Ctrl+点列头仍可排序")
    btn.setObjectName(object_name)
    btn.clicked.connect(handler)
    return btn


def set_col_filter_button_on(btn: QPushButton, on: bool):
    """列头筛选开关状态 → 按钮文字（勾选态加 ✓）。"""
    btn.setText(f"{_BTN_TEXT}✓" if on else _BTN_TEXT)


def make_col_filter_hint_label() -> QLabel:
    """列头筛选状态提示标签（琥珀色；调用方需自行挂清除菜单）。"""
    label = QLabel(f"{_BTN_TEXT}：0 列")
    label.setProperty("class", "amberHint")
    return label
