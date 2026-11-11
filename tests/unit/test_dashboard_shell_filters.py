# -*- coding: utf-8 -*-
"""DashboardShell 筛选接线 API（第二期真接入）单元测试。

覆盖看板外壳与内容组件之间的新契约：控件归位（常驻条 / 抽屉三组）、命中徽章、
激活条件数、条件整行收起、操作条按需展开。纯结构约定，不依赖真实业务数据。
"""
import pytest
from PySide6.QtWidgets import QComboBox, QGroupBox, QLabel, QPushButton, QScrollArea

from gui_pyside6.components.dashboard_shell import DashboardShell, pack_row


def _combo(*items):
    c = QComboBox()
    c.addItems(list(items) or ["全部"])
    return c


@pytest.fixture()
def shell(qapp):
    s = DashboardShell()
    yield s
    s.deleteLater()


class TestAddFilter:
    def test_bar_filter_lands_in_filter_bar(self, shell):
        w = _combo("全部", "箱")
        shell.add_filter("unit", "单位", w)
        slot = shell._filters["unit"]
        assert slot.zone == "bar" and slot.widget is w and slot.badge is None
        # 常驻控件插在 stretch 之前，右侧重置/总命中仍然贴右
        assert shell.filter_bar.layout().indexOf(w) < shell.filter_bar.layout().count() - 3
        labels = [l.text() for l in shell.filter_bar.findChildren(QLabel)]
        assert "单位" in labels                       # 标签由外壳一并创建

    def test_bar_capacity_is_five(self, shell):
        assert DashboardShell.MAX_PERSISTENT_FILTERS == 5
        for i in range(5):
            shell.add_filter("k%d" % i, "条件%d" % i, _combo())
        with pytest.raises(ValueError, match="常驻筛选条最多"):
            shell.add_filter("sixth", "第六个", _combo())

    def test_duplicate_key_rejected(self, shell):
        shell.add_filter("unit", "单位", _combo())
        with pytest.raises(ValueError, match="key 重复"):
            shell.add_filter("unit", "单位2", _combo())

    def test_unknown_zone_and_group_rejected(self, shell):
        with pytest.raises(ValueError, match="未知筛选区域"):
            shell.add_filter("a", "甲", _combo(), zone="popup")
        with pytest.raises(ValueError, match="未知抽屉分组"):
            shell.add_filter("b", "乙", _combo(), zone="drawer", group="whatever")

    def test_drawer_filter_gets_hit_badge(self, shell):
        w = _combo()
        shell.add_filter("color", "颜色标记", w, zone="drawer", group="material")
        slot = shell._filters["color"]
        assert slot.zone == "drawer" and slot.badge is not None
        assert slot.badge.text() == "—"

    def test_persistent_bar_has_no_horizontal_scroll(self, shell):
        # 设计稿红线：常驻筛选条永不允许横向滚动（改造前那条拖不完的滚动条就是它）
        shell.add_filter("unit", "单位", _combo())
        shell.add_filter("mtd", "物料类型", _combo(), zone="drawer", group="material")
        assert not shell.filter_bar.findChildren(QScrollArea)


class TestDrawerGroups:
    def test_group_order_follows_semantics_not_insertion(self, shell):
        shell.add_filter("quar", "隔离区", _combo(), zone="drawer", group="org")
        shell.add_filter("zero", "含未投料", _combo(), zone="drawer", group="numeric")
        shell.add_filter("mtd", "物料类型", _combo(), zone="drawer", group="material")
        # 看布局顺序而不是 findChildren 顺序：findChildren 按创建先后返回，测不出插位
        boxes = [shell.drawer_layout.itemAt(i).widget()
                 for i in range(shell.drawer_layout.count())]
        titles = [b.title() for b in boxes if isinstance(b, QGroupBox)]
        assert titles == ["物料维度", "数值维度", "组织与状态维度"], titles

    def test_empty_drawer_creates_nothing(self, shell):
        assert shell._drawer_groups == {}
        assert shell.drawer_container.isHidden() or not shell.drawer_visible


