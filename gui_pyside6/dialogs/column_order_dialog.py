# -*- coding: utf-8 -*-
"""列顺序设置对话框（方案B：不靠「拖动列头」也能改列顺序，改完自动保存）。

纯 UI 组件，不耦合任何持久化：调用方负责把新顺序写回（看板走
``BoardLayoutManager.save_board_order``，主表走 ``ColumnController`` 的
``__order__``）。各看板的「列顺序」按钮点进来弹它，用户用 上移/下移/置顶/置底
调整，确定后取 :meth:`result_order`。

用法::

    dlg = ColumnOrderDialog(parent, title="负损看板",
                            current_order=["订单日期", "流程订单", ...],
                            default_order=["订单日期", "流程订单", ...])  # 可选
    if dlg.exec() == QDialog.Accepted:
        new_order = dlg.result_order()      # 用户确认后的列名顺序（视觉左→右）
        if new_order and new_order != current_order:
            ... 应用并持久化 ...
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QDialogButtonBox,
)

from gui_pyside6.components import dialog_chrome


class ColumnOrderDialog(QDialog):
    """列出当前全部列，支持上移/下移/置顶/置底与「恢复默认」。

    - ``current_order``：当前视觉顺序（左→右）的列名列表，作为初始列表。
    - ``default_order``：可选。给「恢复默认」用；没给则该按钮置灰。恢复时
      默认序列里已不存在的列忽略，默认序列之后出现的新列按当前顺序殿后。
    """

    def __init__(self, parent=None, title="", current_order=None, default_order=None):
        super().__init__(parent)
        self._title = title or "列顺序"
        self._default_order = list(default_order) if default_order else None
        self._current_order = list(current_order) if current_order else []

        # 统一弹窗外壳规范（设计稿 4.4 尺寸档 small 420×520；标题「列顺序设置 · <看板名>」）
        dialog_chrome.apply(self, dialog_chrome.TIER_SMALL, "列顺序设置",
                           self._title if title else None)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        hint = QLabel(
            "用「上移 / 下移 / 置顶 / 置底」调整列的显示顺序，确定后自动保存，"
            "下次打开沿用。列的顺序也可以直接拖动表头改变。")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        body = QHBoxLayout()
        body.setSpacing(8)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SingleSelection)
        body.addWidget(self._list, 1)

        side = QVBoxLayout()
        side.setSpacing(6)
        btn_up = QPushButton("↑ 上移")
        btn_down = QPushButton("↓ 下移")
        btn_top = QPushButton("⇑ 置顶")
        btn_bottom = QPushButton("⇓ 置底")
        btn_up.setToolTip("把选中列往前挪一格")
        btn_down.setToolTip("把选中列往后挪一格")
        btn_top.setToolTip("把选中列挪到最前")
        btn_bottom.setToolTip("把选中列挪到最后")
        for b in (btn_up, btn_down, btn_top, btn_bottom):
            side.addWidget(b)
        btn_restore = QPushButton("恢复默认")
        btn_restore.setToolTip("回到程序初始的列顺序")
        if not self._default_order:
            btn_restore.setEnabled(False)
            btn_restore.setToolTip("本看板未提供默认列顺序")
        side.addWidget(btn_restore)
        side.addStretch(1)
        body.addLayout(side)
        outer.addLayout(body, 1)

        btn_up.clicked.connect(lambda: self._move(-1))
        btn_down.clicked.connect(lambda: self._move(1))
        btn_top.clicked.connect(lambda: self._move(-100))
        btn_bottom.clicked.connect(lambda: self._move(100))
        btn_restore.clicked.connect(self._restore_default)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText("保存")
        btn_box.button(QDialogButtonBox.Cancel).setText("取消")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        outer.addWidget(btn_box)

        self._fill(self._current_order)

    def _fill(self, names):
        """按给定列名重建列表（文本=列名，item 不可编辑，取结果直接读文本）。"""
        self._list.clear()
        for nm in names:
            it = QListWidgetItem(str(nm))
            it.setData(Qt.ItemDataRole.UserRole, str(nm))
            self._list.addItem(it)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _move(self, delta):
        """移动选中列。delta：-1 上移 / 1 下移 / -100 置顶 / 100 置底。"""
        item = self._list.currentItem()
        if item is None:
            return
        idx = self._list.row(item)
        n = self._list.count()
        if delta <= -99:
            target = 0
        elif delta >= 99:
            target = n - 1
        else:
            target = idx + delta
        if target < 0 or target >= n or target == idx:
            return
        it = self._list.takeItem(idx)
        self._list.insertItem(target, it)
        self._list.setCurrentRow(target)
        self._list.scrollToItem(self._list.item(target))

    def _restore_default(self):
        if not self._default_order:
            return
        base = list(self._default_order)
        base_set = set(base)
        current = [self._list.item(i).data(Qt.ItemDataRole.UserRole)
                   for i in range(self._list.count())]
        extra = [c for c in current if c not in base_set]
        self._fill(base + extra)

    def result_order(self):
        """用户确认后的列名顺序（左→右）；取消/未填则返回空列表。"""
        return [self._list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self._list.count())]
