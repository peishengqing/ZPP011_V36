# -*- coding: utf-8 -*-
"""可搜索多选标签控件（设计稿 v43.333 rules.html 的 ``.chips`` 形态）

改造前什么样
------------
``auto_quarantine_rule_dialog`` 把 20 个「单位」平铺成 20 个 QCheckBox 竖排，
「类别」还按规则内容动态再追加复选框 —— 一条规则的条件区就把表单撑到一屏多，
设计稿原话：**「可搜索多选，20 项不再平铺」**。

现在什么样
----------
一行标签（内容多时自动换行）：
  · 已选 → ``primarySoft`` 实底标签，右侧 ✕，点一下取消选择
  · 未选 → 描边标签，右侧 ＋，点一下选中；最多只平铺 ``_INLINE_MAX`` 个
  · 收尾恒有「搜索…」标签 → 弹层（搜索框 + 勾选列表 + 全选 / 清空）

三条硬约束
----------
1. **不丢数据**：规则里已选、但不在候选枚举里的取值（旧配置手填过的类别/单位）
   照样展示与持久化 —— 等价保留旧代码「未知分类也补出复选框」的兜底语义。
2. **配色只用令牌**：QSS 交给 ``dialog_chrome.style_with_tokens``，占位符是令牌名，
   亮暗切换自动跟随；本文件不出现 hex（``tests/unit/test_design_tokens.py`` 门禁 4）。
   圆角/字号走 ``SIZE_PX`` / ``FONT_PT`` 档位，不在控件里就地写数字。
3. **主题回调不持有控件**：``style_with_tokens`` 内部走弱引用，控件销毁时自动摘除。
"""
from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui_pyside6.components import dialog_chrome
from gui_pyside6.themes.tokens import FONT_PT, FONT_UI, SIZE_PX
from gui_pyside6.utils.icons import get_icon
from utils.theme_manager import Thm

#: 未选标签最多平铺几个，超出的只能从弹层里搜（设计稿「20 项不再平铺」的落点）
_INLINE_MAX = 6
_TAG_H = 22             # design-system.css .tag{height:22px}
_TAG_ICON = 10          # 标签里的 ＋/✕ 线性图标边长
_CHIPS_GAP = 5          # design-system.css .chips{gap:5px}
#: 期望行宽 / 最小行宽：对应设计稿 .rule-body 里一条 .frow 能给标签的横向空间
#: （720 档弹窗正文 420 左右）。有了最小宽度，流式排布的最矮高度才不会被
#: Qt 的 heightForWidth 机制算成「每个标签各占一行」。
_PREF_ROW_W = 420
_MIN_ROW_W = 260
_POPUP_GAP = 6          # design-system.css 浮层排布间距
_POPUP_W = 240
_POPUP_H = 340

#: .tag / .tag.on / .chips 的 Qt 对应物。颜色一律是令牌名，运行时由 TOKENS 填。
_TAG_CSS = f"""
QWidget#tagMulti {{ background: transparent; border: none; }}
QWidget#tagMulti QToolButton {{
    background: $surface2;
    border: 1px solid $border;
    border-radius: {SIZE_PX["radiusSm"]}px;
    color: $textMuted;
    font-family: {FONT_UI};
    font-size: {FONT_PT["note"]}px;
    padding: 0 7px;
}}
QWidget#tagMulti QToolButton:hover {{ border-color: $primarySoftBd; color: $primaryHover; }}
QWidget#tagMulti QToolButton[tagRole="on"] {{
    background: $primarySoft;
    border-color: $primarySoftBd;
    color: $primaryHover;
    font-weight: 600;
}}
QWidget#tagMulti QToolButton[tagRole="search"] {{ border-style: dashed; }}
QWidget#tagMulti QLabel#tagMultiEmpty {{ color: $textFaint; font-size: {FONT_PT["note"]}px; }}
"""

_POPUP_CSS = f"""
QWidget#tagMultiPopup {{ background: $surface; border: 1px solid $border; }}
QWidget#tagMultiPopup QLineEdit {{ background: $surface2; color: $text; border: 1px solid $border; }}
QWidget#tagMultiPopup QPushButton {{ background: $surface2; color: $textMuted; }}
QWidget#tagMultiPopup QPushButton:hover {{ background: $primarySoft; color: $primaryHover; }}
QWidget#tagMultiPopup QListWidget {{
    background: $surface;
    border: 1px solid $border;
    color: $text;
    font-family: {FONT_UI};
    font-size: {FONT_PT["note"]}px;
}}
"""


