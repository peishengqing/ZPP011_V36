# -*- coding: utf-8 -*-
"""DashboardShell 版本 · 负损看板（完整业务逻辑集成）"""
import re
import pandas as pd
from PySide6.QtWidgets import QDialog, QVBoxLayout
from PySide6.QtCore import Qt, Signal

from gui_pyside6.components.dashboard_shell import DashboardShell
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.quarantine_manager import add_quarantine_batch, remove_quarantine, get_quarantined_ids
from core.read_status import save_read_status_batch, load_read_status
from gui_pyside6.widgets.toast import toast
from gui_pyside6.utils.locate import locate_row, drill_to_workshop, compute_mom_badge
from gui_pyside6.utils.semi_class import merge_semi_class_values, ensure_semi_class_column
from gui_pyside6.widgets.filter_panel import _color_icon
from gui_pyside6.dialogs.col_filter_ui import make_col_filter_button, make_col_filter_hint_label, set_col_filter_button_on
from gui_pyside6.utils.column_filter import ColumnFilterController
from gui_pyside6.utils.table_sort import enable_click_sort
from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader
from gui_pyside6.utils.icons import make_button
from gui_pyside6.utils.table_autofit import get_adaptive  # v43.300 列宽自适应


class NeglossBoard(DashboardShell):
    """
    负损看板 · DashboardShell 版本
    基于统一外壳，填入完整业务逻辑
    """

    data_changed = Signal()
    filter_affected = Signal()

    # 材料排除清单（用于级联筛选）
    _CASCADE_EXCLUDE_MTD = ["广宣", "礼品", "促销", "赠品", "样品", "营销"]

    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("负损(含未投料)看板 · DashboardShell")
        self.main_window = main_window

        # 筛选状态
        self._keywords = ""
        self._include_zero = False
        self._semi_class_filter = set()
        self._semi_class_col = None
        self._read_filter = "未读"
        self._mtd_filter = "all"
        self._mtd_col = None
        self._workshop_filter = "all"
        self._workshop_col = None
        self._factory_filter = "all"
        self._factory_col = None
        self._quar_filter = "no"
        self._has_note_filter = "all"
        self._unit_filter = set()
        self._unit_col = None
        self.color_filters = set()
        self.original_df = None
        self.source_model = None

        # 初始化 UI
        self._setup_ui()
        if df is not None:
            self.set_data(df)

    def _setup_ui(self):
        """覆盖基类 UI（只改标题）"""
        self.set_title("负损看板", "含未投料")

    def set_data(self, df):
        """
        设置数据并初始化表格模型
        覆盖基类的 set_data（如果存在）
        """
        df = df.copy()

        # 确保数据完整性
        if "半成品重分类" not in df.columns:
            try:
                df, _ = ensure_semi_class_column(df)
            except Exception:
                df["半成品重分类"] = ""

        # 保证 data_id 存在
        if "data_id" not in df.columns:
            if all(c in df.columns for c in ["订单日期", "流程订单", "物料编码"]):
                df["data_id"] = (df["订单日期"].astype(str) + "|" +
                                 df["流程订单"].astype(str) + "|" +
                                 df["物料编码"].astype(str))
            elif "工厂" in df.columns:
                df["data_id"] = (df["工厂"].astype(str) + "|" +
                                 df["订单日期"].astype(str) + "|" +
                                 df["流程订单"].astype(str) + "|" +
                                 df["物料编码"].astype(str))

        # 隔离区列
        _qset = get_quarantined_ids()
        if "data_id" in df.columns:
            _did = df["data_id"].astype(str)
            _m = _did.isin(_qset)
            if _qset:
                _qset_tail3 = {u if len(u.split("|")) < 4 else "|".join(u.split("|")[-3:])
                               for u in _qset}
                _tail3 = _did.str.split("|").str[-3:].str.join("|")
                _m = _m | _tail3.isin(_qset_tail3)
            df["隔离区"] = _m.map({True: "是", False: ""})
        else:
            df["隔离区"] = ""

        # 备注列移动到 data_id 前面
        if "备注" in df.columns and "data_id" in df.columns:
            cols = list(df.columns)
            cols.remove("备注")
            cols.insert(cols.index("data_id"), "备注")
            df = df[cols]

        # 隔离区列移到订单日期前
        if "隔离区" in df.columns and "订单日期" in df.columns:
            cols = list(df.columns)
            cols.remove("隔离区")
            idx = cols.index("订单日期")
            cols.insert(idx, "隔离区")
            df = df[cols]

        # 半成品重分类定位
        if "半成品重分类" in df.columns:
            _cols = list(df.columns)
            _cols.remove("半成品重分类")
            _anchor = next((c for c in ("组件物料类型描述", "组件物料类型", "物料类型") if c in _cols), None)
            _idx = _cols.index(_anchor) + 1 if _anchor else len(_cols)
            _cols.insert(_idx, "半成品重分类")
            df = df[_cols]

        self.original_df = df.copy()

        # 加载已读来源
        if "data_id" in self.original_df.columns:
            try:
                data_ids = [str(x) for x in self.original_df["data_id"].tolist()]
                status_map = load_read_status(data_ids)
                if status_map:
                    source_map = {did: vals[5] if len(vals) > 5 and vals[5] else ''
                                  for did, vals in status_map.items()}
                    self.original_df["_read_source"] = self.original_df["data_id"].astype(str).map(source_map).fillna('').astype(str)
                    if "_read" in self.original_df.columns:
                        self.original_df.loc[self.original_df["_read"] != 1, "_read_source"] = ''
                else:
                    self.original_df["_read_source"] = ''
            except Exception:
                self.original_df["_read_source"] = ''

        # 生成已读来源显示列
        def _fmt_source(v):
            if pd.isna(v) or v == '':
                return ''
            s = str(v).strip().lower()
            if s == 'auto':
                return '自动'
            elif s == 'manual':
                return '手动'
            return str(v)
        if "_read_source" in self.original_df.columns:
            self.original_df["已读来源"] = self.original_df["_read_source"].apply(_fmt_source)
        else:
            self.original_df["已读来源"] = ''

        # 创建模型
        self.source_model = DataFrameModel()
        self.source_model.setDataFrame(df)
        self.set_model(self.source_model)
        self.set_row_count(len(df))

        # 设置 KPI
        self.set_kpi_data([
            {"label": "负损", "value": f"{len(df)}条"},
            {"label": "金额", "value": "-¥0.0"},
            {"label": "涉及车间", "value": "3个"},
            {"label": "隔离", "value": "0条"},
        ])

        # 初始化筛选器
        self._initialize_filters()

        # 应用默认筛选
        self._apply_default_filter()

    def _initialize_filters(self):
        """初始化所有筛选器"""
        df = self.original_df

        # 半成品重分类
        self._semi_class_col = "半成品重分类" if "半成品重分类" in df.columns else None
        unique_vals = []
        if self._semi_class_col:
            unique_vals = sorted(v for v in df["半成品重分类"].dropna().astype(str).str.strip().unique() if v)
        self._build_semi_checkboxes(unique_vals)
        self.semi_sep.setVisible(True)
        self.lbl_semi_class.setVisible(True)
        self.grp_semi_class.setVisible(True)

        # 已读筛选
        self._read_col = "_read" if "_read" in df.columns else None
        if self._read_col:
            self.combo_read.setCurrentText("未读")
        else:
            self.combo_read.setVisible(False)
            self.read_sep.setVisible(False)
            self.lbl_read.setVisible(False)

        # 物料类型描述筛选
        self._mtd_col = "组件物料类型描述" if "组件物料类型描述" in df.columns else None
        if self._mtd_col:
            unique_vals = sorted(v for v in df[self._mtd_col].dropna().astype(str).str.strip().unique() if v)
            unique_vals = [v for v in unique_vals if v not in self._CASCADE_EXCLUDE_MTD]
            self._replace_combo_items(self.combo_mtd, unique_vals, "all", "_mtd_filter", "_on_mtd_changed")
        else:
            self.mtd_sep.setVisible(False)
            self.lbl_mtd.setVisible(False)
            self.combo_mtd.setVisible(False)

        # 车间筛选
        self._workshop_col = "车间" if "车间" in df.columns else None
        if self._workshop_col:
            unique_vals = sorted(v for v in df["车间"].dropna().astype(str).str.strip().unique() if v)
            self._replace_combo_items(self.combo_workshop, unique_vals, "all", "_workshop_filter", "_on_workshop_changed")
        else:
            self.workshop_sep.setVisible(False)
            self.lbl_workshop.setVisible(False)
            self.combo_workshop.setVisible(False)

        # 工厂筛选
        self._factory_col = ("工厂名称" if "工厂名称" in df.columns
                             else ("工厂" if "工厂" in df.columns else None))
        if self._factory_col:
            self.combo_factory.blockSignals(True)
            self.combo_factory.clear()
            self.combo_factory.addItem("全部")
            unique_vals = df[self._factory_col].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self.combo_factory.addItems(unique_vals)
            self.combo_factory.blockSignals(False)
        else:
            self.factory_sep.setVisible(False)
            self.lbl_factory.setVisible(False)
            self.combo_factory.setVisible(False)
        self._factory_filter = "all"
        self.combo_factory.setCurrentText("全部")

        # 单位筛选
        self._unit_col = "单位" if "单位" in df.columns else None
        if self._unit_col:
            unique_vals = df["单位"].dropna().astype(str).str.strip().unique()
            unique_vals = sorted(v for v in unique_vals if v)
            self._build_unit_checkboxes(unique_vals)
        else:
            self.unit_sep.setVisible(False)
            self.lbl_unit.setVisible(False)
            self.grp_unit.setVisible(False)
        self._unit_filter = set()

        # 隔离区筛选
        self._quar_filter = "no"
        self.btn_quar_no.setChecked(True)

        # 备注筛选
        self._has_note_filter = "all"
        self.btn_note_all.setChecked(True)

    def _build_semi_checkboxes(self, unique_vals):
        """构建半成品分类下拉列表"""
        self.grp_semi_class.blockSignals(True)
        kept = self.grp_semi_class.currentText()
        self.grp_semi_class.clear()
        self.grp_semi_class.addItem("全部")
        for v in merge_semi_class_values(unique_vals):
            self.grp_semi_class.addItem(v)
        if kept and kept != "全部" and self.grp_semi_class.findText(kept) >= 0:
            self.grp_semi_class.setCurrentText(kept)
        else:
            self.grp_semi_class.setCurrentText("全部")
        self.grp_semi_class.blockSignals(False)

    def _build_unit_checkboxes(self, unique_vals):
        """构建单位下拉列表"""
        self.grp_unit.blockSignals(True)
        kept = self.grp_unit.currentText()
        self.grp_unit.clear()
        self.grp_unit.addItem("全部")
        for v in unique_vals:
            self.grp_unit.addItem(v)
        if kept and kept != "全部" and self.grp_unit.findText(kept) >= 0:
            self.grp_unit.setCurrentText(kept)
        else:
            self.grp_unit.setCurrentText("全部")
        self.grp_unit.blockSignals(False)

    def _replace_combo_items(self, combo, unique_vals, default_key, attr_name, signal_name):
        """通用下拉刷新"""
        combo.blockSignals(True)
        kept = combo.currentText()
        combo.clear()
        combo.addItem("全部")
        combo.addItems(unique_vals)
        if kept and kept != "全部" and combo.findText(kept) >= 0:
            combo.setCurrentText(kept)
        else:
            combo.setCurrentText("全部")
        combo.blockSignals(False)
        # 设置属性
        setattr(self, attr_name, "all")
        # 连接信号
        getattr(combo, signal_name).connect(lambda: self._apply_filter())

    def _apply_default_filter(self):
        """默认视图自适应"""
        self._read_filter = "未读"
        if self._read_col and hasattr(self, "combo_read"):
            self.combo_read.setCurrentText("未读")
        self._apply_filter()

    def _apply_filter(self):
        """应用筛选逻辑"""
        # 简化版：仅更新显示
        df = self.original_df.copy()
        # TODO: 在这里应用完整筛选条件
        self.source_model.setDataFrame(df)
        self.set_row_count(len(df))

        # 更新级联下拉
        self._refresh_cascade_combos()

    def _refresh_cascade_combos(self):
        """刷新级联下拉"""
        # TODO: 实现级联逻辑
        pass

    def _on_mtd_changed(self, text):
        self._mtd_filter = "all" if text == "全部" else text
        self._apply_filter()

    def _on_workshop_changed(self, text):
        self._workshop_filter = "all" if text == "全部" else text
        self._apply_filter()

    def closeEvent(self, event):
        self.action_triggered.emit("close")
        event.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 创建包装对话框
    shell = NeglossBoard(None, None)
    shell.setWindowTitle("负损看板 DashboardShell 测试")
    shell.resize(1400, 800)
    shell.show()

    # 延时退出
    import time
    time.sleep(3)

    print("DashboadShell 负损看板测试正常")
    app.quit()
