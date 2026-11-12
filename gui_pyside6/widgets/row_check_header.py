# -*- coding: utf-8 -*-
"""行首勾选道 —— v43.350 第五期G1：照抄设计稿表格首列（34px ``.chk``）

为什么用「垂直表头」而不是真加一列
--------------------------------
设计稿把勾选框放在表格第一列。但本项目主表的模型是 **模型列号 == DataFrame 列号**
的 1:1 映射（``data_frame_model.py`` 里 ``columnCount() = len(_display_columns)``），
全仓 20+ 处按列号取数、排序、列头筛选、存/取列宽、自适应列宽、复制区域都建立在这个
映射上；真加一列 = 所有既有列号 +1，属于伤筋动骨。
而垂直表头本来就在 ``columnCount`` 之外，且它当前只显示行号 —— 把勾选道放这里，
既有列号一个都不动，行号也照样保留（裴哥靠「第 N 行」口头定位数据）。

勾选状态 = 选中状态，不引入第二套
--------------------------------
勾上 = 该行在 ``selectionModel`` 里被选中（整行），取消 = 从选择里去掉。
所以底部状态条「已选 n 行」、批量标记已读、批量导出、批量隔离、Ctrl+C 复制区域
全部照常工作，不需要任何新代码去读「勾选集合」。

左上角那颗是设计稿表头里的全选框（三态：全不勾 / 部分 / 全勾），
点一下 = 全选当前**可见**行（代理筛选后的行，不是全表）。

配色全部现取 ``Thm.color(令牌)``：整道自绘，不走 QSS —— 因为一旦让原生先画 section，
行号就会被画在道中央，跟勾选框叠在一起；自绘才能同时控制两者位置。
"""