class TestHitReporting:
    def test_total_hits_uses_thousand_separator(self, shell):
        shell.set_total_hits(1234)
        assert shell.lbl_total_hit.text() == "共 1,234 条命中"

    def test_filter_hits_only_touches_badged_slots(self, shell):
        shell.add_filter("unit", "单位", _combo())                       # 常驻：无徽章
        shell.add_filter("mtd", "物料类型", _combo(), zone="drawer", group="material")
        shell.set_filter_hits("unit", 99)          # 不该抛，也不该显示
        shell.set_filter_hits("mtd", 1234)
        shell.set_filter_hits("not_registered", 7)  # 看板口径项（如「负损」）无徽章
        assert shell._filters["unit"].badge is None
        assert shell._filters["mtd"].badge.text() == "1,234 条"

    def test_active_count_shows_on_drawer_button(self, shell):
        shell.set_filter_active(["keywords", "unit", "read"])
        assert shell.btn_filter_drawer.text() == "筛选 (3)"
        shell.set_filter_active([])
        assert shell.btn_filter_drawer.text() == "筛选 (0)"

    def test_drawer_button_text_switches_when_open(self, shell):
        shell.set_filter_active(["unit"])
        shell._on_filter_drawer_toggled()
        assert shell.drawer_visible and shell.btn_filter_drawer.text() == "收起筛选"
        shell._on_filter_drawer_toggled()
        assert not shell.drawer_visible and shell.btn_filter_drawer.text() == "筛选 (1)"


class TestHideAndReset:
    def test_hide_filter_takes_whole_row(self, shell):
        w = _combo()
        shell.add_filter("read", "已读", w, zone="drawer", group="org")
        slot = shell._filters["read"]
        assert not (slot.label.isHidden() or slot.widget.isHidden() or slot.badge.isHidden())
        shell.set_filter_visible("read", False)
        assert slot.label.isHidden() and slot.widget.isHidden() and slot.badge.isHidden()
        shell.set_filter_visible("read", True)
        assert not (slot.label.isHidden() or slot.widget.isHidden() or slot.badge.isHidden())

    def test_set_filter_visible_unknown_key_is_noop(self, shell):
        shell.set_filter_visible("ghost", False)   # 数据缺列时看板会登记未注册的条件

    def test_reset_button_calls_board_callback(self, shell):
        called = []
        shell.set_reset_callback(lambda: called.append(1))
        shell.btn_reset.click()
        assert called == [1]
        shell._reset_cb = None
        shell.btn_reset.click()                      # 没挂回调时不得抛异常


class TestActionBar:
    def test_action_bar_hidden_until_widget_added(self, shell):
        assert shell._action_bar.isHidden()
        shell.set_action_widget(QLabel("操作"))
        assert not shell._action_bar.isHidden()

    def test_add_action_button_keeps_stretch_last(self, shell):
        btn = shell.add_action_button("导出 Excel", lambda: None)
        assert isinstance(btn, QPushButton)
        lay = shell._action_bar_layout
        assert lay.itemAt(lay.count() - 1).spacerItem() is not None


class TestPackRow:
    def test_pack_row_reparents_widgets(self, qapp):
        a, b = QPushButton("全部"), QPushButton("否")
        row = pack_row([a, b])
        assert a.parentWidget() is row and b.parentWidget() is row
        assert row.layout().indexOf(a) == 0 and row.layout().indexOf(b) == 1


class TestBoardContract:
    """三块主看板的筛选声明必须落在外壳上限内（第二期真接入的验收口径）。"""

    @pytest.fixture(params=["neg_loss", "pos_loss", "semi"])
    def board(self, qapp, request):
        from gui_pyside6.widgets.neg_loss_content import NegLossContent
        from gui_pyside6.widgets.pos_loss_content import PosLossContent
        from gui_pyside6.widgets.semi_content import SemiContent
        cls = {"neg_loss": NegLossContent, "pos_loss": PosLossContent,
               "semi": SemiContent}[request.param]
        return cls(object())

    def test_declarations_within_shell_limits(self, board):
        bar_keys = [k for k, _l, _a in board.BAR_FILTERS]
        drawer = [(g, k) for g, k, _l, _a in board.DRAWER_FILTERS]
        assert 0 < len(bar_keys) <= DashboardShell.MAX_PERSISTENT_FILTERS
        assert len(set(bar_keys) | {k for _g, k in drawer}) == len(bar_keys) + len(drawer)
        assert {g for g, _k in drawer} <= set(DashboardShell._GROUP_TITLES)
        # 声明的属性名必须真的在 _build_filter_widgets 里创建出来
        for *_, attr in list(board.BAR_FILTERS) + list(board.DRAWER_FILTERS):
            assert getattr(board, attr, None) is not None, attr

    def test_attach_shell_wires_everything(self, board):
        shell = DashboardShell()
        board.attach_shell(shell)
        assert board.shell is shell
        assert len(shell._filters) == len(board.BAR_FILTERS) + len(board.DRAWER_FILTERS)
        assert shell._reset_cb == board._reset_filters
        for *_, attr in list(board.BAR_FILTERS) + list(board.DRAWER_FILTERS):
            w = getattr(board, attr)
            assert w.parentWidget() is not None, attr
        shell.deleteLater()
