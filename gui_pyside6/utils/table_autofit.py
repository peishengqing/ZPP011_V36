# -*- coding: utf-8 -*-
"""ZPP011 表格列宽统一自适应（v43.300，裴哥 2026-11-05 选方案 C 全项目收编）。

全项目原有 8 张 QTableView + 19 处 QTableWidget 共 6 类互不相同的列宽策略，
本模块提供唯一实现：一张表挂一个 :class:`AdaptiveTable`，由
:func:`install_adaptive` 统一安装。

历史红线（都是事故换来的，勿删注释、勿违反）：
  1. 主表万行级**禁止** ``resizeColumnsToContents()``：同步逐行测宽会卡死主线程、
     整窗变黑「未响应」（controllers/column_controller.py:202-203、
     dialogs/deviation_warning_dialog.py:1191-1193、main_window.py:780-789）。
     本模块一律不调用它，改用「表头 sectionSizeHint + 限量采样字宽」估算内容宽，
     采样行数上限 SAMPLE_ROWS，绝不扫全表。
  2. ``QHeaderView.ResizeToContents`` 模式下 ``setColumnWidth()`` 语义冲突，
     且 ``StretchLastSection(True)`` 会让最后一列独吞余量、放大后右侧大片空白
     （dialogs/alert_dialog.py:978-983、dialogs/quarantine_dialog.py:150）。
     本模块统一把表头切回 Interactive + StretchLastSection(False) 再设宽。
  3. QSS 不得改 sizeHint（widgets/board_visual.py:36-42，顶部筛选栏逐像素精算）。
  4. 列宽按**列名**识别，绝不按列索引缓存（setDataFrame 重排列会错位，
     dialogs/alert_dialog.py:781、dialogs/deviation_warning_dialog.py:1552）。
  5. 「最大化时不要覆盖用户手动调过的列宽」
     （dialogs/deviation_warning_dialog.py:646-648）：用户拖过任一列后停止自动
     重算，直到显式调用 :meth:`AdaptiveTable.reset_and_refit`。
  6. SortBadgeHeader 的漏斗/排序角标不占列宽
     （widgets/sort_badge_header.py:50-67），内容宽额外预留 BADGE_PAD px，
     避免自适应后角标压住列名文字。
  7. 事件过滤用独立 QObject，不覆盖宿主类自己的 ``eventFilter()``
     （沿用 widgets/board_visual.py:161-176 的 _FloatPosWatcher 模式）。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QEvent, QObject, QTimer
from PySide6.QtWidgets import QHeaderView

DEFAULT_MIN_SECTION = 50
DEFAULT_MAX_SECTION = 420
DEFAULT_DEBOUNCE_MS = 300
SAMPLE_ROWS = 120          # 内容采样上限：绝不扫全表
BADGE_PAD = 20             # SortBadgeHeader 漏斗/排序角标占位
MIN_EXTRA_PX = 8           # 余量小于此值不折腾，避免抖动
TEXT_PAD = 16              # 单元格左右内边距估计
SAMPLE_CHARS = 80          # 单格参与测宽的最大字符数（长备注截断估计）
LONG_TEXT_KEYS = ('名称', '描述', '物料', '备注', '原因', '说明', '建议', '结论', '内容')


def _clamp(value, lo, hi):
    return max(int(lo), min(int(hi), int(value)))


def _col_name(view, col):
    """按列名取表头文本；不缓存索引，避免模型重排后错位。"""
    model = view.model()
    if model is None:
        return ''
    try:
        value = model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
    except (TypeError, RuntimeError):
        try:
            value = model.headerData(col, Qt.Horizontal)
        except (TypeError, RuntimeError):
            return ''
    return '' if value is None else str(value).replace('\n', '')


def _is_long_text(name):
    return any(k in name for k in LONG_TEXT_KEYS)


class AdaptiveTable(QObject):
    """单张表的列宽自适应控制器。

    mode:
      ``'content'``    按表头 + 限量采样估内容宽，再分配视口余量（看板 / 小结果表）。
      ``'distribute'`` 只分配视口余量，**绝不测内容**（主表万行红线）。
      ``'off'``        不自动重算，仅保留手动触发能力。

    respect_fixed=True 时跳过原本被设成 Fixed 的列、也不改 StretchLastSection，
    用于 left_panel / 变动明细 / 看板明细等历史逐像素精算过的固定布局。
    """

    def __init__(self, view, *, mode='content',
                 min_section=DEFAULT_MIN_SECTION,
                 max_section=DEFAULT_MAX_SECTION,
                 debounce_ms=DEFAULT_DEBOUNCE_MS,
                 sample_rows=SAMPLE_ROWS,
                 respect_fixed=False,
                 parent=None):
        super().__init__(parent if parent is not None else view)
        self._view = view
        self.mode = mode
        self._min = min_section
        self._max = max_section
        self._debounce_ms = debounce_ms
        self._sample_rows = sample_rows
        self.respect_fixed = respect_fixed
        self._user_touched = False
        self._applying = False
        self._installed = False

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_refit)

        header = view.horizontalHeader()
        # 用户拖拽标记：程序自身设宽时 _applying=True，不误标成用户拖过
        header.sectionResized.connect(self._on_section_resized)
        view.installEventFilter(self)
        # 顶层窗口也监听：showMaximized 但子 view 尺寸恰好不变时仍能收到通知
        self._top = view.window()
        if self._top is not None and self._top is not view:
            self._top.installEventFilter(self)
        self._installed = True

    # ------------------------------------------------------------------
    # 对外 API
    # ------------------------------------------------------------------
    @property
    def user_touched(self):
        return self._user_touched

    def request_refit(self, delay=None):
        """请求重算（带防抖合并）。用户拖过列宽 / 已卸载时直接忽略。"""
        if self.mode == 'off' or self._user_touched or not self._installed:
            return
        self._timer.stop()
        self._timer.start(self._debounce_ms if delay is None else int(delay))

    def schedule_initial(self):
        """setModel / set_data 之后调用：延迟到下一轮事件循环再算，避免阻塞首帧。

        对应 dialogs/deviation_warning_dialog.py:1191-1193 的历史踩坑。
        """
        if self.mode == 'off' or self._user_touched or not self._installed:
            return
        QTimer.singleShot(0, self._do_refit)

    def refit_now(self):
        """立即重算（忽略防抖，但仍尊重用户拖拽标记）。"""
        self._timer.stop()
        self._do_refit()

    def reset_and_refit(self):
        """「重置列宽」入口：清掉用户拖拽标记后重新自适应。"""
        self._user_touched = False
        self.refit_now()

    def uninstall(self):
        if not self._installed:
            return
        self._timer.stop()
        try:
            self._view.removeEventFilter(self)
            if self._top is not None and self._top is not self._view:
                self._top.removeEventFilter(self)
        except RuntimeError:
            pass
        try:
            self._view.horizontalHeader().sectionResized.disconnect(
                self._on_section_resized)
        except (RuntimeError, TypeError):
            pass
        self._installed = False
        if getattr(self._view, '_adaptive_table', None) is self:
            self._view._adaptive_table = None

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _on_section_resized(self, *_args):
        if not self._applying:
            self._user_touched = True

    def eventFilter(self, obj, event):
        if self._installed and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.request_refit()
        return False

    def _visible_cols(self, view, model):
        cols = [c for c in range(model.columnCount()) if not view.isColumnHidden(c)]
        if self.respect_fixed:
            header = view.horizontalHeader()
            cols = [c for c in cols
                    if header.sectionResizeMode(c) != QHeaderView.Fixed]
        return cols

    def _content_width(self, view, header, col):
        """表头 sizeHint（不扫数据行）+ 限量采样数据字宽，取较大者。"""
        width = header.sectionSizeHint(col)
        model = view.model()
        if model is None:
            return width
        fm = view.fontMetrics()
        rows = min(model.rowCount(), self._sample_rows)
        for row in range(rows):
            try:
                value = model.data(model.index(row, col), Qt.DisplayRole)
            except RuntimeError:
                continue
            if value is None:
                continue
            text = str(value)[:SAMPLE_CHARS]
            if not text:
                continue
            try:
                px = fm.horizontalAdvance(text)
            except AttributeError:
                px = fm.boundingRect(text).width()
            if px + TEXT_PAD > width:
                width = px + TEXT_PAD
        return width + BADGE_PAD

    def _distribute_extra(self, view, cols):
        """把视口余量按列名权重分给可见列；超出视口则保留横向滚动，不硬压。"""
        header = view.horizontalHeader()
        budget = view.viewport().width()
        if budget <= 0:
            return
        widths = [header.sectionSize(c) for c in cols]
        extra = budget - sum(widths)
        if extra < MIN_EXTRA_PX:
            return
        weights = [2.0 if _is_long_text(_col_name(view, c)) else 1.0 for c in cols]
        total_weight = sum(weights)
        if total_weight <= 0:
            return
        for col, weight, current in zip(cols, weights, widths):
            add = int(extra * weight / total_weight)
            if add <= 0:
                continue
            target = _clamp(current + add, self._min, self._max)
            if target != current:
                view.setColumnWidth(col, target)

    def _do_refit(self):
        if self.mode == 'off' or self._user_touched or not self._installed:
            return
        view = self._view
        try:
            header = view.horizontalHeader()
            model = view.model()
        except RuntimeError:
            return
        if model is None or model.columnCount() == 0:
            return
        # 整表列宽锁（QHeaderView.Fixed）时跳过，保留 column_controller 的锁语义
        try:
            if header.sectionResizeMode(0) == QHeaderView.Fixed and not self.respect_fixed:
                return
        except RuntimeError:
            return
        cols = self._visible_cols(view, model)
        if not cols:
            return

        self._applying = True
        try:
            # 破掉 ResizeToContents + StretchLastSection 的历史冲突（红线 2）
            if not self.respect_fixed:
                header.setSectionResizeMode(QHeaderView.Interactive)
                header.setStretchLastSection(False)
                header.setMinimumSectionSize(self._min)
                header.setMaximumSectionSize(self._max)
            if self.mode == 'content':
                measured = {c: self._content_width(view, header, c) for c in cols}
                for col, width in measured.items():
                    target = _clamp(width, self._min, self._max)
                    if target != header.sectionSize(col):
                        view.setColumnWidth(col, target)
            # 两种模式都做余量分配：这是「窗口变宽消留白」的核心
            self._distribute_extra(view, cols)
        finally:
            self._applying = False


def install_adaptive(view, *, mode='content', key=None, **kwargs):
    """给一张 QTableView/QTableWidget 安装（或替换）列宽自适应控制器。

    ``key`` 仅用于日志/持久化分组标识，可选。返回 :class:`AdaptiveTable`，
    并以 ``view._adaptive_table`` 保活（QObject 子对象 + 显式引用双保险）。
    重复调用会先卸载旧控制器，避免两套机制打架。
    """
    previous = getattr(view, '_adaptive_table', None)
    if previous is not None:
        previous.uninstall()
    controller = AdaptiveTable(view, mode=mode, **kwargs)
    controller._key = key
    view._adaptive_table = controller
    return controller


def get_adaptive(view):
    """取回已安装的控制器；未安装返回 None。"""
    return getattr(view, '_adaptive_table', None)
