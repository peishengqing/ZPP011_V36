# -*- coding: utf-8 -*-
"""行尾悬浮操作道回归测试（v43.351 第五期G2）。

要守住的四件事：
1. 道**不是模型里的列** —— 与 G1 同一条墙：全仓按「模型列号 == DataFrame 列号」取数，
   列数一个都不能动；
2. 道与表格是同一个 ``QFrame#tableShell`` 里的兄弟，每行的上下边界必须跟视口里的
   同一行严格对齐（错位就是把按钮画到别人的行上）；改窗口尺寸、纵向滚动之后仍要对齐；
3. 悬浮行只有 ``RowStyleDelegate`` 一个真源 —— 划过道会让整行亮，且不引入第二套状态、
   不改变选择；
4. 两颗按钮只是既有功能的入口：不新写业务，点了只报视图行号。

无需真实显示：QT_QPA_PLATFORM=offscreen 即可运行。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QItemSelectionModel, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QStandardItem, QStandardItemModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QTableView

from gui_pyside6.themes.tokens import SIZE_PX
from gui_pyside6.widgets.main_table_view import MainTableView
from gui_pyside6.widgets.row_action_lane import AUDIT, MORE, RowActionLane
from gui_pyside6.widgets.row_style_delegate import RowStyleDelegate
from utils.theme_manager import Thm

ROWS, COLS = 12, 6


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _model():
    mdl = QStandardItemModel(ROWS, COLS)
    for r in range(ROWS):
        for c in range(COLS):
            mdl.setItem(r, c, QStandardItem(f"r{r}c{c}"))
    mdl.setHorizontalHeaderLabels([f"列{c}" for c in range(COLS)])
    return mdl


def _build():
    """照 components/main_table.py 的组装方式搭一遍：壳里 [表格 | 道]。"""
    view = MainTableView()
    view.setObjectName("tableView")
    view.setModel(_model())
    view.setItemDelegate(RowStyleDelegate(view))
    view.setSelectionBehavior(QTableView.SelectRows)
    lane = RowActionLane(view)
    shell = QFrame()
    shell.setObjectName("tableShell")
    lay = QHBoxLayout(shell)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lay.addWidget(view, 1)
    lay.addWidget(lane, 0)
    shell.resize(760, 420)
    shell.show()
    QTest.qWait(1)
    return shell, view, lane


def _send(lane, etype, pos, button=Qt.NoButton):
    QApplication.sendEvent(lane, QMouseEvent(
        etype, QPointF(pos), QPointF(lane.mapToGlobal(pos)),
        Qt.LeftButton, button, Qt.NoModifier))


def _click_btn(lane, row, kind):
    btn = dict(lane._btn_rects(lane._row_rect(row)))[kind]
    _send(lane, QEvent.MouseMove, btn.center())
    _send(lane, QEvent.MouseButtonPress, btn.center(), Qt.LeftButton)
    _send(lane, QEvent.MouseButtonRelease, btn.center(), Qt.LeftButton)


def _misaligned(view, lane):
    """道里第 r 行的中心换回视口坐标再问一次行号，不等于 r 的就是错位。"""
    bad = []
    for r in range(ROWS):
        rect = lane._row_rect(r)
        if rect is None:
            continue
        if view.rowAt(rect.center().y() - lane._rows_top()) != r:
            bad.append(r)
    return bad


def test_lane_is_sibling_not_column(qapp):
    """道宽 = 令牌 74，紧贴表格右边，且模型列数一点没动。"""
    shell, view, lane = _build()
    assert lane.width() == SIZE_PX["tableRowActions"] == 74
    assert view.model().columnCount() == COLS
    assert lane.x() == view.x() + view.width()
    assert lane.y() == view.y()
    assert view.width() + lane.width() <= shell.width()
    shell.deleteLater()


def test_rows_stay_aligned_with_viewport(qapp):
    """每一行都跟视口里的同一行对齐 —— 这是把按钮画对地方的前提。"""
    shell, view, lane = _build()
    assert _misaligned(view, lane) == []
    shell.resize(600, 300)
    QTest.qWait(1)
    assert _misaligned(view, lane) == []
    view.verticalScrollBar().setValue(60)
    QTest.qWait(1)
    assert _misaligned(view, lane) == []
    shell.deleteLater()


def test_rows_bottom_is_viewport_bottom(qapp):
    """行的下界取视口底：横向滚动条那一截不属于行，不能把行线画上去。"""
    shell, view, lane = _build()
    vp = view.viewport()
    assert lane._rows_bottom() == view.y() + vp.y() + vp.height() - lane.y()
    shell.deleteLater()


def test_two_22px_buttons_right_aligned(qapp):
    """两颗 22×22、2px 间隙、贴右，都在道内（设计稿 .rowact）。"""
    shell, view, lane = _build()
    rects = lane._btn_rects(lane._row_rect(3))
    assert [k for k, _ in rects] == [AUDIT, MORE]
    for _, btn in rects:
        assert btn.width() == btn.height() == 22
        assert 0 <= btn.left() and btn.right() < lane.width()
    assert rects[1][1].right() > lane.width() - 24
    # QRect.right() 含端点，所以 2px 间隙读作 3
    assert rects[1][1].left() - rects[0][1].right() == 3
    shell.deleteLater()


def test_buttons_emit_view_row_only_when_hit(qapp):
    """压中才发：铅笔报行 5、三点报行 7；没压中按钮不发。"""
    shell, view, lane = _build()
    got = []
    lane.audit_clicked.connect(lambda r: got.append(("audit", r)))
    lane.more_clicked.connect(lambda r: got.append(("more", r)))
    _click_btn(lane, 5, AUDIT)
    _click_btn(lane, 7, MORE)
    assert got == [("audit", 5), ("more", 7)]
    pos = QPoint(2, lane._row_rect(2).center().y())
    before = len(got)
    _send(lane, QEvent.MouseMove, pos)
    _send(lane, QEvent.MouseButtonPress, pos, Qt.LeftButton)
    _send(lane, QEvent.MouseButtonRelease, pos, Qt.LeftButton)
    assert len(got) == before
    shell.deleteLater()


def test_hover_state_has_one_source(qapp):
    """划过道 → 悬浮行记在代理那里（整行一起亮）；离开道 → 归零。"""
    shell, view, lane = _build()
    seen = []
    view.itemDelegate().hover_row_changed.connect(seen.append)
    _send(lane, QEvent.MouseMove,
          lane._btn_rects(lane._row_rect(4))[0][1].center())
    assert lane.hover_row() == 4 == view.itemDelegate().hover_row()
    assert 4 in seen
    lane.leaveEvent(QEvent(QEvent.Leave))
    assert lane.hover_row() == -1
    shell.deleteLater()


def test_hovering_lane_does_not_touch_selection(qapp):
    """露按钮是纯视觉：不选行、不勾行（勾选只属于 G1 那条道）。"""
    shell, view, lane = _build()
    view.selectionModel().clearSelection()
    _send(lane, QEvent.MouseMove,
          lane._btn_rects(lane._row_rect(4))[0][1].center())
    assert not view.selectionModel().hasSelection()
    shell.deleteLater()


def test_row_background_matches_viewport_row(qapp):
    """道底每一行的底色跟视口里同一行同源：选中行用选择底色令牌。"""
    shell, view, lane = _build()
    plain = lane._row_bg(1)
    view.selectionModel().select(
        view.model().index(1, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows)
    assert lane._row_bg(1).name() != plain.name()
    assert lane._row_bg(1).name().lower() == Thm.color("primarySoft").lower()
    shell.deleteLater()


def test_buttons_appear_only_on_the_hovered_row(qapp):
    """像素：划过哪一行，哪一行才多出按钮墨迹；别的行一个像素都不变。

    13px 线性图标全是抗锯齿，落不到纯令牌色上，所以不比颜色，比「画之前/画之后
    变了几个像素」—— 这正是设计稿 opacity:0 → tr:hover:1 要守住的语义。
    """
    shell, view, lane = _build()
    app = QApplication.instance()

    def band(row):
        rect = lane._row_rect(row)
        return rect.adjusted(1, 1, -1, -1)

    def snapshot():
        app.processEvents()
        return lane.grab().toImage()

    lane.leaveEvent(QEvent(QEvent.Leave))
    cold = snapshot()
    _send(lane, QEvent.MouseMove, lane._btn_rects(lane._row_rect(2))[0][1].center())
    hot = snapshot()

    def changed(rect):
        n = 0
        for x in range(rect.left(), rect.right()):
            for y in range(rect.top(), rect.bottom()):
                if cold.pixelColor(x, y) != hot.pixelColor(x, y):
                    n += 1
        return n

    on_row = changed(band(2))
    off_row = changed(band(6))
    assert on_row > 60, "划过的那一行应画出两颗按钮（变了 %d px）" % on_row
    assert off_row == 0, "没划过的行不该有任何变化（变了 %d px）" % off_row
    shell.deleteLater()