from PySide6.QtCore import (
    QModelIndex, QItemSelection, QItemSelectionModel, QPoint, QPersistentModelIndex,
    QRect, Qt, Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QPolygon, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QWidget

from gui_pyside6.themes.tokens import SIZE_PX, num_font
from utils.theme_manager import Thm

_CHK = 13            # 设计稿 .chk 13×13
_CHK_X = 8           # 勾选框左边距
_CHK_R = 3           # 设计稿 border-radius:3px
_PEN_W = 1.5         # 设计稿 border:1.5px

_OFF, _PART, _ON = 0, 1, 2


def _box_rect(width, height):
    """勾选框在 section 里的矩形（垂直居中，靠左）。"""
    return QRect(_CHK_X, (height - _CHK) // 2, _CHK, _CHK)


def paint_check(painter, rect, state):
    """画一颗 13×13 勾选框：off=描边空框，on=主色实心+白勾，partial=主色实心+白横杠。

    与 SelectAllCheck（角标）共用，保证两处形状/描边完全一致。
    """
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    if state == _OFF:
        painter.setBrush(QColor(Thm.color("surface")))
        painter.setPen(QPen(QColor(Thm.color("borderStrong")), _PEN_W))
        painter.drawRoundedRect(rect, _CHK_R, _CHK_R)
    else:
        painter.setBrush(QColor(Thm.color("primary")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, _CHK_R, _CHK_R)
        mark = QPen(QColor(Thm.color("onPrimary")), 1.8)
        mark.setCapStyle(Qt.RoundCap)
        mark.setJoinStyle(Qt.RoundJoin)
        painter.setPen(mark)
        cx, cy = rect.center().x(), rect.center().y()
        if state == _ON:
            # 设计稿 .chk.on::after：一段短勾（左下→中下→右上）
            painter.drawPolyline(QPolygon([QPoint(cx - 4, cy), QPoint(cx - 1, cy + 3),
                                           QPoint(cx + 4, cy - 3)]))
        else:
            painter.drawLine(cx - 3, cy, cx + 3, cy)
    painter.restore()


class RowCheckHeader(QHeaderView):
    """垂直表头 = 行首勾选道：自绘「勾选框 + 行号」，点一下切换该行选中。"""

    #: 勾选集合变化（供外部刷新批量操作按钮的可用性）
    checked_changed = Signal()

    def __init__(self, view: QAbstractItemView, parent=None):
        super().__init__(Qt.Vertical, parent or view)
        self._view = view
        self.setObjectName("rowCheckLane")
        self.setFixedWidth(SIZE_PX["tableCheckLane"])
        self.setDefaultSectionSize(SIZE_PX["tableRow"])
        self.setSectionResizeMode(QHeaderView.Fixed)
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        # 主题切换跟着换色。回调引用挂在 destroyed 上注销（同 dashboard_shell 的
        # _theme_cb 思路）：主窗口可能被测试反复重建，不注销的话全局回调表会越漏越长，
        # 切一次主题就往已销毁对象上打一次 → RuntimeError。
        self._theme_cb = lambda *_: self.update()
        Thm.on_change(self._theme_cb)
        self.destroyed.connect(lambda _o=None, c=self._theme_cb: Thm.unregister(c))
        # 选择变化 → 重画勾选道 + 通知角标。
        # 注意：PySide6 6.6 里 QAbstractItemView.selectionChanged 是**受保护虚函数**
        # （不是信号，没有 .connect），所以只能去连选择模型的 selectionChanged；
        # 而 setModel 会换掉选择模型，故在 setModel 里重新绑定。
        self._bound_sm = None
        self._bind_selection()

    def setModel(self, model):
        super().setModel(model)
        self._bind_selection()

    def _bind_selection(self):
        sm = self._view.selectionModel()
        if sm is None or sm is self._bound_sm:
            return
        if self._bound_sm is not None:
            try:
                self._bound_sm.selectionChanged.disconnect(self._on_selection_changed)
            except (RuntimeError, TypeError):
                pass
        sm.selectionChanged.connect(self._on_selection_changed)
        self._bound_sm = sm
        self._on_selection_changed()

    def _on_selection_changed(self, *_):
        self.update()
        self.checked_changed.emit()

    # PySide6 6.6.3 坑：QAbstractItemView.update(index) 遮蔽了 QWidget.update()，
    # 无参调用会 TypeError —— 与 SortBadgeHeader 同一处理（见 sort_badge_header.py:40）。
    def update(self, *args):
        if not args:
            QWidget.update(self)
            return
        if isinstance(args[0], (QModelIndex, QPersistentModelIndex)):
            super().update(*args)
            return
        QWidget.update(self, *args)

    def sizeHint(self):
        sh = super().sizeHint()
        sh.setWidth(SIZE_PX["tableCheckLane"])
        return sh

    # ── 状态读取 ────────────────────────────────────────────────
    def _model(self):
        return self._view.model()

    def _selection(self):
        return self._view.selectionModel()

    def is_row_checked(self, row):
        sm, mdl = self._selection(), self._model()
        if sm is None or mdl is None or row < 0 or row >= mdl.rowCount():
            return False
        # 整行选中（勾道点出来的）或首列单元格被选中（在表格里拖选到 col0 的）都算勾上
        return (sm.isRowSelected(row, QModelIndex())
                or sm.isSelected(mdl.index(row, 0)))

    def total_rows(self):
        mdl = self._model()
        return 0 if mdl is None else mdl.rowCount()

    def check_state(self):
        """角标三态：0 全不勾 / 1 部分 / 2 全勾。

        行数走 ``selectedRows()``（Qt 按选择段算，不逐格展开）—— 万行表全选时
        逐格 selectedIndexes() 要摊十几万个索引，每次选择变化都重算会卡。
        """
        sm = self._selection()
        if sm is None or not sm.hasSelection():
            return _OFF
        total = self.total_rows()
        if total and len(sm.selectedRows()) >= total:
            return _ON
        return _PART

    # ── 交互 ────────────────────────────────────────────────────
    def toggle_row(self, row):
        """切换该行选中态（累加式：勾第二行不会取消第一行）。"""
        sm, mdl = self._selection(), self._model()
        if sm is None or mdl is None or not (0 <= row < mdl.rowCount()):
            return
        cols = mdl.columnCount()
        if cols <= 0:
            return
        band = QItemSelection(mdl.index(row, 0), mdl.index(row, cols - 1))
        sm.select(band, QItemSelectionModel.Deselect
                  if self.is_row_checked(row) else QItemSelectionModel.Select)

    def set_all(self, checked: bool):
        """角标全选：True=全选当前可见行，False=清空。"""
        if self._view.model() is None:
            return
        if checked:
            self._view.selectAll()
        else:
            self._view.clearSelection()

    def _section_at(self, pos):
        """QHeaderView 在 PySide6 6.6 没有 sectionAt()，按 position/size 线性定位。"""
        y = pos.y()
        for visual in range(self.count()):
            p = self.sectionViewportPosition(visual)
            s = self.sectionSize(visual)
            if p <= y < p + s:
                return self.logicalIndex(visual)
        return -1

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            row = self._section_at(event.position().toPoint())
            if row >= 0:
                self.toggle_row(row)
                event.accept()
                return
        super().mousePressEvent(event)

    # ── 绘制 ────────────────────────────────────────────────────
    def paintEvent(self, event):
        if not self.isVisible() or self.width() <= 0:
            return
        vp = self.viewport()
        painter = QPainter(vp)
        if not painter.isActive():
            return
        mdl = self._model()
        try:
            bg = QColor(Thm.color("surface2"))
            line = QColor(Thm.color("border"))
            num_pen = QColor(Thm.color("textFaint"))
            font = num_font(10)
            painter.setFont(font)
            fm = QFontMetrics(font)
            for logical in range(self.count()):
                y = self.sectionViewportPosition(logical)
                h = self.sectionSize(logical)
                if y + h < event.rect().top() or y > event.rect().bottom():
                    continue
                rect = QRect(0, y, self.width(), h)
                painter.fillRect(rect, bg)
                painter.setPen(line)
                painter.drawLine(rect.bottomLeft(), rect.bottomRight())
                state = _ON if self.is_row_checked(logical) else _OFF
                # _box_rect 给的是「节区内」坐标，必须按节区原点平移，否则勾选框
                # 会全部叠在视口顶部（探针取色实测踩过这个坑）。
                paint_check(painter, _box_rect(self.width(), h).translated(0, y), state)
                # 行号取自模型的 headerData：主表挂的是 AuditProxyModel，它返回的就是
                # **当前视图第几行**（筛选/排序后依旧 1..N 连续），不是 Excel 里的原始行号
                label = "" if mdl is None else str(
                    mdl.headerData(logical, Qt.Vertical, Qt.DisplayRole) or "")
                painter.setPen(num_pen)
                painter.drawText(QRect(_CHK_X + _CHK + 4, y,
                                       self.width() - _CHK_X - _CHK - 6, h),
                                 Qt.AlignRight | Qt.AlignVCenter,
                                 fm.elidedText(label, Qt.ElideRight,
                                               self.width() - _CHK_X - _CHK - 6))
        finally:
            painter.end()


class SelectAllCheck(QWidget):
    """左上角标 = 设计稿表头里的全选框（三态），点一下全选/清空当前可见行。"""

    toggled = Signal(bool)

    def __init__(self, header: RowCheckHeader, parent=None):
        super().__init__(parent)
        self._header = header
        # 尺寸不写死：由 MainTableView 摆成「垂直表头宽 × 水平表头高」那块交叉区
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("全选 / 取消全选（只作用于当前筛选后可见的行）")
        self._theme_cb = lambda *_: self.update()
        Thm.on_change(self._theme_cb)
        self.destroyed.connect(lambda _o=None, c=self._theme_cb: Thm.unregister(c))
        header.checked_changed.connect(self.update)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.toggled.emit(self._header.check_state() != _ON)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return
        try:
            painter.fillRect(self.rect(), QColor(Thm.color("surface2")))
            painter.setPen(QColor(Thm.color("border")))
            painter.drawLine(self.rect().bottomLeft(), self.rect().bottomRight())
            box = _box_rect(self.width(), self.height())
            paint_check(painter, box, self._header.check_state())
        finally:
            painter.end()