class _ChipFlow(QLayout):
    """标签流式排布 —— design-system.css ``.chips{display:flex;flex-wrap:wrap}`` 的 Qt 对应物。

    为什么不能直接用 QHBoxLayout：它不会换行。实测 20 个单位选 5 个时
    sizeHint 宽 991px，而规则对话框只有 ~620px，标签会被压扁并溢出容器；
    换成 QVBoxLayout 又变成设计稿批评的「平铺撑高表单」。
    高度随宽度变化（hasHeightForWidth），窄处多一行、宽处一行放完。
    """

    def __init__(self, gap=_CHIPS_GAP, parent=None):
        super().__init__(parent)
        self._items = []
        self._gap = gap

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, idx):
        return self._items[idx] if 0 <= idx < len(self._items) else None

    def takeAt(self, idx):
        return self._items.pop(idx) if 0 <= idx < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, max(width, 0), 0), commit=False).height()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, commit=True)

    def sizeHint(self):
        """按设计稿正文行宽给建议尺寸（高度随行宽流式算，避免「一列到底」的虚高）。"""
        if not self._items:
            return QSize(0, 0)
        return QSize(_PREF_ROW_W, self.heightForWidth(_PREF_ROW_W))

    def minimumSize(self):
        if not self._items:
            return QSize(0, 0)
        widest = max(i.sizeHint().width() for i in self._items)
        return QSize(widest, _TAG_H)

    def _arrange(self, rect, commit):
        x, y, row_h = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            w = min(hint.width(), max(rect.width(), 0))
            over_edge = x + w > rect.x() + rect.width()
            if over_edge and x > rect.x():
                x = rect.x()
                y += row_h + self._gap
                row_h = 0
            if commit:
                item.setGeometry(QRect(x, y, w, hint.height()))
            x += w + self._gap
            row_h = max(row_h, hint.height())
        return QRect(rect.x(), rect.y(), rect.width(), y + row_h - rect.y())


