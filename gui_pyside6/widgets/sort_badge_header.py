# -*- coding: utf-8 -*-
"""
自定义表头：在已排序列角上叠加「层级数字 + 升降箭头」角标（多级排序一眼可见），
并在已设 Excel 式取值过滤的列左上角画橙色漏斗标。

从 main_window 抽取为共享组件，供主表与所有分析对话框统一使用。

paintEvent 仅 override：先 super().paintEvent 画出原生表头（外观完全保持），
再叠加角标 / 漏斗。漏斗标的绘制与「是否有排序列」无关——
（修复原实现：未排序却已设取值过滤时不画漏斗的 bug）。
"""
import os
import time

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

    @staticmethod
    def _click_log(msg):
        """v43.116 诊断：把表头点击链路日志追加到 %TEMP%\\zpp011_click.log。
        写盘失败（无 TEMP / 权限）静默吞掉——日志是诊断辅助，绝不能反过来让程序崩。"""
        try:
            log_path = os.path.join(os.environ.get("TEMP", ""), "zpp011_click.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    def _section_at(self, pos):
        """v43.118 修：把鼠标 position 映射到列号。
        Qt6 的 QHeaderView 已移除 sectionAt / sectionToLogical / logicalSectionAt
        （旧 C++ API，PySide6 里全为 False），改用 sectionPosition/sectionSize
        （本类 paintEvent 已在用、稳）逐段线性定位，返回 (visual, logical)。"""
        try:
            count = self.count()
            x = pos.x()
            for visual in range(count):
                p = self.sectionPosition(visual)
                s = self.sectionSize(visual)
                if p <= x < p + s:
                    return visual, self.logicalIndex(visual)
            return -1, -1
        except Exception:
            return -1, -1

    def setModel(self, model):
        # 关键修复（v43.119）：QTableView.setModel 会调用 header.setModel，并把 header 的
        # sectionsClickable 重置为默认 False —— 而本项目的 PySide6 版本下 setSortingEnabled(True)
        # 并不会把它设回 True。结果是列头点击不发射 sectionClicked 信号，导致所有依赖该信号的
        # 功能（点击列头排序 / 列头 Excel 式取值筛选）彻底哑火（表现即"点列头既不可排序也不可筛选"）。
        # 这里在模型一挂上就重新打开 clickable，覆盖 setModel 的重置；主表与全部看板共用的
        # SortBadgeHeader 统一受益，无需在 dialog 的 set_data 里逐个补救。
        super().setModel(model)
        self.setSectionsClickable(True)

    def mousePressEvent(self, event):
        # 鼠标按下时捕获修饰符：QApplication.keyboardModifiers() 在 sectionClicked handler
        # 里经常读不到 Ctrl（Qt 经典坑），故改在 mousePressEvent 可靠捕获。
        self._ctrl_held = bool(event.modifiers() & Qt.ControlModifier)
        # v43.118 诊断（零功能副作用）：记录按下命中列，用于分辨"没点到表头/点错列"。
        try:
            pos = event.position().toPoint()
        except Exception:
            pos = event.pos()
        visual, logical = self._section_at(pos)
        self._click_log(f"[press] 表头按下 visual={visual} logical={logical} "
                        f"ctrl={self._ctrl_held} 可见={self.isVisible()}")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # v43.118 诊断：记录释放命中列；若与按下列不同，Qt 会把这次点击判为
        # 「调列宽拖拽」而不发 sectionClicked → 表现为「点列头没反应」。
        try:
            pos = event.position().toPoint()
        except Exception:
            pos = event.pos()
        visual, logical = self._section_at(pos)
        self._click_log(f"[release] 表头释放 visual={visual} logical={logical}")
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
