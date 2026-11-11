# -*- coding: utf-8 -*-
"""表格看板统一视觉美化 + 悬浮「可视化看板」入口（v43.299，方案 C）。

适用范围（5 个表格看板，均为 QDialog 子类）：
  - 偏差率预警看板  DeviationWarningDialog
  - 替代料看板      AlertDialog
  - 正损看板        PosLossDashboardDialog
  - 负损看板        NegLossDashboardDialog
  - 半成品看板      SemiDashboardDialog

设计约束（都是历史事故换来的，勿违反）：
  1. **只改观感，不改布局尺寸**：QSS 里一律不写 padding / margin / font-size /
     font-family，也不给 QPushButton / QGroupBox 改 border-width。顶部筛选栏的
     宽度是 v43.139/v43.143/v43.154 逐像素精算过的（1150px 窗口差 11px 就重叠），
     任何会改 sizeHint 的规则都可能让 13 个筛选控件互相压住。
  2. 样式作用在 **dialog 自身**（setStyleSheet），并用 `QDialog#zppBoardDialog`
     后代选择器限定作用域，不污染主窗口的 light/dark 全局主题。
  3. 悬浮按钮是 dialog 的独立 child（不进任何 layout），定位交给独立的
     QObject eventFilter 监听 Resize/Show —— **不覆盖** 各看板自身的
     `eventFilter()` 方法（它们装在 table_view 上，用于右键/表头交互）。
  4. 按钮打开的是全量 14 图 HTML 看板（含瀑布图/箱线图），数据取主表
     `_get_master_df()`（列最全），避免用看板裁列后的子表导致大量图显示占位。
"""
import traceback

from PySide6.QtCore import Qt, QEvent, QObject, QTimer
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QMessageBox,
    QPushButton,
)

# ---------------------------------------------------------------------------
# 局部主题：作用域限定在挂了 objectName="zppBoardDialog" 的对话框内
#
# 🔴 尺寸红线（v43.299 offscreen 实测）：QSS 里一旦对 QPushButton / QComboBox /
#    QLineEdit 写 border / border-radius / padding，Qt 会改用 stylesheet 路径
#    重算 sizeHint —— 按钮 80x20 → 24x12、下拉 66x22 → 56x18。
#    顶部筛选栏宽度是历史逐像素精算的，尺寸一变就挤压重叠（v43.139/v43.154）。
#    故对筛选控件**只写颜色类属性**（background-color / color / selection-*），
#    offscreen 断言见 verify_board_visual2.py：5 类控件 sizeHint 前后完全一致。
#    圆角/内边距只用在「不进布局」的独立悬浮按钮与不影响筛选栏的表格/滚动条上。
#
# 🎨 颜色真源（设计稿第一期第 1 条，替代原先写死在此处的浅色值）：
#    本模块不再自带一份 hex —— 亮/暗两套 QSS 全部由
#    gui_pyside6/themes/tokens.py::build_board_qss(theme) 生成。
#    改造前这里写死 #f4f7fb / #0969da / #eef4fb 等浅色值，正是设计稿诊断 D1
#    「主窗口切到暗色、5 个表格看板依然是亮的」的直接根源（文件头旧注释把
#    「不污染主窗口全局主题」实现成了「自己也没了暗色」）。
#    v43.344 的临时绕行（桥接器在暗色时清空 dialog 级 QSS）已随之拆除。
# ---------------------------------------------------------------------------
from gui_pyside6.themes.tokens import build_board_qss


def board_qss_for(is_dark: bool) -> str:
    """按当前主题取看板 dialog 级 QSS（唯一生成处见 tokens.py）。"""
    return build_board_qss("dark" if is_dark else "light")


# 向后兼容别名：仍被外部当作「亮色看板 QSS」引用的，保持可用。
# 新代码请用 board_qss_for(Thm.is_dark)，不要再依赖这个常量。
BOARD_QSS = build_board_qss("light")

FLOAT_BTN_TEXT = "📊 可视化看板"
FLOAT_BTN_TIP = (
    "打开 14 图 HTML 可视化看板（瀑布图 / 箱线图 / 趋势 / Top10）\n"
    "数据取当前主表全量，与本窗口的筛选条件相互独立"
)


class _FloatPosWatcher(QObject):
    """把悬浮按钮钉在右下角（避开底部按钮栏），不覆盖 dialog 自身 eventFilter。"""

    def __init__(self, dialog, btn):
        super().__init__(dialog)
        self._dialog = dialog
        self._btn = btn

    def eventFilter(self, obj, event):
        if obj is self._dialog:
            try:
                if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                    QTimer.singleShot(0, self.place)
            except (AttributeError, RuntimeError):
                pass
        return False

    def place(self):
        try:
            d, b = self._dialog, self._btn
            # 距底 56px：给底部「加入隔离区 / 导出 / 关闭」按钮栏留位置
            x = d.width() - b.width() - 20
            y = d.height() - b.height() - 56
            b.move(max(0, x), max(0, y))
            b.raise_()
            b.show()
        except RuntimeError:
            pass  # 对话框已销毁


