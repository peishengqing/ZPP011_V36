# -*- coding: utf-8 -*-
"""右侧悬浮操作道 —— v43.351 第五期G2：照抄设计稿 ``.rowact``（22×22 两颗，划过才出现）

设计稿原文（index.html）
----------------------
最后一列 ``<th style="width:74px"></th>`` 是空的，行里放 ``.rowact``：两颗 22×22、
圆角 4、图标 13×13 的按钮（铅笔=审核、三点=更多），``opacity:0`` 平时看不见，
``tr:hover`` 时才淡入；鼠标停在按钮上才换主色软底。

为什么是「表格旁边的第 2 块控件」而不是加一列
------------------------------------------
加真列要撞 G1 那条老墙：本项目 模型列号 == DataFrame 列号 是 1:1 映射，加一列等于
20+ 处按列号取数的代码集体 +1，列宽持久化也要迁移。
那能不能让视口右端让出 74px？试过，两条路都不通：
• ``setViewportMargins``：QTableView 每次重排（换模型/排序/隐藏列/改大小）都会在私有的
  ``layoutViews()`` 里把四个边距打回它自己算的基准值，覆盖不掉 —— 探针实测视口宽度
  纹丝不动；即使当场补上了，紧随其后的一串重排又抹掉，循环补位既收敛不了也说不清。
• 把道作为视口的子控件叠在右端：会盖住最后一列的数据，横向滚动时更明显。
所以道做成表格的**并排兄弟**（``QFrame#tableShell`` 里 [表格 | 道]），边框从 ``#tableView``
挪到壳上，两者共着一圈边框，看上去仍是同一张表的最后一列。道宽 74px 从布局里扣，
自适应列宽的预算本来就取 ``viewport().width()``，因此自动跟着少 74px，无需改动。

悬浮行只有一个真源
------------------
「划过哪一行」由 ``RowStyleDelegate`` 记着（它本来就要给整行叠淡色）。本控件只读它、
并在鼠标进入道时代它把悬浮行设过去（``set_hover_row``），所以鼠标滑到按钮上，整行
照样亮 —— 不存在第二套悬浮状态。

两颗按钮不新写功能
------------------
铅笔 = 该行审核证据卡（与右键菜单同一入口，纯只读）；三点 = 直接调既有
``_show_context_menu``（合成一个视口坐标），菜单本体一行都不复制。
"""

from PySide6.QtCore import QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QToolTip, QWidget

from gui_pyside6.themes.tokens import SIZE_PX
from gui_pyside6.utils.icons import get_icon
from utils.theme_manager import Thm

_BTN = 22            # 设计稿 .rowact button 22×22
_BTN_GAP = 2         # 设计稿 gap:2px
_BTN_R = 4           # 设计稿 border-radius:var(--r-sm)
_ICON = 13           # 设计稿 .rowact svg 13×13
_PAD_R = 12          # 贴右内边距（设计稿 td 左右各 10px，按钮组再往里收一点）
_HOVER_ALPHA = 26    # 与 RowStyleDelegate._HOVER_ALPHA 同档：两处叠色必须一样深

AUDIT, MORE = "audit", "more"
_BTN_SPEC = {AUDIT: ("edit", "审核"), MORE: ("dots", "更多")}


