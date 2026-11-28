"""PosLossContent - 正损看板内容组件

继承 BaseBoardContent，只覆盖正损看板的核心口径与「偏差数量」分档筛选；
共通筛选 / 表格交互 / 已读与隔离同步 / 导出全部由基类提供（见 base_board_content.py）。
"""

import pandas as pd
from PySide6.QtWidgets import QComboBox
from gui_pyside6.widgets.base_board_content import BaseBoardContent


class PosLossContent(BaseBoardContent):
    """正损(超投)看板：核心口径 = 实际 > 定额 且 定额 > 0"""

    BOARD_KEY = "pos_loss"
    BOARD_TITLE = "正损看板"
    EXPORT_NAME = "正损看板"
    # 正损多一个「偏差数量」分档抽屉项（material 组，位于半成品分类后、颜色标记前），
    # 覆盖 DRAWER_FILTERS 保持原组内顺序；其掩码经 _extra_filter_terms 并入 terms/级联。
    # 注：负损的「含未投料」开关在正损口径下无意义（实际=0 不可能大于定额），已移除。
    DRAWER_FILTERS = (("material", "mtd", "物料类型", "combo_mtd"),
                      ("material", "semi_class", "半成品分类", "grp_semi_class"),
                      ("material", "dev_qty", "偏差数量", "combo_dev_qty"),
                      ("material", "color", "颜色标记", "color_bar"),
                      ("org", "quar", "隔离区", "quar_bar"),
                      ("org", "alt", "替代料", "alt_bar"),
                      ("org", "note", "备注", "note_bar"))

    def _core_mask(self, df):
        """正损掩码：实际 > 定额 且 定额 > 0（超投）。列缺失则全 False。

        q>0 是「超投」的前提：定额为 0 的行属「疑似投错」，不属于本看板口径。
        列名 fallback 沿用负损看板既有写法，勿写死单列，否则上游列名一变就静默失效。
        """
        act_col = next((c for c in ["数量-实际", "实际", "实际数量", "数量 - 实际", "actual"]
                        if c in df.columns), None)
        qty_col = next((c for c in ["数量-定额", "定额", "定额数量", "数量 - 定额", "quota"]
                        if c in df.columns), None)
        if not act_col or not qty_col:
            return pd.Series(False, index=df.index)
        a = pd.to_numeric(df[act_col], errors="coerce")
        q = pd.to_numeric(df[qty_col], errors="coerce")
        return a.notna() & q.notna() & (q > 0) & (a > q)

    def _extra_filter_terms(self, df):
        """偏差数量分档作为独立筛选维度（保留抽屉徽章 + 参与级联排除）。"""
        return {"dev_qty": self._dev_qty_mask(df)}

    def _dev_qty_mask(self, df):
        """偏差数量筛选：大于0 / 等于0 / 小于0。缺列时不约束。"""
        if self._dev_qty_filter == "all":
            return pd.Series(True, index=df.index)
        col = next((c for c in ("偏差数量", "偏差数量(含税)", "数量偏差")
                    if c in df.columns), None)
        if col is None:
            return pd.Series(True, index=df.index)
        vals = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        if self._dev_qty_filter == "gt0":
            return vals > 0.001
        if self._dev_qty_filter == "eq0":
            return vals.abs() <= 0.001
        if self._dev_qty_filter == "lt0":
            return vals < -0.001
        return pd.Series(True, index=df.index)

    # ---- 专属钩子：偏差数量分档 ----
    def _build_core_filter_widgets(self):
        self._dev_qty_filter = "all"
        self.combo_dev_qty = QComboBox()
        self.combo_dev_qty.setMinimumWidth(120)
        self.combo_dev_qty.setMaximumWidth(160)
        self.combo_dev_qty.addItems(["全部", "大于0", "等于0", "小于0"])
        self.combo_dev_qty.currentTextChanged.connect(self._on_dev_qty_changed)

    def _on_dev_qty_changed(self, text):
        mapping = {"全部": "all", "大于0": "gt0", "等于0": "eq0", "小于0": "lt0"}
        self._dev_qty_filter = mapping.get(text, "all")
        self._apply_filter()

    def _reset_core_filters(self):
        self._dev_qty_filter = "all"
        self.combo_dev_qty.setCurrentText("全部")

    def _active_core_filter_keys(self):
        return ["dev_qty"] if self._dev_qty_filter != "all" else []

    def _core_status_tag(self):
        return "超投(实际>定额)"
