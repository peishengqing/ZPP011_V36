# -*- coding: utf-8 -*-
"""主表格单元格自绘代理 — v43.349 第五期E（照抄设计稿 index.html 的表格格式）

设计稿里表格有三处"不是数据、是格式"的东西，QSS 与模型角色都表达不了，
只能由 delegate 在 super().paint() 之后叠一层：

1. 悬浮行高亮（`.tbl tbody tr:hover`）—— 用半透明叠加，不能像 QSS
   ``::item:hover`` 那样整格刷成实色。因为本表把行色当数据用（审核后变更浅红、
   隔离区浅黄、替代料浅蓝、未投料浅绿、偏差率预警浅橙、替代料组归组色），
   实色悬浮会在鼠标划过时把这些含义全部抹掉。半透明叠加则与它们叠色共存。
2. 选中格左缘 3px 主色条（``tr.sel td:first-child{box-shadow:inset 3px 0 0 primary}``）。
   本表选择行为是 SelectItems（单元格级，非整行），所以条纹画在每个选中格的左缘。
3. 状态胶囊（``.pill``）—— 「偏差区间」列的 正偏差/负偏差/零偏差 由实色文字
   改成"浅底 + 语义色文字 + 同色描边"的胶囊；语义仍是超投红、节约绿。

配色全部经 ``Thm.color(令牌)`` 现取，不写死十六进制：暗色切换自动换档。
"""

from PySide6.QtCore import QEvent, QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QStyle, QStyleOptionViewItem, QStyledItemDelegate

from utils.theme_manager import Thm

# 胶囊列：列名 → (显示值 → (文字/边框令牌, 底色令牌))
_PILL_SPECS = {
    "偏差区间": {
        "正偏差": ("danger", "dangerSoft"),
        "负偏差": ("ok", "okSoft"),
        "零偏差": ("textMuted", "surface3"),
    },
}

_PILL_H = 19          # 设计稿 .pill height
_PILL_PAD_X = 7       # 设计稿 .pill padding
_CELL_PAD_X = 10      # 设计稿 td padding-left
_HOVER_ALPHA = 26     # 悬浮叠色不透明度：够看出"鼠标在哪一行"，又不盖掉行色含义


class RowStyleDelegate(QStyledItemDelegate):
    """在原生绘制之上叠加：悬浮行叠色 + 选中格左缘主色条 + 状态胶囊。"""

    #: 悬浮行变了（右侧操作道靠它决定「这一行要不要露出小按钮」，见 row_action_lane）
    hover_row_changed = Signal(int)

    def __init__(self, view: QAbstractItemView, parent=None):
        super().__init__(parent or view)
        self._view = view
        self._hover_row = -1
        self._hover_pos = None
        vp = view.viewport()
        vp.setMouseTracking(True)
        vp.installEventFilter(self)
        # 滚动后同一鼠标位置对应另一行：按光标位置重算，避免残留高亮跑错行
        sb = view.verticalScrollBar()
        if sb is not None:
            sb.valueChanged.connect(self._recheck_hover)

    # ── 悬浮行跟踪 ────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        et = event.type()
        if et == QEvent.Type.MouseMove:
            self._hover_pos = event.position().toPoint()
            self._recheck_hover()
        elif et == QEvent.Type.Leave:
            self._hover_pos = None
            self._set_hover_row(-1)
        return False   # 只旁听，绝不吞事件（排序/点选/右键菜单照常）

    def _recheck_hover(self, *_):
        if self._hover_pos is None or not self._view.viewport().underMouse():
            self._set_hover_row(-1)
            return
        idx = self._view.indexAt(self._hover_pos)
        self._set_hover_row(idx.row() if idx.isValid() else -1)

    def _set_hover_row(self, row):
        if row == self._hover_row:
            return
        old, self._hover_row = self._hover_row, row
        self._repaint_row(old)
        self._repaint_row(row)
        self.hover_row_changed.emit(row)

    # 对外两个口：右侧操作道读当前悬浮行、也能把悬浮行设回来（鼠标划过操作道时
    # 整行照样要亮 —— 悬浮行只有一个真源，就是这个代理）
    def hover_row(self):
        return self._hover_row

    def set_hover_row(self, row):
        self._set_hover_row(row)

    def _repaint_row(self, row):
        """只重绘这一行所在的视口条带（整表 update 在万行表上会闪）。"""
        if row < 0:
            return
        v = self._view
        h = v.rowHeight(row)
        y = v.rowViewportPosition(row)
        if h <= 0 or y + h < 0 or y > v.viewport().height():
            return
        v.viewport().update(0, y, v.viewport().width(), h)

    # ── 绘制 ──────────────────────────────────────────────────────
    def paint(self, painter, option, index):
        pill = self._pill_of(index)
        if pill is None:
            super().paint(painter, option, index)
        else:
            # 借原生画背景（含交替行色/行标记/选中），只把文字留给胶囊自己画
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            opt.text = ""
            super().paint(painter, opt, index)
            self._paint_pill(painter, opt, pill[0], pill[1])
        if painter.hasClipping():
            painter.setClipRect(option.rect)   # 叠层限制在本格内，不越界蹭到邻格
        self._paint_row_tint(painter, option, index)
        self._paint_selection_bar(painter, option, index)

    def _pill_of(self, index):
        """返回 (文字, (文字色令牌, 底色令牌))；该格不该画胶囊时返回 None。"""
        spec = _PILL_SPECS.get(self._column_name(index))
        if not spec:
            return None
        text = str(index.data(Qt.DisplayRole) or "").strip()
        tokens = spec.get(text)
        if tokens is None:
            return None
        return text, tokens

    def _column_name(self, index):
        mdl = index.model()
        try:
            return str(mdl.headerData(index.column(), Qt.Horizontal, Qt.DisplayRole) or "")
        except Exception:
            return ""

    def _paint_pill(self, painter, option, text, tokens):
        fg = QColor(Thm.color(tokens[0]))
        bg = QColor(Thm.color(tokens[1]))
        font = QFont(option.font)
        font.setPixelSize(11)
        font.setBold(True)      # 设计稿 .pill font-weight:600
        painter.save()
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setFont(font)
        w = QFontMetrics(font).horizontalAdvance(text) + _PILL_PAD_X * 2
        rect = QRect(option.rect.left() + _CELL_PAD_X,
                     option.rect.center().y() - _PILL_H // 2,
                     min(w, max(24, option.rect.width() - _CELL_PAD_X - 2)), _PILL_H)
        painter.setBrush(bg)
        bd = QColor(fg)
        bd.setAlpha(96)         # 设计稿 .pill 同色淡描边
        painter.setPen(QPen(bd, 1))
        painter.drawRoundedRect(rect, _PILL_H // 2, _PILL_H // 2)
        inner = rect.adjusted(_PILL_PAD_X, 0, -_PILL_PAD_X, 0)
        fm = QFontMetrics(font)
        painter.setPen(fg)
        painter.drawText(inner, Qt.AlignCenter, fm.elidedText(text, Qt.ElideRight, inner.width()))
        painter.restore()

    def _paint_row_tint(self, painter, option, index):
        if self._hover_row < 0 or index.row() != self._hover_row:
            return
        c = QColor(Thm.color("textFaint"))
        c.setAlpha(_HOVER_ALPHA)
        painter.fillRect(option.rect, c)

    def _paint_selection_bar(self, painter, option, index):
        if not (option.state & QStyle.State.State_Selected):
            return
        painter.fillRect(QRect(option.rect.left(), option.rect.top(), 3,
                               option.rect.height()), QColor(Thm.color("primary")))