class RowActionLane(QWidget):
    """表格右端 74px 道：只在鼠标划过的那一行露出「审核 / 更多」两颗小按钮。"""

    #: 命中某行的按钮（行号 = 视图行号，与勾选道 / selectionModel 同一坐标系）
    audit_clicked = Signal(int)
    more_clicked = Signal(int)

    def __init__(self, view: QAbstractItemView, parent=None):
        super().__init__(parent)
        self._view = view
        self._hot = None          # 鼠标正压着的那颗按钮（None=没压）
        self.setObjectName("rowActionLane")
        self.setFixedWidth(SIZE_PX["tableRowActions"])
        self.setMouseTracking(True)
        self.setToolTip("鼠标滑到哪一行，哪一行右边就出现「审核 / 更多」")
        self._theme_cb = lambda *_: self.update()
        Thm.on_change(self._theme_cb)
        self.destroyed.connect(lambda _o=None, c=self._theme_cb: Thm.unregister(c))
        # 视口里的悬浮行变了 → 道上也得跟着露/藏按钮
        view.itemDelegate().hover_row_changed.connect(lambda _r=None: self.update())

    # ── 几何 ────────────────────────────────────────────────────
    def gutter_width(self):
        return SIZE_PX["tableRowActions"]

    def _rows_top(self):
        """视口第一行在本控件里的 y。

        道与表格是同一个壳里的兄弟，两者在同一层布局行里顶对齐，但各自的 frame/表头
        高度只属于表格，所以偏移要按「控件树里的绝对位置」算，不能假设相等。
        """
        vp = self._view.viewport()
        return self._view.y() + vp.y() - self.y()

    def _rows_bottom(self):
        """视口底在本控件里的 y：道比视口多出来的那截（横向滚动条那一行）不该画行。"""
        vp = self._view.viewport()
        return self._view.y() + vp.y() + vp.height() - self.y()

    def _btn_rects(self, row_rect):
        x1 = row_rect.right() - _PAD_R - _BTN + 1
        x0 = x1 - _BTN_GAP - _BTN
        y = row_rect.center().y() - _BTN // 2
        return [(AUDIT, QRect(x0, y, _BTN, _BTN)), (MORE, QRect(x1, y, _BTN, _BTN))]

    def _row_rect(self, row):
        """某行在本控件里的矩形；不在视口可视范围返回 None。"""
        v = self._view
        h = v.rowHeight(row)
        y = v.rowViewportPosition(row)
        if h <= 0 or y + h <= 0 or y > v.viewport().height():
            return None
        return QRect(0, self._rows_top() + y, self.width(), h)

    def hover_row(self):
        """本道当前该露出按钮的行：鼠标在道里就用道自己的，否则跟视口一致。"""
        return self._view.itemDelegate().hover_row()

    # ── 交互 ────────────────────────────────────────────────────
    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        row = self._view.rowAt(pos.y() - self._rows_top())
        self._hot = None
        rect = self._row_rect(row) if row is not None and row >= 0 else None
        if rect is not None:
            for kind, btn in self._btn_rects(rect):
                if btn.contains(pos):
                    self._hot = kind
                    break
        self.setCursor(Qt.PointingHandCursor if self._hot else Qt.ArrowCursor)
        if self._hot:
            QToolTip.showText(event.globalPosition().toPoint(), _BTN_SPEC[self._hot][1], self)
        else:
            QToolTip.hideText()
        # 划过按钮也算划过这一行（设计稿 tr:hover 本就整行亮）：悬浮行交还给代理
        self._view.itemDelegate().set_hover_row(row if row is not None else -1)
        self.update()

    def leaveEvent(self, event):
        self._hot = None
        self._view.itemDelegate().set_hover_row(-1)
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        row = self.hover_row()
        if event.button() == Qt.LeftButton and self._hot and row >= 0:
            (self.audit_clicked if self._hot == AUDIT else self.more_clicked).emit(row)
            event.accept()
            self._hot = None
            return
        super().mouseReleaseEvent(event)

    # ── 绘制 ────────────────────────────────────────────────────
    def _row_bg(self, row):
        """跟视口里那一行同色：选中→选择底色，否则模型给的行色，再否则交替色。"""
        v, mdl = self._view, self._view.model()
        sm = v.selectionModel()
        # 判定与勾选道 is_row_checked 同一套：整行选中 或 首格被选中
        if sm is not None and (sm.isRowSelected(row, QModelIndex())
                               or sm.isSelected(mdl.index(row, 0))):
            # QSS 给主表定的选择底色就是 #E7EDFB=primarySoft（::item:selected）
            return QColor(Thm.color("primarySoft"))
        idx = mdl.index(row, 0)
        for col in range(mdl.columnCount()):
            if not v.isColumnHidden(col):
                idx = mdl.index(row, col)
                break
        c = idx.data(Qt.BackgroundRole)
        if c is not None and QColor(c).isValid():
            return QColor(c)
        # 兜底走令牌而不走 palette：#tableView 的底色/交替色是 QSS 直接写死的
        # surface / surface2，视口 palette 在样式表下不保证同步
        return QColor(Thm.color("surface2" if (v.alternatingRowColors() and row % 2 == 1)
                                else "surface"))

    def paintEvent(self, event):
        mdl = self._view.model()
        painter = QPainter(self)
        if not painter.isActive():
            return
        try:
            top, bottom = self._rows_top(), max(self._rows_top(), self._rows_bottom())
            painter.fillRect(self.rect(), QColor(Thm.color("surface")))
            self._paint_header_band(painter, top)
            if mdl is None or mdl.rowCount() == 0 or bottom <= top:
                return
            # 只在视口那一段里画行：道若比视口高（表格底部还有横向滚动条），多出来
            # 的那截留底色，不能把行线画到滚动条上去
            painter.setClipRect(QRect(0, top, self.width(), bottom - top))
            hover = self.hover_row()
            line = QColor(Thm.color("border"))
            for r in range(mdl.rowCount()):
                rect = self._row_rect(r)
                if rect is None or rect.bottom() < top or rect.top() > bottom:
                    continue
                painter.fillRect(rect, self._row_bg(r))
                painter.setPen(line)
                painter.drawLine(rect.bottomLeft(), rect.bottomRight())
                if r != hover:
                    continue
                tint = QColor(Thm.color("textFaint"))
                tint.setAlpha(_HOVER_ALPHA)
                painter.fillRect(rect, tint)
                self._paint_buttons(painter, rect)
        finally:
            painter.end()

    def _paint_header_band(self, painter, top):
        """道顶端那段 = 设计稿那个空的 <th>：跟其它表头同底色 + 一条下边框。"""
        if top <= 0:
            return
        painter.fillRect(QRect(0, 0, self.width(), top), QColor(Thm.color("surface2")))
        painter.setPen(QPen(QColor(Thm.color("borderStrong"))))
        painter.drawLine(0, top - 1, self.width(), top - 1)

    def _paint_buttons(self, painter, row_rect):
        for kind, btn in self._btn_rects(row_rect):
            hot = self._hot == kind
            if hot:
                painter.setBrush(QColor(Thm.color("primarySoft")))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(btn, _BTN_R, _BTN_R)
            ink = Thm.color("primary") if hot else Thm.color("textMuted")
            pm = get_icon(_BTN_SPEC[kind][0], _ICON, ink).pixmap(_ICON, _ICON)
            painter.drawPixmap(btn.center().x() - _ICON // 2,
                               btn.center().y() - _ICON // 2, pm)