def _open_visual_board(parent, main_window, board_label):
    """点击悬浮按钮：打开 14 图 HTML 看板（与「📊 看板 ▾ → 管理看板」同源）。"""
    try:
        df = None
        if main_window is not None:
            getter = getattr(main_window, "_get_master_df", None)
            if callable(getter):
                df = getter()
            if df is None or getattr(df, "empty", True):
                vm = getattr(main_window, "view_model", None)
                df = getattr(vm, "df", None)
        if df is None or getattr(df, "empty", True):
            QMessageBox.information(parent, "提示", "暂无数据，请先进行分析。")
            return

        # 延迟导入：避免 widgets -> dialogs -> main_window 的循环依赖
        from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog

        dlg = DashboardDialog(df, None, parent=parent, main_window=main_window)
        dlg.setWindowTitle(f"可视化看板 · 14 图（由{board_label}打开）")
        dlg.resize(1100, 820)
        # 「到主表」芯片联动（与主菜单入口保持一致）
        bridge = getattr(main_window, "_apply_board_focus", None) if main_window else None
        if callable(bridge):
            try:
                dlg.focus_requested.connect(bridge)
            except Exception:
                pass
        dlg.exec()
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        QMessageBox.warning(parent, "可视化看板", f"打开失败：{e}")


def apply_board_visual(dialog, main_window, board_label="偏差看板", show_float_btn=False):
    """给一个表格看板对话框套主题 + （可选）挂悬浮「可视化看板」按钮。

    用法（在 __init__ 的 setup_ui()/set_data() 之后加一行）：
        from gui_pyside6.widgets.board_visual import apply_board_visual
        apply_board_visual(self, main_window, board_label="负损看板")

    v43.319：悬浮「可视化看板」按钮默认**不再创建**（show_float_btn=False）。
    原因：点开要走 Chromium + 12 图，首次卡死；且用户有网页版看板，桌面端这入口多余。
    表格美化主题 + 列宽自适应照常生效。需要按钮时显式传 show_float_btn=True。

    返回悬浮按钮对象（未创建时返回 None），便于 offscreen 测试断言。

    v43.300：同时在 ``dialog.table_view`` 上装一个 AdaptiveTable 控制器，并保活为
    ``dialog._board_col_autofit``。列宽自适应由它统一接管（这是 5 个看板 __init__
    末尾唯一的共用落点，各看板无需各自写安装代码）。
    """
    dialog.setObjectName("zppBoardDialog")
    # 合并已有的 dialog 级 stylesheet（若未来有人加过），本主题放最后以生效
    prev = dialog.styleSheet() or ""

    # v43.346：dialog 级 QSS 改为主题感知 + 订阅主题变化。
    # 旧实现只挂一次亮色 BOARD_QSS，切到暗色后看板仍是白底 —— 设计稿诊断 D1。
    from gui_pyside6.themes.tokens import theme_of
    from utils.theme_manager import Thm

    def _apply_board_theme(is_dark, _dlg=dialog, _prev=prev):
        try:
            _dlg.setStyleSheet(_prev + "\n" + build_board_qss(theme_of(is_dark)))
        except RuntimeError:
            pass  # 对话框已销毁

    _apply_board_theme(Thm.is_dark)
    Thm.on_change(_apply_board_theme)
    # 保活引用，避免闭包被 GC（watcher 同样是这个套路）
    dialog._board_theme_applier = _apply_board_theme

    btn = None
    watcher = None
    if show_float_btn:
        btn = QPushButton(FLOAT_BTN_TEXT, dialog)
        btn.setObjectName("zppVisualBtn")
        btn.setToolTip(FLOAT_BTN_TIP)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumWidth(148)   # 独立 child，不进布局，改宽度不影响筛选栏
        try:
            shadow = QGraphicsDropShadowEffect(btn)
            shadow.setBlurRadius(14)
            shadow.setOffset(0, 3)
            shadow.setColor(Qt.GlobalColor.gray)
            btn.setGraphicsEffect(shadow)
        except Exception:
            pass  # 个别平台不支持，按钮本身仍可用
        btn.clicked.connect(
            lambda checked=False: _open_visual_board(dialog, main_window, board_label)
        )

        watcher = _FloatPosWatcher(dialog, btn)
        dialog.installEventFilter(watcher)
        # 保活：watcher/btn 都是 dialog 的 QObject 子对象，这里再显式挂引用，双保险
        dialog._board_visual_watcher = watcher
        dialog._board_visual_btn = btn
        QTimer.singleShot(0, watcher.place)

    # v43.300：统一列宽自适应（5 个看板共用落点）
    try:
        from gui_pyside6.utils.table_autofit import install_adaptive
        view = getattr(dialog, 'table_view', None)
        if view is not None:
            ctrl = install_adaptive(view, mode='content', key=board_label)
            dialog._board_col_autofit = ctrl      # 显式保活
            ctrl.schedule_initial()               # 延迟到下一轮事件循环，避免首帧卡死
    except Exception:
        traceback.print_exc()   # 用户可见链路禁止静默 pass
    return btn
