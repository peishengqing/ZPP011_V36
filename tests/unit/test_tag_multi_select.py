# -*- coding: utf-8 -*-
"""可搜索多选标签控件回归测试（v43.352 第四期A）。

要守住的四件事（都对应设计稿 rules.html 对旧表单的批评）：
1. **不再平铺** —— 20 个取值不会长出 20 个复选框，控件里没有 QCheckBox，
   标签数被 ``_INLINE_MAX`` 卡住；
2. **不丢数据** —— 旧配置里手填过、不在候选枚举里的取值照样展示、照样能持久化；
3. **顺序稳定** —— ``selected()`` 输出与改造前「按复选框插入顺序 join」逐字一致，
   配置无需迁移（这条一旦破了，rules.json 会整片重排，diff 没法看）；
4. **只用令牌** —— 替换后的 QSS 里不留未解析的 ``$占位符``，色号全是令牌取值。

无需真实显示：QT_QPA_PLATFORM=offscreen 即可运行。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QLineEdit, QListWidget, QPushButton, QToolButton,
    QVBoxLayout, QWidget,
)

from gui_pyside6.themes.tokens import TOKENS
from gui_pyside6.widgets.tag_multi_select import _INLINE_MAX, TagMultiSelect
from utils.theme_manager import Thm

#: 旧 dialog 里那 20 个平铺单位（``_build_ui`` 的 ``_known_units``），逐字照抄
UNITS = ["个", "箱", "瓶", "罐", "袋", "包", "卷", "米", "kg", "吨",
         "套", "件", "盒", "桶", "只", "对", "支", "根", "张", "片"]
CATS = ["包材", "原辅料", "广宣", "食品半成品", "饮料半成品"]

_TOKEN_HEX = {v.lower() for t in TOKENS.values()
              for v in t.values() if isinstance(v, str) and v.startswith("#")}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _chips(w):
    return [b for b in w.findChildren(QToolButton) if b.parent() is w]


def _roles(w):
    return [b.property("tagRole") for b in _chips(w)]


def _chip(w, text):
    for b in _chips(w):
        if b.text() == text:
            return b
    raise AssertionError("没有标签 %r（现有：%s）" % (text, [b.text() for b in _chips(w)]))


def _spy(w):
    hits = []
    w.changed.connect(lambda vals: hits.append(list(vals)))
    return hits


def _open(qapp, w):
    _chip(w, "搜索…").click()
    assert w._popup is not None, "点「搜索…」没弹层"
    return w._popup


# ------------------------------------------------------------------ 不再平铺
def test_twenty_units_do_not_tile(qapp):
    w = TagMultiSelect(UNITS)
    chips = _chips(w)
    # 平铺时代：20 个复选框；现在：预览 _INLINE_MAX 个 + 1 个搜索入口
    assert len(chips) == _INLINE_MAX + 1
    assert not w.findChildren(QCheckBox), "单位仍被平铺成复选框"
    assert "片" not in [c.text() for c in chips], "超出预览数的取值不该铺开"


def test_selected_units_stay_visible(qapp):
    w = TagMultiSelect(UNITS)
    w.setSelected(["片", "个", "吨"])
    texts = [c.text() for c in _chips(w)]
    # 已选标签排在最前，且内部按候选枚举顺序（个 < 吨 < 片）
    assert texts[:3] == ["个", "吨", "片"]
    assert _roles(w)[:3] == ["on", "on", "on"]
    assert texts[-1] == "搜索…"


def test_chips_wrap_instead_of_overflowing(qapp):
    """``.chips{flex-wrap:wrap}``：窄处必须换行、不能溢出容器，宽处收回一行。

    QHBoxLayout 做不到（实测 20 单位选 5 个 sizeHint 宽 991px，对话框只有 620px），
    这条断言就是那个流式排布存在的理由。
    """
    host = QWidget()
    QVBoxLayout(host).addWidget(TagMultiSelect(UNITS))
    w = host.findChild(TagMultiSelect)
    w.setSelected(["个", "箱", "瓶", "罐", "袋"])
    host.resize(300, 200)
    host.show()
    qapp.processEvents()
    chips = _chips(w)
    assert len({c.y() for c in chips}) >= 2, "标签必须换行而不是压扁"
    assert all(c.x() + c.width() <= w.width() + 1 for c in chips), "标签溢出容器宽度"

    host.resize(1400, 200)
    qapp.processEvents()
    assert len({c.y() for c in _chips(w)}) == 1, "宽度够了就该收回一行"
    host.close()


def test_chip_height_matches_mockup(qapp):
    w = TagMultiSelect(CATS)
    for c in _chips(w):
        assert c.property("tagRole") in ("on", "add", "search")
        assert c.minimumHeight() == c.maximumHeight() == 22   # .tag{height:22px}


def test_widget_css_uses_only_token_colors(qapp):
    w = TagMultiSelect(CATS)
    for token in re.findall(r"#[0-9A-Fa-f]{6}", w.styleSheet()):
        assert token.lower() in _TOKEN_HEX, "标签样式出现表外色号 %s" % token


def test_every_placeholder_resolved(qapp):
    """QSS 里留着未解析的 ``$xxx``，说明用了 TOKENS 之外的键名（属性会被静默丢弃）。"""
    w = TagMultiSelect(CATS)
    assert "$" not in w.styleSheet()


# ------------------------------------------------------------------ 交互
def test_click_selected_chip_deselects(qapp):
    w = TagMultiSelect(CATS)
    w.setSelected(["包材"])
    hits = _spy(w)
    _chip(w, "包材").click()
    assert w.selected() == []
    assert hits == [[]]


def test_click_add_chip_selects(qapp):
    w = TagMultiSelect(CATS)
    hits = _spy(w)
    _chip(w, "原辅料").click()
    assert w.selected() == ["原辅料"]
    assert hits == [["原辅料"]]
    assert _chip(w, "原辅料").property("tagRole") == "on"


def test_no_change_emits_no_signal(qapp):
    w = TagMultiSelect(CATS)
    w.setSelected(["广宣"])
    hits = _spy(w)
    w._toggle("食品半成品", False)      # 本来就没选中 → 幂等
    assert hits == []


# ------------------------------------------------------------------ 顺序稳定
def test_selected_order_follows_candidate_enumeration(qapp):
    """回填乱序 → 读出仍按候选枚举顺序，与旧「复选框插入顺序 join」逐字一致。"""
    w = TagMultiSelect(CATS)
    w.setSelected(["饮料半成品", "包材", "广宣"])
    assert w.selected() == ["包材", "广宣", "饮料半成品"]


def test_unknown_selected_value_survives(qapp):
    """旧配置里手填过的取值不在枚举里，也不能被吞掉（旧代码为此专门补复选框）。"""
    w = TagMultiSelect(CATS)
    w.setSelected(["包材", "定制彩箱"])
    assert w.selected() == ["包材", "定制彩箱"]
    assert _chip(w, "定制彩箱").property("tagRole") == "on"
    w.setValues(CATS + ["礼盒"])        # 刷新候选枚举
    assert "定制彩箱" in w.selected(), "刷新候选集把老取值弄丢了"
    w.setValues([])                     # 候选全空也不该丢已选
    assert w.selected() == ["包材", "定制彩箱"]


# ------------------------------------------------------------------ 弹层
def test_popup_lists_all_candidates_with_search(qapp):
    w = TagMultiSelect(UNITS)
    popup = _open(qapp, w)
    lst = popup.findChild(QListWidget)
    assert lst is not None and lst.count() == len(UNITS), "20 项要在弹层里齐全"
    search = popup.findChild(QLineEdit)
    assert search is not None and search.placeholderText() == "搜索取值…"
    search.setText("kg")
    shown = [lst.item(i).text() for i in range(lst.count()) if not lst.isRowHidden(i)]
    assert shown == ["kg"]


def test_popup_select_all_and_clear(qapp):
    w = TagMultiSelect(UNITS)
    popup = _open(qapp, w)
    lst = popup.findChild(QListWidget)
    btns = {b.text(): b for b in popup.findChildren(QPushButton)}
    assert set(btns) >= {"全选", "清空"}
    btns["全选"].click()
    assert w.selected() == UNITS
    btns["清空"].click()
    assert w.selected() == []
    assert not [i for i in range(lst.count())
                if lst.item(i).checkState() == Qt.Checked]


def test_popup_respects_existing_selection(qapp):
    w = TagMultiSelect(UNITS)
    w.setSelected(["片", "箱"])
    lst = _open(qapp, w).findChild(QListWidget)
    checked = [lst.item(i).text() for i in range(lst.count())
               if lst.item(i).checkState() == Qt.Checked]
    assert checked == ["箱", "片"]      # 弹层里同样按候选枚举顺序


def test_popup_check_propagates_to_chips(qapp):
    w = TagMultiSelect(UNITS)
    hits = _spy(w)
    lst = _open(qapp, w).findChild(QListWidget)
    for i in range(lst.count()):
        if lst.item(i).text() == "卷":
            lst.item(i).setCheckState(Qt.Checked)
    assert w.selected() == ["卷"]
    assert _chip(w, "卷").property("tagRole") == "on"
    assert hits == [["卷"]]


def test_reopen_popup_does_not_accumulate(qapp):
    w = TagMultiSelect(UNITS)
    for _ in range(3):
        _open(qapp, w)
        w._open_popup()
    assert len(w.findChildren(QLineEdit)) == 1, "旧弹层没回收，每开一次漏一只"


# ------------------------------------------------------------------ 主题
def test_theme_switch_recolors(qapp):
    w = TagMultiSelect(CATS)
    light = TOKENS["light"]["primarySoft"]
    dark = TOKENS["dark"]["primarySoft"]
    was_dark = Thm.is_dark
    try:
        Thm.set_dark(True)
        assert dark in w.styleSheet() and light not in w.styleSheet()
    finally:
        Thm.set_dark(was_dark)
    if not was_dark:
        assert light in w.styleSheet() and dark not in w.styleSheet()
