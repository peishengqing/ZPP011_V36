# -*- coding: utf-8 -*-
"""弹窗外壳规范 kit（设计稿 v43.333 第三期 · dialogs.html）。

改造前的三个病（设计稿「现状」章原文）：
  1. 尺寸随机 —— 全项目 30+ 弹窗只有 5 个显式设过尺寸，其余由默认布局撑开，
     同类弹窗大小能差一倍；
  2. 标题三派并存 —— emoji 前缀（⚙ 规则中心 / 🪪 物料画像 / 📈 数据稳定性看板 /
     🔗 替代料长链预警 / 🔁 隔离区闭环复盘）、纯文本带副标（隔离区 - 疑难数据暂存）、
     参数后缀（负损(含未投料)看板 - 彩罐/托盘/手包袋）。emoji 在部分 Windows
     字体下直接渲染成方块；
  3. 同类弹窗结构各异 —— 都是「给人看结论 + 证据」，排布方式却每块都不一样。

本模块把设计稿的规范落成可调用的东西，尺寸档一律读 tokens.DIALOG_SIZES：

- ``apply(dialog, tier, name, subtitle)``  标题规范 + 尺寸档 + 最大化策略
- ``VerdictBanner``  EvidenceShell 的结论条（结论先行）
- ``StepChain``      EvidenceShell 的溯源链（编号步骤）
- ``ImpactBanner``   BatchShell 的影响范围条（不可逆操作前必带）
- ``style_with_tokens(widget, css)``  给普通控件挂只用令牌取色、能跟随亮暗的 QSS

颜色全部来自 TOKENS，不写死 hex（第一期红线）；亮暗切换通过 Thm.on_change 重刷。
"""
from __future__ import annotations

import weakref
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from gui_pyside6.themes.tokens import DIALOG_SIZES, FONT_UI, SIZE_PX, TOKENS
from utils.theme_manager import Thm

#: 尺寸档（设计稿 4.4 弹窗规范速查）
TIER_SMALL = "small"      # 420×520 小表单
TIER_MEDIUM = "medium"    # 720×560 中型表单 / 批量操作
TIER_LARGE = "large"      # 960×640 大型分析
TIER_BOARD = "board"      # 1440×900 看板

#: 设计稿：「内容会超一屏才给最大化」——只有大型分析和看板符合这个条件
MAXIMIZABLE_TIERS = frozenset({TIER_LARGE, TIER_BOARD})

#: 标题栏装饰图标黑名单：设计稿点名 emoji 在部分 Windows 字体下渲染成方块，
#: 而且它们挤掉了真正的信息（名称 + 副标）。只剥开头的装饰符，不动正文。
TITLE_ICONS = "⚙🪪📈🔗🔁📊🔍🧾🗂✅❌⚠🎯📁🔔📝💡⭐🚀🔒📌"
#: 变体选择符：emoji 后面常跟 U+FE0F/U+FE0E 决定用文本还是图形渲染，肉眼不可见
#: 却会占掉标题第一个字符，所以按「装饰符」一起剥掉。
_VARIATION_SELECTORS = "️︎"


def strip_title_icon(title):
    """去掉标题开头的 emoji/装饰符（含紧跟的空白与变体选择符）。"""
    s = str(title or "").strip()
    while s and (s[0] in TITLE_ICONS or s[0] in _VARIATION_SELECTORS):
        s = s[1:].lstrip()
    return s


def format_title(name, subtitle=None):
    """设计稿标题格式：``名称 · 副标``（无 emoji、无括号堆叠）。

    副标为空时只回名称。名称里的 emoji 前缀会被剥掉，所以旧标题字符串可以直接
    丢进来当迁移用，不必先手工洗一遍。
    """
    n = strip_title_icon(name)
    sub = strip_title_icon(subtitle) if subtitle else ""
    return "%s · %s" % (n, sub) if sub else n


