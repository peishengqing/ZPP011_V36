"""NegLossContent - 负损看板内容组件

继承 BaseBoardContent，只覆盖负损看板的核心口径与「含未投料」专属开关；
共通筛选 / 表格交互 / 已读与隔离同步 / 导出全部由基类提供（见 base_board_content.py）。
"""

import pandas as pd
from PySide6.QtWidgets import QCheckBox
from gui_pyside6.widgets.base_board_content import BaseBoardContent


class NegLossContent(BaseBoardContent):
    """负损(含未投料)看板：核心口径 = 0<=实际<定额（含未投料可开关）"""

    BOARD_KEY = "neg_loss"
    BOARD_TITLE = "负损看板"
    EXPORT_NAME = "负损含未投料看板"
    # 专属抽屉条目：含未投料开关（numeric 组）
    # 筛选精简（v44.16）：13→6，去抽屉，只留高频核心。被去的长尾筛选
    # （物料类型/半成品分类/单位/车间/工厂/替代料/备注）控件与 mask 暂留
    # （不挂外壳即不显示），确认稳定后再清理死代码。
    BAR_FILTERS = (("keywords", "关键字", "edit_keywords"),
                   ("include_zero", "含未投料", "chk_include_zero"),
                   ("read", "已读", "combo_read"),
                   ("net_dev_qty", "净偏差数量", "_net_dev_qty_container"),
                   ("quar", "隔离区", "quar_bar"))
    DRAWER_FILTERS = ()
    _CORE_DRAWER_FILTERS = ()

    def _core_mask(self, df):
        """负损掩码：含未投料=0<=实际<定额；不含=0<实际<定额。列缺失则全 False。"""
        act_col = next((c for c in ["数量-实际", "实际", "实际数量", "数量 - 实际", "actual"]
                        if c in df.columns), None)
        qty_col = next((c for c in ["数量-定额", "定额", "定额数量", "数量 - 定额", "quota"]
                        if c in df.columns), None)
        if not act_col or not qty_col:
            return pd.Series(False, index=df.index)
        a = pd.to_numeric(df[act_col], errors="coerce")
        q = pd.to_numeric(df[qty_col], errors="coerce")
        if self._include_zero:
            return a.notna() & (a >= 0) & q.notna() & (a < q)
        return a.notna() & (a > 0) & q.notna() & (a < q)

    # ---- 专属钩子：含未投料开关 ----
    def _build_core_filter_widgets(self):
        self._include_zero = False
        self.chk_include_zero = QCheckBox("含未投料")
        self.chk_include_zero.setToolTip(
            "包含未投料：实际=0 的行也视为负损（不影响未投料判定，仅影响负损口径）")
        self.chk_include_zero.setChecked(False)
        self.chk_include_zero.stateChanged.connect(self._on_include_zero_changed)

    def _on_include_zero_changed(self, state):
        self._include_zero = (state != 0)
        self._apply_filter()

    def _reset_core_filters(self):
        self._include_zero = False
        self.chk_include_zero.setChecked(False)

    def _active_core_filter_keys(self):
        return ["include_zero"] if self._include_zero else []

    def _core_status_tag(self):
        return "含未投料" if self._include_zero else "不含未投料"
