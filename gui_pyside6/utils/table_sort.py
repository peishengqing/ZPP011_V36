# -*- coding: utf-8 -*-
"""
列头点击排序工具
================
为 QTableView + DataFrameModel 启用「点击列头排序」。

背景：本项目（PySide6 / Qt6）下，`QTableView.setSortingEnabled(True)` 的
内部「sectionClicked → sortByColumn → model.sort」自动连接在 DataFrameModel
上不生效（实测点击列头不触发 model.sort）。本模块改用显式连接：
`header.sectionClicked` → 自管 handler → `DataFrameModel.sort()`，
并自管排序箭头，规避该失效连接。

交互：两态——点列头升序，再点同一列降序，再点又升序循环（与隔离区 Tab1 一致）。
`skip_cols` 中的列不参与排序（如内部 _read 列）。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableView


class HeaderSortController:
    """管理单个 QTableView 的列头点击排序。"""

    def __init__(self, table_view, get_model, skip_cols=()):
        """
        :param table_view: 目标 QTableView
        :param get_model: 返回当前 DataFrameModel 的可调用对象（模型可能被替换，需动态取）
        :param skip_cols: 不参与排序的模型列索引集合
        """
        if not isinstance(table_view, QTableView):
            raise TypeError("table_view 必须是 QTableView")
        self.table_view = table_view
        self.get_model = get_model
        self.skip_cols = set(skip_cols)
        self._col = -1
        self._order = Qt.AscendingOrder

        header = table_view.horizontalHeader()
        # 必须保持 sortingEnabled=True，否则 QHeaderView 点击时不发射 sectionClicked，
        # 自定义 handler 收不到信号。Qt 内部自动连接在本环境下未生效，实际排序由本类完成。
        table_view.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_click)

    def _on_click(self, logical_index):
        model = self.get_model()
        if model is None:
            return
        if logical_index in self.skip_cols:
            return
        if logical_index == self._col:
            order = Qt.DescendingOrder if self._order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            order = Qt.AscendingOrder
        model.sort(logical_index, order)
        self._col = logical_index
        self._order = order
        self.table_view.horizontalHeader().setSortIndicator(logical_index, order)

    def reapply(self):
        """模型被替换/重渲染（如应用筛选）后恢复排序态。无激活排序时为空操作。"""
        if self._col < 0:
            return
        model = self.get_model()
        if model is None:
            return
        model.sort(self._col, self._order)
        self.table_view.horizontalHeader().setSortIndicator(self._col, self._order)

    def apply_default(self, col, order):
        """列表首次渲染时设默认排序并立即生效（不依赖列头点击，规避 Qt6 点击失效）。

        仅在用户尚未手动点击列头排序时调用；激活后由 reapply() 维持用户排序。
        """
        if col < 0:
            return
        model = self.get_model()
        if model is None:
            return
        self._col = col
        self._order = order
        model.sort(col, order)
        self.table_view.horizontalHeader().setSortIndicator(col, order)

    @property
    def active(self):
        return self._col >= 0


def enable_click_sort(table_view, get_model, skip_cols=()):
    """便捷入口：为 table_view 启用列头点击排序，返回 HeaderSortController。"""
    return HeaderSortController(table_view, get_model, skip_cols)