def apply(dialog, tier, name, subtitle=None, maximizable=None):
    """给弹窗套上统一外壳规范：标题 + 尺寸档 + 标题栏按钮策略。

    ``maximizable=None`` 时按档位默认（只有 large/board 给最大化）。必须在构造期
    （show 之前）调用：Qt 在窗口已显示后改 windowFlags 会重建窗口并把它隐藏，
    所以这里对已可见的窗口跳过 flags，只保标题和尺寸。
    """
    if tier not in DIALOG_SIZES:
        raise KeyError("未知弹窗尺寸档 %r，可用：%s"
                       % (tier, ", ".join(sorted(DIALOG_SIZES))))
    dialog.setWindowTitle(format_title(name, subtitle))
    w, h = DIALOG_SIZES[tier]
    dialog.resize(w, h)
    allow = (tier in MAXIMIZABLE_TIERS) if maximizable is None else bool(maximizable)
    if dialog.isVisible():
        return
    flags = dialog.windowFlags()
    if allow:
        flags |= Qt.WindowMaximizeButtonHint
    else:
        # 不给最大化也不给最小化：标题栏留一个没有意义的箭头更让人以为能展开
        flags &= ~Qt.WindowMaximizeButtonHint
        flags &= ~Qt.WindowMinimizeButtonHint
    dialog.setWindowFlags(flags)


def _tone(tone):
    """语义色档 → (accent, 底色, 正文, 副文, 边框)。"""
    tk = TOKENS["dark" if Thm.is_dark else "light"]
    if tone not in tk or (tone + "Soft") not in tk:
        raise KeyError("未知语义色档 %r" % (tone,))
    return tk[tone], tk[tone + "Soft"], tk["text"], tk["textMuted"], tk["border"]


class _WeakThemeCb:
    """只持弱引用的主题回调。

    直接把 ``widget._restyle`` 这个绑定方法注册进 Thm，等于让全局单例强引用
    widget —— widget 永远不被回收，destroyed 也永远不触发，每开一次弹窗就漏一只
    控件。弱引用打破了这条持有链：widget 关掉即回收，destroyed 再把自己摘掉。
    """

    def __init__(self, widget):
        self._ref = weakref.ref(widget)

    def __call__(self, _dark=False):
        w = self._ref()
        if w is not None:
            w._restyle()


class _TokenStyleCb:
    """主题回调：只持 widget 弱引用，写一段按令牌名取色的 QSS。

    闭包直接引用 widget 会让 Thm 的回调列表把控件永久留住（每开一次弹窗漏一只），
    所以这里和 _WeakThemeCb 一样走 weakref。
    """

    def __init__(self, widget, css_body):
        self._ref = weakref.ref(widget)
        self._css = css_body

    def __call__(self, _dark=False):
        w = self._ref()
        if w is None:
            return
        tk = TOKENS["dark" if Thm.is_dark else "light"]
        try:
            # 用 string.Template 而不是 str.format：QSS 满是 { }，format 会把
            # 「{ color:...}」当成占位符直接 KeyError（探针里真踩过）。
            w.setStyleSheet(Template(self._css).safe_substitute(**tk))
        except RuntimeError:
            pass  # C++ 对象已销毁，回调随后由 destroyed 摘除


def style_with_tokens(widget, css_body):
    """给现成控件（QLabel/QPushButton…）挂一段只用令牌取色的 QSS，并跟随亮暗切换。

    ``css_body`` 里用 ``$primary``、``$textMuted`` 这类令牌名占位，色号由 TOKENS
    在运行时填 —— 业务代码不写死 hex 是第一期的红线，
    ``tests/unit/test_design_tokens.py`` 门禁 4 会把写死的色号挑出来。
    改造前这些弹窗各自把 ``#10B981 / #6B7280 / #666`` 抄在 setStyleSheet 里，
    暗色下就是一块亮斑。
    """
    cb = _TokenStyleCb(widget, css_body)
    Thm.on_change(cb)
    widget.destroyed.connect(lambda *_: Thm.unregister(cb))
    cb()
    return cb


