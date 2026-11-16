# -*- coding: utf-8 -*-
"""
unfed_dashboard_dialog.py — 未投料看板

看板职责
------------------------------------
把「整张流程订单一个料都没投」的单子捞出来给人看。这类订单通常产量已报
（虚报产量）、原始备注为空、偏差率恒为 -100%，在主表里完全隐形——既被
「无备注预警」的 ≠100% 规则排除，明细里又没有任何提示，只能靠这张板兜底。

口径与导出「完整偏差明细.未投料订单」列（post_process._add_unfed_flag，
v43.254 落地）**完全同源**：
  某流程订单下**所有组件行**的实际用量都 ≈ 0（|实际| ≤ 0.001 容差）→
  该订单的所有行都算「未投料」。实际为空/非数值的行不算零投料；流程订单
  为空的行不参与判定；部分投料的订单不算未投料。
实测本期 35 单 / 82 行，缺料金额 -332.40 万元、占全期总偏差 56.1%。

筛选区照搬隔离区（QuarantineDialog Tab1）同款：关键字搜索 + 列头取值筛选
（Excel 式勾选浮层）+ 是否备注 + 净偏差数量区间，组件行级展示、双击定位主表。
"""
import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableView, QVBoxLayout,
)

from gui_pyside6.components import dialog_chrome
from gui_pyside6.dialogs.col_filter_ui import (
    make_col_filter_button, make_col_filter_hint_label, set_col_filter_button_on,
)
from gui_pyside6.models.data_frame_model import DataFrameModel
from gui_pyside6.utils.board_empty_hint import set_empty_hint
from gui_pyside6.utils.column_filter import ColumnFilterController
from gui_pyside6.utils.icons import make_button
from gui_pyside6.utils.locate import locate_row
from gui_pyside6.utils.row_number_gutter import enable_row_numbers
from gui_pyside6.utils.table_autofit import install_adaptive, get_adaptive
from gui_pyside6.utils.table_sort import enable_click_sort
from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader
from gui_pyside6.widgets.toast import toast
from utils.theme_manager import Thm

# 「实际用量为 0」的容差：与 post_process「完全未投料订单」/analysis_extra_sheets
# 的 _ZERO_TOL 保持同一口径，否则看板和导出表会给出不同的「未投料」结论。
_ZERO_TOL = 0.001

# 展示列（组件行级，一行一组件；订单信息在行里，可按流程订单/工厂/车间筛）
_DISPLAY_COLS = ['订单日期', '流程订单', '工厂', '车间', '产品物料描述',
                 '物料编码', '物料名称', '单位', '定额', '实际',
                 '净偏差数量', '偏差金额', '备注']
# 内部定位列：供双击定位主表（locate_row 优先 原表行号、其次 data_id），
# 界面隐藏、导出剔除。
_INTERNAL_COLS = ['原表行号', 'data_id']
# DataFrameModel.setDataFrame 会自动注入的已读状态列（挪到最前两列）：
# 对本只读看板无意义，界面隐藏、导出剔除；列头筛选/排序也跳过这两列。
_MODEL_INJECTED = ['_read', '_read_source']


def unfed_order_mask(df):
    """整单未投料掩码：某流程订单下所有组件行的实际用量都≈0 → 该单所有行 True。

    与导出「完整偏差明细.未投料订单」（post_process._add_unfed_flag）同口径：
    - |实际| ≤ 0.001 记为「零投料」行；
    - 实际为空/非数值的行不算零投料（与 post_process 的 isinstance 数值判定一致）；
    - 流程订单为空的行不参与判定、也不会被标；
    - 该订单**所有**行都零投料才算「未投料订单」，部分投料不算。
    返回与 df 等长的 bool Series；df 为空或缺关键列时返回全 False。
    """
    if df is None or df.empty or '流程订单' not in df.columns or '实际' not in df.columns:
        return pd.Series(False, index=df.index if df is not None else None)
    mask = pd.Series(False, index=df.index)
    order = df['流程订单']
    valid = order.notna() & order.astype(str).str.strip().ne('')
    sub = df.loc[valid]
    if sub.empty:
        return mask
    act = pd.to_numeric(sub['实际'], errors='coerce')
    is_zero = act.abs() <= _ZERO_TOL          # NaN → False，与 post_process 一致
    tot = sub.groupby(sub['流程订单']).size()
    zero = is_zero.groupby(sub['流程订单']).sum()
    unfed_orders = tot.index[(zero >= tot) & (tot > 0)]
    if len(unfed_orders):
        mask.loc[sub.index[sub['流程订单'].isin(unfed_orders)]] = True
    return mask


