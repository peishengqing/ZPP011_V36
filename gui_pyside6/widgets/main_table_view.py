# -*- coding: utf-8 -*-
"""主表视图 —— v43.350 第五期G1：把「两块表头交叉出来的那个角」管起来

为什么需要一个子类
------------------
设计稿把「全选」勾选框放在表头行的第一格，也就是**垂直表头与水平表头交叉**的那块
矩形。Qt 本来有现成的口子：``QTableView.setCornerWidget(w, Qt.TopLeftCorner)``。
但 PySide6 6.6.3 把第二个参数砍掉了（``setCornerWidget() takes exactly one argument``，
关键字形式也不行），剩下这一个重载写死放**右下角**（滚动条交叉处）—— 实测
``w.pos()`` 落在 viewport 右下角，界面上左上角什么都没有。

所以这里自己摆：那块角的几何就是 ``x=垂直表头.x()、y=水平表头.y()、
w=垂直表头宽、h=水平表头高``。它在 viewport 之外，不受滚动影响，但会随窗口尺寸、
滚动条出现/消失、行号变宽而变，故在视图 resize/show 和两块表头的 resize 后重摆一次。
"""

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QTableView


class MainTableView(QTableView):
    """主表视图：左上角全选框由本类手工定位（PySide6 的 setCornerWidget 只会放右下角）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._corner_widget = None
        self._watch_headers()

    def _watch_headers(self):
        for h in (self.horizontalHeader(), self.verticalHeader()):
            if h is not None:
                h.installEventFilter(self)

    def setHorizontalHeader(self, header):
        # 主窗口会把水平表头换成 SortBadgeHeader，换完得重新盯它的尺寸变化
        super().setHorizontalHeader(header)
        if header is not None:
            header.installEventFilter(self)
        self._layout_corner()

    def setVerticalHeader(self, header):
        super().setVerticalHeader(header)
        if header is not None:
            header.installEventFilter(self)
        self._layout_corner()

    def set_corner_widget(self, widget):
        """挂上左上角控件（一般是 SelectAllCheck）；传 None 撤掉。"""
        if self._corner_widget is not None and self._corner_widget is not widget:
            self._corner_widget.setParent(None)
        self._corner_widget = widget
        if widget is None:
            return
        widget.setParent(self)
        widget.show()
        self._layout_corner()

    def corner_widget(self):
        return self._corner_widget

    def _layout_corner(self):
        w = self._corner_widget
        if w is None:
            return
        vh, hh = self.verticalHeader(), self.horizontalHeader()
        # 表头隐藏（无模型时的极端态）就别摆，免得盖住内容
        if not vh.isVisible() or not hh.isVisible():
            w.hide()
            return
        w.setGeometry(vh.x(), hh.y(), vh.width(), hh.height())
        w.show()
        w.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_corner()

    def showEvent(self, event):
        super().showEvent(event)
        self._layout_corner()

    def eventFilter(self, obj, event):
        # 表头尺寸一变（滚动条增减、行号变宽、列头换行），交叉角就得跟着挪
        if event.type() in (QEvent.Resize, QEvent.Show):
            self._layout_corner()
        return super().eventFilter(obj, event)

    def setModel(self, model):
        super().setModel(model)
        # 模型挂上后 Qt 会重算两块表头的可见性与尺寸
        self._layout_corner()
