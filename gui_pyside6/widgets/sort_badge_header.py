# -*- coding: utf-8 -*-
"""
自定义表头：在已排序列角上叠加「层级数字 + 升降箭头」角标（多级排序一眼可见），
并在已设 Excel 式取值过滤的列“列名左侧”画橙色漏斗标（贴近 Excel 表头筛选图标）。

从 main_window 抽取为共享组件，供主表与所有分析对话框统一使用。

paintEvent 仅 override：先 super().paintEvent 画出原生表头（外观完全保持），
再叠加角标 / 漏斗。漏斗标的绘制与「是否有排序列」无关——
（修复原实现：未排序却已设取值过滤时不画漏斗的 bug）。

新增（2026-10-01）：
- 已筛选列的漏斗图标放在“列名左侧”（rect.left()+2 起，垂直居中），而非列头右侧；
- 提供 set_funnel_clicked_handler：点击漏斗命中区域时直接回调（打开该列筛选浮层），
  不需要先开启“列头筛选”模式；未命中漏斗时保持原有排序/筛选路由不变。
"""

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QPolygon, QFont, QFontMetrics
from PySide6.QtWidgets import QHeaderView
from gui_pyside6.utils.click_debug import click_log


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
        self._on_funnel_clicked = None  # 注入：点击漏斗图标回调（直接打开该列筛选）
        self._funnel_rects = {}  # logical_index -> QRect（漏斗命中区域，供 mouseRelease 判定）

    def set_sort_columns_getter(self, getter):
        self._get_sort_columns = getter

    def set_filtered_columns_getter(self, getter):
        self._get_filtered_columns = getter

    def set_funnel_clicked(self, handler):
        """注入“点击漏斗图标”回调：handler(logical_index)。未注入时漏斗仅作视觉提示。"""
        self._on_funnel_clicked = handler

    def _funnel_badge_rect(self, col):
        """按需计算某已筛选列的漏斗角标矩形（与 paintEvent 的绘制布局完全一致）。

        不依赖 paint 是否已执行：表头隐藏过/未重绘时 _funnel_rects 可能为空，
        命中判定若只看缓存会在「漏斗画了但点不到」时失手，故统一按需计算。

        修复（2026-10-02）：col 0（已读图标列）也允许画漏斗/可点——读/未读
        正是常用漏斗筛选；旧守卫 col <= 0 会把它静默跳过（排序角标仍跳过 col 0）。"""
        if col < 0 or col >= self.count():
            return None
        rect = QRect(self.sectionPosition(col), 0, self.sectionSize(col), self.height())
        if rect.width() <= 0:
            return None
        badge_w = 18
        badge_h = max(18, self.height() - 4)
        bx = rect.left() + 2
        by = max(2, (self.height() - badge_h) // 2)
        return QRect(bx, by, badge_w, badge_h)

    @staticmethod
    def _click_log(msg):
        """点击链路诊断日志：默认关闭，设 ZPP011_CLICK_DEBUG=1 才写盘（见 utils/click_debug）。"""
        click_log(msg)

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
        # 优先判定：是否点中某已筛选列的漏斗图标 → 直接打开该列筛选（不触发行级 sectionClicked）。
        # 命中区按需计算（不依赖 paint 缓存 _funnel_rects）：表头若尚未重绘过，缓存为空，
        # 依赖缓存会导致「漏斗画出来了但点不到」。
        if self._on_funnel_clicked is not None:
            for col in sorted(self._get_filtered_columns()):
                fr = self._funnel_badge_rect(col)
                if fr is not None and fr.contains(pos):
                    self._click_log(f"[release] 命中漏斗 col={col} pos=({pos.x()},{pos.y()}) → 直接打开筛选")
                    self._on_funnel_clicked(col)
                    return
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
        # 修复（2026-10-02，真机探针实测）：Qt6 的 QHeaderView 是 QAbstractScrollArea，
        # 节区实际渲染在**内部 viewport 层**；在 frame（self）上建 QPainter 激活恒失败
        # （isActive()=False 直接 return）→ 排序角标与漏斗此前**从未真正画出来过**。
        # 叠加层必须画在 viewport 上；节区坐标用 sectionViewportPosition（与节区同坐标系），
        # 漏斗角标矩形沿用 _funnel_badge_rect（widget 坐标，供点击命中判定），画时换算偏移。
        vp = self.viewport()
        painter = QPainter(vp)
        if not painter.isActive():
            return
        ox, oy = vp.pos().x(), vp.pos().y()
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            # 多级排序角标：层级数字 + 升降箭头，方向明示（蓝=升/橙=降）
            for level, (col, asc) in enumerate(cols, start=1):
                if col <= 0 or col >= count:
                    continue
                rect = QRect(self.sectionViewportPosition(col) - ox, 0,
                             self.sectionSize(col), self.height())
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
            # 列头筛选漏斗标（Excel 风格）：已设取值过滤的列在“列名左侧”画漏斗角标。
            # 角标矩形与点击命中区共用 _funnel_badge_rect（单一来源，保证所见即可点）。
            self._funnel_rects.clear()
            for col in fcols:
                badge = self._funnel_badge_rect(col)
                if badge is None:
                    continue
                # widget 坐标 → viewport 坐标（默认 margin=0，偏移为 0）
                badge = badge.translated(-ox, -oy)
                fcolor = QColor(217, 119, 45)
                fbg = QColor(255, 237, 213)
                fborder = QColor(217, 119, 45)
                # 底色圆角框 + 橙色边框：一眼看出该列已筛选
                painter.setBrush(fbg)
                painter.setPen(QPen(fborder, 1))
                painter.drawRoundedRect(badge, 3, 3)
                # 漏斗：上宽下窄，贴近 Excel 表头筛选图标；不画列名文字，只显示漏斗
                cx = badge.center().x()
                top_y = badge.top() + 3
                bottom_y = badge.bottom() - 3
                mid_y = badge.center().y()
                top_w = 10
                neck_w = 3
                funnel = QPolygon([
                    QPoint(cx - top_w // 2, top_y),
                    QPoint(cx + top_w // 2, top_y),
                    QPoint(cx + neck_w // 2, mid_y + 1),
                    QPoint(cx + neck_w // 2, bottom_y),
                    QPoint(cx - neck_w // 2, bottom_y),
                    QPoint(cx - neck_w // 2, mid_y + 1),
                ])
                painter.setBrush(fcolor)
                painter.setPen(QPen(fcolor, 1))
                painter.drawPolygon(funnel)
                # 记录命中区域（widget 坐标，logical_index 对齐 fcols）
                self._funnel_rects[col] = badge.translated(ox, oy)
        finally:
            painter.end()