class UnfedDashboardDialog(QDialog):
    """未投料看板：整单零投料的订单组件明细，只读视图 + 隔离区同款筛选。"""

    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        dialog_chrome.apply(self, dialog_chrome.TIER_BOARD, "未投料看板", "整单零投料预警")
        self.main_window = main_window
        self._current_keyword = ""
        self._current_remark_filter = "全部"
        # 防抖定时器：搜索框/区间框每次按键不重建模型（同隔离区 300ms）
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_filters)
        self._build_ui()
        self.set_data(df)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        info = QLabel("「未投料订单」= 整张流程订单的所有组件行实际用量都是 0"
                      "（产量已报、一克未投，偏差率恒 -100%）。"
                      "口径与导出「完整偏差明细.未投料订单」列同源。"
                      "开启「列头筛选」后点任意列头弹取值勾选浮层（Excel 式筛选）；"
                      "Ctrl+点列头仍可排序；双击行定位主表。")
        info.setWordWrap(True)
        layout.addWidget(info)

        # ── 筛选区第 1 行（隔离区同款）：关键字 + 清空 + 列头筛选 + 是否备注 ──
        sl = QHBoxLayout()
        sl.addWidget(QLabel("搜索："))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("输入关键字过滤（订单/物料/车间/工厂…），留空显示全部")
        self.edit_search.textChanged.connect(self._on_search_text_changed)
        sl.addWidget(self.edit_search)
        clear_btn = make_button("✕ 清空")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self.edit_search.clear)
        sl.addWidget(clear_btn)
        self.btn_col_filter = make_col_filter_button(self, self._on_toggle_col_filter)
        sl.addWidget(self.btn_col_filter)
        self._col_filter_hint_label = make_col_filter_hint_label()
        sl.addWidget(self._col_filter_hint_label)
        sl.addSpacing(12)
        sl.addWidget(QLabel("是否备注:"))
        self.combo_remark = QComboBox()
        self.combo_remark.setMinimumWidth(70)
        self.combo_remark.setMaximumWidth(100)
        self.combo_remark.addItems(["全部", "有", "无"])
        self.combo_remark.setCurrentText("全部")
        self.combo_remark.currentTextChanged.connect(self._on_remark_filter_changed)
        sl.addWidget(self.combo_remark)
        layout.addLayout(sl)

        # ── 筛选区第 2 行：净偏差数量区间（留空一端=不限、双端留空=不筛选）──
        nl = QHBoxLayout()
        nl.addWidget(QLabel("净偏差数量区间："))
        self.edit_net_dev_min = QLineEdit()
        self.edit_net_dev_min.setPlaceholderText("不限")
        self.edit_net_dev_min.setFixedWidth(90)
        self.edit_net_dev_min.setValidator(QDoubleValidator(self.edit_net_dev_min))
        self.edit_net_dev_min.setToolTip("净偏差数量下限（留空=不限）")
        nl.addWidget(self.edit_net_dev_min)
        nl.addWidget(QLabel("~"))
        self.edit_net_dev_max = QLineEdit()
        self.edit_net_dev_max.setPlaceholderText("不限")
        self.edit_net_dev_max.setFixedWidth(90)
        self.edit_net_dev_max.setValidator(QDoubleValidator(self.edit_net_dev_max))
        self.edit_net_dev_max.setToolTip("净偏差数量上限（留空=不限）")
        nl.addWidget(self.edit_net_dev_max)
        self.edit_net_dev_min.textChanged.connect(lambda _v: self._search_timer.start())
        self.edit_net_dev_max.textChanged.connect(lambda _v: self._search_timer.start())
        nl.addStretch()
        layout.addLayout(nl)

        # ── 主表格（与隔离区列表同构：DataFrameModel + 列头取值筛选 + 自适应列宽）──
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.doubleClicked.connect(self.on_double_click)
        # 自定义表头：SortBadgeHeader 画 Excel 式取值过滤漏斗标（橙色三角）
        self.header = SortBadgeHeader(Qt.Horizontal, self.table_view)
        self.table_view.setHorizontalHeader(self.header)
        # 点击列头排序（显式连接，规避 Qt6 下 setSortingEnabled 内部连接失效）。
        # 跳过模型注入的 _read/_read_source 两列（第 0/1 列）。
        self._sort_ctrl = enable_click_sort(
            self.table_view, lambda: getattr(self, "source_model", None), skip_cols=(0, 1))
        # Excel 式列头取值筛选控制器：筛选模式→弹层；否则委托排序
        self.col_filter_ctrl = ColumnFilterController(
            self.table_view, self.header, self._sort_ctrl,
            lambda: getattr(self, "source_model", None),
            self._apply_filters, skip_cols=(0, 1))
        self.header.set_sort_columns_getter(lambda: [])
        self.header.set_filtered_columns_getter(lambda: self.col_filter_ctrl.filtered_col_set)
        try:
            self.header.sectionClicked.disconnect(self._sort_ctrl._on_click)
        except Exception:
            pass
        self.header.sectionClicked.connect(self.col_filter_ctrl.on_header_clicked)
        # v43.300：取消末列独吞余量，由自适应控制器接管列宽
        self.table_view.horizontalHeader().setStretchLastSection(False)
        enable_row_numbers(self.table_view)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.col_filter_ctrl.filtered_cols_changed.connect(self._update_col_filter_hint)
        self.col_filter_ctrl.attach_clear_menu(self._col_filter_hint_label)
        layout.addWidget(self.table_view)

        # ── 统计行：订单数（按流程订单去重）+ 车间分布（随筛选联动）──
        stats = QHBoxLayout()
        self.lbl_orders = QLabel("")
        self.lbl_orders.setStyleSheet("color:%s; font-weight:bold;" % Thm.color("text"))
        stats.addWidget(self.lbl_orders)
        self.lbl_ws = QLabel("")
        self.lbl_ws.setWordWrap(True)
        self.lbl_ws.setStyleSheet("color:%s; font-size:12px;" % Thm.color("textMuted"))
        stats.addWidget(self.lbl_ws, 1)
        layout.addLayout(stats)

        # ── 底部：计数 + 导出 + 关闭 ──
        bl = QHBoxLayout()
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color:%s; font-weight:bold;" % Thm.color("text"))
        bl.addWidget(self.lbl_count)
        bl.addStretch()
        export_btn = make_button("📎 导出 Excel")
        export_btn.clicked.connect(self.export_excel)
        bl.addWidget(export_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        bl.addWidget(close_btn)
        layout.addLayout(bl)

    # ------------------------------------------------------------------ 数据
    def set_data(self, df):
        """从主表裁列数据里筛出未投料订单的组件行，作为看板全量数据。"""
        if df is None:
            df = pd.DataFrame()
        self._src_df = df.copy()
        mask = unfed_order_mask(df)
        unfed = df.loc[mask]
        # 展示列在前、内部定位列殿后；缺列优雅降级（保留实际存在的列）
        cols = ([c for c in _DISPLAY_COLS if c in unfed.columns]
                + [c for c in _INTERNAL_COLS if c in unfed.columns])
        self.full_df = unfed[cols].copy() if cols else unfed.copy()
        self._apply_filters()

    def _apply_filters(self):
        """按「关键字 + 是否备注 + 净偏差数量区间」叠加过滤（全部/空 = 不过滤）。"""
        if not hasattr(self, 'full_df') or self.full_df is None:
            return
        df = self.full_df
        # 关键字跨列模糊搜索
        kw = (getattr(self, '_current_keyword', '') or '').strip().lower()
        if kw:
            mask = pd.Series(False, index=df.index)
            for c in df.columns:
                mask |= df[c].astype(str).str.lower().str.contains(kw, na=False)
            df = df.loc[mask]
        # 是否备注筛选（全部/有/无）
        remark = getattr(self, '_current_remark_filter', '全部')
        if remark != '全部':
            rcol = self._remark_col(df)
            if rcol:
                vals = df[rcol].apply(lambda x: "" if pd.isna(x) else str(x).strip())
                df = df[vals != "" if remark == '有' else vals == ""]
        # 净偏差数量区间筛选（该列在主表通常存在；缺列时惰性跳过）
        try:
            col = '净偏差数量'
            if col in df.columns:
                lo = self._parse_net_dev_qty(self.edit_net_dev_min.text())
                hi = self._parse_net_dev_qty(self.edit_net_dev_max.text())
                series = pd.to_numeric(df[col], errors='coerce')
                m = pd.Series(True, index=df.index)
                if lo is not None:
                    m &= (series >= lo)
                if hi is not None:
                    m &= (series <= hi)
                df = df[m]
        except Exception:
            import traceback
            traceback.print_exc()
        self._render_table(df.copy())

    def _render_table(self, df):
        """重建表格模型，叠加 Excel 式列头取值过滤，刷新计数与空态提示。"""
        if df is not None and not df.empty:
            df = df.copy()
        # 叠加 Excel 式列头取值过滤（就地过滤，视图行号不变，选中/双击/导出零回归）
        if hasattr(self, "col_filter_ctrl") and self.col_filter_ctrl.has_any():
            df = self.col_filter_ctrl.mask_dataframe(df)
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.table_view.setModel(self.source_model)
        n_shown = 0 if df is None else len(df)
        n_total = 0 if getattr(self, "full_df", None) is None else len(self.full_df)
        self.lbl_count.setText("共 %d 条 / 筛选命中 %d 条" % (n_total, n_shown))
        # 订单数与车间分布（按流程订单去重；车间分布跟随当前筛选结果）
        n_ord_total, _ = self._order_stats(getattr(self, "full_df", None))
        n_ord, ws_txt = self._order_stats(df)
        self.lbl_orders.setText("订单：共 %d 单 / 命中 %d 单" % (n_ord_total, n_ord))
        self.lbl_ws.setText(("车间分布（命中）：" + ws_txt) if ws_txt else "车间分布（命中）：-")
        set_empty_hint(self.table_view, "" if n_shown else (
            "当前数据没有「整单零投料」的订单。"
            if not n_total else
            "没有符合条件的记录（未投料共 %d 条）\n"
            "请清空搜索框，或把「是否备注」切回「全部」。" % n_total))
        # v43.300：列宽自适应收编到统一控制器
        _ctrl = get_adaptive(self.table_view)
        if _ctrl is None:
            install_adaptive(self.table_view, mode='content', key='unfed')
            get_adaptive(self.table_view).schedule_initial()
        else:
            _ctrl.request_refit(0)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        # 内部定位列 + 模型注入列只藏不删：导出仍要剔除（见 export_excel），界面不占宽
        model_df = self.source_model.getDataFrame()
        for col in _INTERNAL_COLS + _MODEL_INJECTED:
            if col in model_df.columns:
                self.table_view.setColumnHidden(int(model_df.columns.get_loc(col)), True)
        # 重渲染后恢复排序态：用户点过列头则保持；否则默认按流程订单升序
        if hasattr(self, "_sort_ctrl"):
            if self._sort_ctrl.active:
                self._sort_ctrl.reapply()
            else:
                df0 = self.source_model.getDataFrame()
                col = df0.columns.get_loc('流程订单') if '流程订单' in df0.columns else 0
                self._sort_ctrl.apply_default(col, Qt.AscendingOrder)

    # ------------------------------------------------------------------ 筛选辅助
    def _on_search_text_changed(self, text):
        """关键字搜索防抖：避免每次按键都重建模型"""
        self._current_keyword = text
        self._search_timer.stop()
        self._search_timer.start()

    def _on_remark_filter_changed(self, text):
        """是否备注下拉框变化：记住选择并走统一过滤"""
        self._current_remark_filter = text
        self._apply_filters()

    @staticmethod
    def _remark_col(df):
        """找备注列：精确「备注」优先，否则首个列名含「备注」的列"""
        if "备注" in df.columns:
            return "备注"
        for c in df.columns:
            if "备注" in str(c):
                return c
        return None

    @staticmethod
    def _parse_net_dev_qty(text):
        """解析净偏差数量输入框文本 → float 或 None（留空/非法=不限）。"""
        s = str(text or "").strip().replace(",", "")
        if not s:
            return None
        try:
            return float(s)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _order_stats(df):
        """订单数与「工厂·车间」分布（按流程订单去重计数）。

        返回 (订单数, 分布文本)；分布形如「食品厂·一车间 5单、饮料厂·灌装车间 3单」，
        按单数降序。工厂/车间列缺失时降级为只报订单数。流程订单为空的行不计。
        """
        if df is None or df.empty or '流程订单' not in df.columns:
            return 0, ''
        sub = df[df['流程订单'].notna() & df['流程订单'].astype(str).str.strip().ne('')]
        if sub.empty:
            return 0, ''
        n = int(sub['流程订单'].nunique())
        parts = []
        if '车间' in sub.columns:
            if '工厂' in sub.columns:
                grp = sub.groupby([sub['工厂'].astype(str), sub['车间'].astype(str)])['流程订单'].nunique()
                parts = ["%s·%s %d单" % (f, w, c)
                         for (f, w), c in grp.sort_values(ascending=False).items()]
            else:
                grp = sub.groupby(sub['车间'].astype(str))['流程订单'].nunique()
                parts = ["%s %d单" % (w, c) for w, c in grp.sort_values(ascending=False).items()]
        return n, "、".join(parts)

    def _update_col_filter_hint(self):
        """刷新「列头筛选提示」：显示已设取值过滤的列（N 列 / 列名）。"""
        ctrl = self.col_filter_ctrl
        label = self._col_filter_hint_label
        col_set = ctrl.filtered_col_set
        source_model = getattr(self, "source_model", None)
        display_cols = getattr(source_model, "_display_columns", []) if source_model is not None else []
        if not col_set:
            label.setText("列头筛选：0 列")
            return
        names = []
        for c in sorted(col_set):
            if 0 <= c < len(display_cols):
                names.append(str(display_cols[c]))
            else:
                names.append(f"列{c}")
        shown = names[:4]
        more = len(names) - len(shown)
        text = "列头筛选：%d 列（%s" % (len(names), "、".join(shown))
        if more > 0:
            text += " …+%d" % more
        text += "）"
        label.setText(text)

    def _on_toggle_col_filter(self):
        """切换列头筛选模式；关闭模式仅停止弹层，取值过滤仍保留。"""
        on = self.col_filter_ctrl.toggle_mode()
        self.btn_col_filter.setChecked(on)
        set_col_filter_button_on(self.btn_col_filter, on)
        self._update_col_filter_hint()

    # ------------------------------------------------------------------ 交互
    def on_double_click(self, index):
        """双击行 → 定位主表对应记录（按 原表行号/data_id），并关闭看板。"""
        if not index.isValid():
            return
        df = self.source_model.getDataFrame()
        if index.row() >= len(df):
            return
        locate_row(self.main_window, df.iloc[index.row()], parent=self, link_source="未投料看板")
        self.accept()

    def export_excel(self):
        """导出当前筛选后的视图（剔除内部定位列）。"""
        path, _ = QFileDialog.getSaveFileName(self, "导出未投料列表", "未投料订单.xlsx", "Excel files (*.xlsx)")
        if path:
            from gui_pyside6.save_guard import safe_save
            export_df = self.source_model.getDataFrame().drop(
                columns=_INTERNAL_COLS + _MODEL_INJECTED, errors='ignore')
            saved = safe_save(self, path,
                              lambda p: export_df.to_excel(p, index=False),
                              what="未投料列表")
            if saved:
                toast(f"已导出 {len(export_df)} 条记录到 {saved}", parent=self)