class TagMultiSelect(QWidget):
    """候选取值以标签形式展示的可搜索多选控件。

    ``selected()`` 的顺序是「候选枚举顺序 + 额外取值靠后」，与改造前
    「按复选框插入顺序 join」的结果逐字一致，配置无需迁移。
    """

    changed = Signal(list)

    def __init__(self, values=(), parent=None):
        super().__init__(parent)
        self.setObjectName("tagMulti")
        self._values = [str(v).strip() for v in values if str(v).strip()]
        self._selected = []
        self._popup = None
        self.setMinimumWidth(_MIN_ROW_W)
        self._host = _ChipFlow(_CHIPS_GAP, self)
        self._host.setContentsMargins(0, 0, 0, 0)
        dialog_chrome.style_with_tokens(self, _TAG_CSS)
        self._rebuild()

    # ---------------------------------------------------------------- 公开 API
    def setValues(self, values):
        """设置候选取值（顺序即展示顺序）；已选中的额外取值不会被丢掉。"""
        self._values = [str(v).strip() for v in values if str(v).strip()]
        self._normalize_selection()
        self._rebuild()

    def values(self):
        return list(self._values)

    def setSelected(self, values, emit=False):
        """回填选中项（对话框加载规则时用，默认不发 ``changed``）。"""
        self._selected = self._dedupe(values)
        self._normalize_selection()
        if emit:
            self.changed.emit(self.selected())
        self._rebuild()

    def selected(self):
        return list(self._selected)

    def clear(self, emit=True):
        self._selected = []
        self.closePopup()
        if emit:
            self.changed.emit([])
        self._rebuild()

    def closePopup(self):
        popup, self._popup = self._popup, None
        if popup is None:
            return
        try:
            popup.close()
        except RuntimeError:
            return          # C++ 对象已销毁
        popup.setParent(None)
        popup.deleteLater()

    # ---------------------------------------------------------------- 内部
    @staticmethod
    def _dedupe(values):
        out, seen = [], set()
        for v in values or ():
            v = str(v).strip()
            if v and v not in seen:
                seen.add(v)
                out.append(v)
        return out

    def _all_candidates(self):
        """候选枚举 + 已选中的额外取值（旧配置里手填过、不在枚举里的值）。"""
        known = set(self._values)
        return self._values + [v for v in self._selected if v not in known]

    def _normalize_selection(self):
        """把已选列表整理成「候选顺序在前、额外取值靠后」的稳定顺序。"""
        cur = set(self._selected)
        known = [v for v in self._values if v in cur]
        extras = [v for v in self._selected if v not in set(self._values) and v in cur]
        self._selected = known + extras

    def _rebuild(self):
        self._clear_host()
        candidates = self._all_candidates()
        if not candidates:
            empty = QLabel("（无可选取值）")
            empty.setObjectName("tagMultiEmpty")
            self._host.addWidget(empty)
            return

        for v in self._selected:
            self._host.addWidget(
                self._chip(v, "on", "取消选择 %s" % v,
                           lambda _=False, val=v: self._toggle(val, False)))
        sel = set(self._selected)
        hidden = [v for v in candidates if v not in sel]
        for v in hidden[:_INLINE_MAX]:
            self._host.addWidget(
                self._chip(v, "add", "选择 %s" % v,
                           lambda _=False, val=v: self._toggle(val, True)))
        self._host.addWidget(
            self._chip("搜索…", "search",
                       "打开可搜索多选（共 %d 个取值）" % len(candidates),
                       self._open_popup))

    def _clear_host(self):
        while self._host.count():
            item = self._host.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _chip(self, text, role, tip, handler):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setProperty("tagRole", role)
        ink = Thm.color("primaryHover") if role == "on" else Thm.color("textMuted")
        btn.setIcon(get_icon({"on": "close", "add": "plus", "search": "search"}[role],
                             _TAG_ICON, ink))
        btn.setFixedHeight(_TAG_H)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tip)
        btn.clicked.connect(handler)
        return btn

    def _toggle(self, value, want_selected):
        cur = set(self._selected)
        if want_selected == (value in cur):
            return                                   # 没有变化，不发信号
        (cur.add if want_selected else cur.discard)(value)
        self._selected = self._dedupe(
            [v for v in self._values if v in cur]
            + [v for v in self._selected if v not in set(self._values) and v in cur]
            + ([value] if want_selected and value not in set(self._values) else []))
        self._normalize_selection()
        self.changed.emit(self.selected())
        self._rebuild()

    # ---------------------------------------------------------------- 弹层
    def _open_popup(self):
        self.closePopup()
        popup = QWidget(self, Qt.Popup)
        popup.setObjectName("tagMultiPopup")
        # Qt.Popup 默认不吃输入法，不打开这个属性就打不进汉字
        # （同 v43.251 列筛选浮层踩过的坑）。
        popup.setAttribute(Qt.WA_InputMethodEnabled, True)
        popup.setMinimumWidth(_POPUP_W)
        popup.setMaximumHeight(_POPUP_H)
        lay = QVBoxLayout(popup)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(_POPUP_GAP)

        search = QLineEdit()
        search.setPlaceholderText("搜索取值…")
        lay.addWidget(search)

        tools = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_all.setToolTip("把当前**搜索结果**全部选中")
        btn_none = QPushButton("清空")
        tools.addWidget(btn_all)
        tools.addWidget(btn_none)
        tools.addStretch(1)
        lay.addLayout(tools)

        lst = QListWidget()
        items = {}
        sel = set(self._selected)
        for v in self._all_candidates():
            it = QListWidgetItem(v)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if v in sel else Qt.Unchecked)
            lst.addItem(it)
            items[v] = it
        lay.addWidget(lst, 1)

        style_cb = dialog_chrome.style_with_tokens(popup, _POPUP_CSS)
        popup.destroyed.connect(lambda *_: Thm.unregister(style_cb))

        def apply_filter(text):
            needle = text.strip().lower()
            for v, it in items.items():
                lst.setRowHidden(lst.row(it), bool(needle) and needle not in v.lower())

        def select_all():
            for v, it in items.items():
                if not lst.isRowHidden(lst.row(it)):
                    it.setCheckState(Qt.Checked)

        def select_none():
            for it in items.values():
                it.setCheckState(Qt.Unchecked)

        # itemChanged 会对每次勾选触发 → _toggle 幂等（无变化不发信号），批量清空不会重发
        lst.itemChanged.connect(lambda it: self._toggle(it.text(), it.checkState() == Qt.Checked))
        search.textChanged.connect(apply_filter)
        btn_all.clicked.connect(select_all)
        btn_none.clicked.connect(select_none)

        self._popup = popup
        popup.show()
        search.setFocus()
