# -*- coding: utf-8 -*-
"""
自定义表头：在已排序列角上叠加「层级数字 + 升降箭头」角标（多级排序一眼可见），
并在已设 Excel 式取值过滤的列左上角画橙色漏斗标。

从 main_window 抽取为共享组件，供主表与所有分析对话框统一使用。

paintEvent 仅 override：先 super().paintEvent 画出原生表头（外观完全保持），
再叠加角标 / 漏斗。漏斗标的绘制与「是否有排序列」无关——
（修复原实现：未排序却已设取值过滤时不画漏斗的 bug）。
"""
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QPolygon, QFont, QFontMetrics
from PySide6.QtWidgets import QHeaderView


class SortBadgeHeader(QHeaderView):
    """自定义表头：多级排序角标 + Excel 式取值过滤漏斗标。

    仅 override paintEvent —— 先 super().paintEvent(event) 画出原样表头，再在每个已排序列
    右上角叠一个角标（如「1▲」蓝升 /「2▼」橙降），并在已设取值过滤的列左上角画橙色漏斗。
    不改动任何列标签或原生外观，零回归风险。
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._get_sort_columns = lambda: []        # 注入：返回 [(列号, 是否升序), ...]
        self._get_filtered_columns = lambda: set()  # 注入：返回已设取值过滤的列号集合
        self._ctrl_held = False  # mousePressEvent 捕获 Ctrl 修饰符，供点击路由可靠读取

    def set_sort_columns_getter(self, getter):
        self._get_sort_columns = getter

    def set_filtered_columns_getter(self, getter):
        self._get_filtered_columns = getter

    def mousePressEvent(self, event):
        # 鼠标按下时捕获修饰符：QApplication.keyboardModifiers() 在 sectionClicked handler
        # 里经常读不到 Ctrl（Qt 经典坑），故改在 mousePressEvent 可靠捕获。
        self._ctrl_held = bool(event.modifiers() & Qt.ControlModifier)
        # v43.116 诊断：记录按下位置与命中列（logical），用于分辨"没点到表头/点错列"
        try:
            pos = event.position().toPoint()
        except Exception:
            pos = event.pos()
        sec = self.sectionAt(pos)
        lg = self.sectionToLogical(sec) if sec >= 0 else -1
        import os, time
        try:
            with open(os.path.join(os.environ.get("TEMP", ""), "zpp011_click.log"), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] [press] 表头按下 sec={sec} logical={lg} "
                        f"ctrl={self._ctrl_held} 可见={self.isVisible()}\n")
        except Exception:
            pass
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # v43.116 诊断：记录释放位置与命中列；若与按下列不同，Qt 会把点击当作
        # 「调列宽拖拽」而不发 sectionClicked → 表现为「点列头没反应」。
        try:
            pos = event.position().toPoint()
        except Exception:
            pos = event.pos()
        sec = self.sectionAt(pos)
        lg = self.sectionToLogical(sec) if sec >= 0 else -1
        import os, time
        try:
            with open(os.path.join(os.environ.get("TEMP", ""), "zpp011_click.log"), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] [release] 表头释放 sec={sec} logical={lg}\n")
        except Exception:
            pass
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        # 无渲染引擎（顶层未可见/离屏/窗口未就绪）时整段 paint 跳过——原生 paintEvent 内部
        # 的 QStylePainter 同样会因 begin 失败刷警告，守卫置于 super() 之前；可见后下次重绘补画。
        if not self.isVisible() or self.width() <= 0:
            return
        super().paintEvent(event)  # 先画原生表头（外观完全保持）
        cols = self._get_sort_columns()
        fcols = self._get_filtered_columns()
        if not cols and not fcols:
            return
        count = self.count()
        painter = QPainter(self)
        if not painter.isActive():
            return
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            # 多级排序角标：层级数字 + 升降箭头，方向明示（蓝=升/橙=降）
            for level, (col, asc) in enumerate(cols, start=1):
                if col <= 0 or col >= count:
                    continue
                rect = QRect(self.sectionPosition(col), 0, self.sectionSize(col), self.height())
                if rect.width() <= 0:  # 隐藏列不画
                    continue
                txt = f"{level}{'▲' if asc else '▼'}"
                font = QFont(self.font())
                font.setPointSize(9)
                font.setBold(True)
                painter.setFont(font)
                metrics = QFontMetrics(font)
                pad_x, pad_y = 4, 2
                tw = metrics.horizontalAdvance(txt) + pad_x * 2
                th = metrics.height() + pad_y
                bx = rect.right() - tw - 2
                by = rect.top() + 2
                badge = QRect(bx, by, tw, th)
                color = QColor(45, 125, 210) if asc else QColor(217, 119, 45)
                painter.setBrush(color)
                painter.setPen(QPen(Qt.NoPen))
                painter.drawRoundedRect(badge, 3, 3)
                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.drawText(badge, Qt.AlignCenter, txt)
            # 列头筛选漏斗标：已设取值过滤的列在左上角画一个小橙三角
            fbrush = QColor(217, 119, 45)
            fpen = QPen(fbrush)
            for col in fcols:
                if col <= 0 or col >= count:
                    continue
                rect = QRect(self.sectionPosition(col), 0, self.sectionSize(col), self.height())
                if rect.width() <= 0:
                    continue
                s = 7
                tri = QPolygon([
                    QPoint(rect.left() + 3, rect.top() + 3),
                    QPoint(rect.left() + 3 + s, rect.top() + 3),
                    QPoint(rect.left() + 3 + s // 2, rect.top() + 3 + s),
                ])
                painter.setBrush(fbrush)
                painter.setPen(fpen)
                painter.drawPolygon(tri)
        finally:
            painter.end()