class _ThemedFrame(QFrame):
    """亮暗切换时重刷自身 QSS 的小基类。

    Thm 的回调列表不随 widget 销毁自动清理，所以注册后必须把 unregister 挂到
    destroyed 上 —— 否则每次主题切换都在遍历一堆已经死掉的 C++ 对象。
    """

    def __init__(self, object_name, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._theme_cb = None

    def _style_body(self):
        raise NotImplementedError

    def _restyle(self, _dark=None):
        # _dark 形参是必需的：Thm.set_dark 回调是 cb(dark) 调用，而它外层
        # try/except pass 会把签名不匹配的 TypeError 静默吞掉 —— 表现就是
        # 「主题切换了但控件颜色不动」，查不到任何报错。
        try:
            self.setStyleSheet("#%s {%s}" % (self.objectName(), self._style_body()))
        except RuntimeError:
            pass  # C++ 对象已销毁，回调随后由 destroyed 摘除

    def _watch_theme(self):
        self._restyle()
        cb = _WeakThemeCb(self)
        Thm.on_change(cb)
        self._theme_cb = cb
        self.destroyed.connect(lambda *_: Thm.unregister(cb))


class VerdictBanner(_ThemedFrame):
    """结论条：设计稿要求 EvidenceShell 第一屏先给一句人话结论，再给依据。"""

    def __init__(self, main_text, sub_text="", tone="info", parent=None):
        super().__init__("dlgVerdict", parent)
        self._tone = tone
        lay = QHBoxLayout(self)
        lay.setContentsMargins(SIZE_PX["cardPad"], 8, SIZE_PX["cardPad"], 8)
        lay.setSpacing(SIZE_PX["gridGap"])
        col = QVBoxLayout()
        col.setSpacing(2)
        self.lbl_main = QLabel(main_text)
        self.lbl_main.setObjectName("verdictMain")
        self.lbl_main.setWordWrap(True)
        col.addWidget(self.lbl_main)
        self.lbl_sub = QLabel(sub_text)
        self.lbl_sub.setObjectName("verdictSub")
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setVisible(bool(sub_text))
        col.addWidget(self.lbl_sub)
        lay.addLayout(col, 1)
        self._watch_theme()

    def set_verdict(self, main_text, sub_text=None, tone=None):
        """结论允许后填：弹窗先建骨架，算完数据再回填。"""
        self.lbl_main.setText(main_text)
        if sub_text is not None:
            self.lbl_sub.setText(sub_text)
            self.lbl_sub.setVisible(bool(sub_text))
        if tone is not None and tone != self._tone:
            self._tone = tone
            self._restyle()

    def _style_body(self):
        accent, soft, text, muted, border = _tone(self._tone)
        return (
            "background:%s; border:1px solid %s; border-left:3px solid %s;"
            " border-radius:%dpx;"
            " QLabel#verdictMain { color:%s; font-family:%s; font-size:%dpt;"
            " font-weight:600; background:transparent; border:none; }"
            " QLabel#verdictSub { color:%s; font-family:%s; font-size:%dpt;"
            " background:transparent; border:none; }"
            % (soft, border, accent, SIZE_PX["radiusMd"],
               text, FONT_UI, 13, muted, FONT_UI, 11)
        )


class ImpactBanner(_ThemedFrame):
    """影响范围条：批量操作前写明「将影响多少行、其中多少会被覆盖」。"""

    def __init__(self, rich_text, parent=None):
        super().__init__("dlgImpact", parent)
        self.lbl = QLabel(rich_text)
        self.lbl.setObjectName("impactText")
        self.lbl.setTextFormat(Qt.RichText)
        self.lbl.setWordWrap(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(SIZE_PX["cardPad"], 8, SIZE_PX["cardPad"], 8)
        lay.addWidget(self.lbl)
        self._watch_theme()

    def set_text(self, rich_text):
        self.lbl.setText(rich_text)

    def _style_body(self):
        accent, soft, text, _muted, border = _tone("warn")
        return (
            "background:%s; border:1px solid %s; border-left:3px solid %s;"
            " border-radius:%dpx;"
            " QLabel#impactText { color:%s; font-family:%s; font-size:%dpt;"
            " background:transparent; border:none; }"
            % (soft, border, accent, SIZE_PX["radiusMd"], text, FONT_UI, 12)
        )


class StepChain(_ThemedFrame):
    """溯源链：编号 + 一行依据，设计稿 EvidenceShell 的证据块形态。"""

    def __init__(self, items=(), parent=None):
        super().__init__("dlgChain", parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(6)
        self._n = 0
        self._watch_theme()
        for text in items:
            self.add_step(text)

    def add_step(self, text):
        self._n += 1
        row = QHBoxLayout()
        row.setSpacing(SIZE_PX["gridGap"])
        dot = QLabel(str(self._n))
        dot.setObjectName("chainStepNo")
        dot.setAlignment(Qt.AlignCenter)
        dot.setFixedWidth(18)
        row.addWidget(dot)
        lbl = QLabel(text)
        lbl.setObjectName("chainStepText")
        lbl.setWordWrap(True)
        row.addWidget(lbl, 1)
        self._lay.addLayout(row)
        return row

    def _style_body(self):
        accent, _soft, text, _muted, _border = _tone("primary")
        return (
            "background:transparent; border:none;"
            " QLabel#chainStepNo { color:%s; font-family:%s; font-size:%dpt;"
            " font-weight:600; }"
            " QLabel#chainStepText { color:%s; font-family:%s; font-size:%dpt; }"
            % (accent, FONT_UI, 12, text, FONT_UI, 12)
        )
