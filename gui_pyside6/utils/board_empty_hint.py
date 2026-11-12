# -*- coding: utf-8 -*-
"""看板空结果提示：表格空着却不写原因，用户只看到一片白，分不清「本期真没数据」
还是「被筛选条件筛没了」。

提示挂在表体 viewport 正中（浮在空网格上，不占布局、不动列宽行高）；文案统一由
`empty_hint_text` 算 —— 默认只看未读的看板筛出 0 行时，要说清「未读 0 条、已读还有
N 条、可切「全部」」，含糊的一句「无数据」等于没说。
"""
from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtWidgets import QLabel

from utils.theme_manager import Thm


def _style():
    """提示的字色跟着主题走（写死色号会被设计令牌门禁拦下）。

    每次显示时重算：主题切换不会专门来刷新这块浮标，但切完总会重新筛一次，
    那时读到的就是新主题的颜色。
    """
    return ("color:%s; font-size:13px; background:transparent;"
            "padding:8px 14px;" % Thm.color("textMuted"))

# 「只看未读」在各看板里的写法不一样（内容组件用中文、老看板用英文），认这一组就行
_UNREAD_MODES = ("未读", "unread")

# 完全没有数据（不是被筛掉的）时的说法，各看板共用
NO_DATA_TEXT = "暂无数据\n请先回到主界面完成分析，再打开看板。"


class _CenterHint(QObject):
    """viewport 尺寸变了就把提示重新铺满、靠 AlignCenter 回到正中。"""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize:
            lbl = getattr(obj, "_board_empty_lbl", None)
            if lbl is not None and lbl.isVisible():
                lbl.setGeometry(0, 0, obj.width(), obj.height())
        return False


def set_empty_hint(view, text):
    """在表格中央显示一行提示；text 为空串就撤掉。view 是任意 QAbstractItemView。"""
    vp = view.viewport()
    lbl = getattr(vp, "_board_empty_lbl", None)
    if lbl is None:
        if not text:
            return
        lbl = QLabel(vp)
        lbl.setObjectName("boardEmptyHint")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        vp._board_empty_lbl = lbl
        filt = _CenterHint(vp)
        # 过滤器对象必须挂在 viewport 上：只当局部变量的话它先被 GC，事件就没人接了
        vp._board_empty_filter = filt
        vp.installEventFilter(filt)
    lbl.setText(text)
    lbl.setVisible(bool(text))
    if text:
        lbl.setStyleSheet(_style())
        lbl.setGeometry(0, 0, vp.width(), vp.height())
        lbl.raise_()


def empty_hint_text(n_shown, df, read_mode):
    """当前筛选下 0 行时写什么；有行返回空串（不显示）。

    df 传**筛选前**的全量（original_df），否则「已读还有 N 条」算不出来。
    """
    if n_shown > 0:
        return ""
    total = 0 if df is None else len(df)
    if total == 0:
        return NO_DATA_TEXT
    if read_mode in _UNREAD_MODES and "_read" in df.columns:
        unread = int((df["_read"] == 0).sum())
        if unread == 0:
            return ("未读 0 条 · 已读 %d 条\n"
                    "看板默认只列未读；要看已读的记录请把「已读/未读」切到「全部」。"
                    % (total - unread))
    return ("没有符合条件的记录（原始 %d 条）\n"
            "可点「重置」清空筛选条件再看。" % total)
