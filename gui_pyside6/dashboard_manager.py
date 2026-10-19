# -*- coding: utf-8 -*-
"""
Dashboard 管理器 (DashboardManager) - 看板统一管理

负责：所有独立看板的创建、显示、生命周期管理。
将所有看板相关的取数 -> 校验 -> 筛选 -> 裁列 -> 打开窗口流程集中在这里，
让 MainWindow 只保留薄壳转发。

目标：替代或整合 DashboardController，让 MainWindow 更轻量。
"""

import pandas as pd

from PySide6.QtWidgets import QMessageBox

from gui_pyside6.dialogs.alert_dialog import AlertDialog
from gui_pyside6.dialogs.alt_chain_dialog import AltChainDialog
from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog
from gui_pyside6.dialogs.data_stability_dialog import DataStabilityDialog
from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog
from gui_pyside6.dialogs.material_profile_dialog import MaterialProfileDialog, normalize_text
from gui_pyside6.dialogs.neg_loss_dashboard_dialog import NegLossDashboardDialog
from gui_pyside6.dialogs.pos_loss_dashboard_dialog import PosLossDashboardDialog
from gui_pyside6.dialogs.quarantine_review_dialog import QuarantineReviewDialog
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog
from core.alert_monitor import filter_alt_alerts
from core.read_status import get_material_names


class DashboardManager:
    """看板管理器，统一所有看板对话框的打开逻辑。"""

    def __init__(self, mw):
        self.mw = mw
        self._open_dialogs = {}  # 跟踪已打开的对话框，避免重复打开

    def _open_dialog(self, dialog, key):
        """打开对话框，跟踪是否已打开，若已打开则聚焦."""
        # 若对话框已打开且未关闭，则聚焦
        if key in self._open_dialogs and not self._open_dialogs[key].closeEvent:
            self._open_dialogs[key].raise_()
            self._open_dialogs[key].activateWindow()
            return
        dialog.exec()
        self._open_dialogs[key] = dialog

    def show_alert_dashboard(self):
        """打开替代料看板."""
        try:
            df = self.mw._get_master_df()
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            if "偏差率(%)" not in df.columns:
                QMessageBox.information(self, "提示", "当前数据无偏差率列")
                return
            threshold = getattr(self.mw.alert_monitor, 'threshold', 10)
            if "是否替代料" in df.columns:
                alerts_df = filter_alt_alerts(df, threshold)
            else:
                alerts_df = df[df["偏差率(%)"].abs() > threshold]
            if alerts_df.empty:
                QMessageBox.information(self, "提示", "没有替代料预警记录")
                return
            required_cols = [c for c in [
                "工厂", "订单日期", "订单类型", "流程订单", "物料编码", "物料名称", "物料描述",
                "备注", "备注来源", "审核结果",
                "车间", "定额", "实际", "偏差数量", "偏差率(%)",
                "净偏差数量", "净偏差金额", "净偏差率(%)",
                "是否替代料", "_post_audit_changed", "_quarantined",
                "半成品重分类", "_read"
            ] if c in alerts_df.columns]
            alerts_df = alerts_df[required_cols]
            if "_read" in alerts_df.columns:
                alerts_df["状态"] = alerts_df["_read"].map({0: "未读", 1: "已读"})
                alerts_df = alerts_df[["状态"] + [c for c in alerts_df.columns if c != "状态"]]
            dialog = AlertDialog(alerts_df, self.mw)
            self._open_dialog(dialog, "alert")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开替代料看板失败: {e}")

    def show_deviation_warning_dashboard(self):
        """打开偏差率预警看板."""
        try:
            df = self.mw._get_master_df()
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            if "偏差率(%)" not in df.columns:
                QMessageBox.information(self, "提示", "当前数据无偏差率列")
                return
            rates = pd.to_numeric(df["偏差率(%)"], errors='coerce').fillna(0)
            act_col = '数量-实际' if '数量-实际' in df.columns else ('实际' if '实际' in df.columns else None)
            qty_col = '数量-定额' if '数量-定额' in df.columns else ('定额' if '定额' in df.columns else None)
            if act_col and qty_col:
                a = pd.to_numeric(df[act_col], errors='coerce').fillna(0)
                q = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
                no_input = (a.abs() <= 0.001) & (q > 0.001)
                mask = (rates.abs() >= 10) & (~no_input)
            else:
                mask = rates.abs() >= 10
            warnings_df = df[mask].copy()
            warnings_df["原表行号"] = warnings_df.index
            if warnings_df.empty:
                QMessageBox.information(self, "提示", "没有偏差率预警记录（|偏差率| ≥ 10%）")
                return
            candidates = [
                "工厂", "订单日期", "订单类型", "流程订单", "原表行号", "产品物料号码", "产品物料描述",
                "物料编码", "物料名称", "物料描述",
                "备注", "备注来源",
                "车间", "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "净偏差率(%)", "是否替代料",
                "备注原因", "预警", "半成品重分类", "_read", "_quarantined",
            ]
            required_cols = [c for c in candidates if c in warnings_df.columns]
            warnings_df = warnings_df[required_cols]
            if "_read" in warnings_df.columns:
                warnings_df["状态"] = warnings_df["_read"].map({0: "未读", 1: "已读"})
                warnings_df = warnings_df[["状态"] + [c for c in warnings_df.columns if c != "状态"]]
            dialog = DeviationWarningDialog(warnings_df, self.mw)
            self._open_dialog(dialog, "deviation_warning")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开偏差率预警看板失败: {e}")

    def show_neg_loss_dashboard(self):
        """打开负损(含未投料)看板."""
        try:
            df = self.mw._get_master_df()
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            candidates = [
                "订单日期", "订单类型", "流程订单", "物料编码", "物料名称", "物料描述",
                "工厂", "工厂名称",
                "车间", "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
                "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
            ]
            keep = [c for c in candidates if c in df.columns]
            sub = df[keep].copy() if keep else df.copy()
            if "半成品重分类" not in sub.columns:
                sub["半成品重分类"] = ""
            dialog = NegLossDashboardDialog(sub, self.mw)
            self._open_dialog(dialog, "neg_loss")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开负损看板失败: {e}")

    def show_pos_loss_dashboard(self):
        """打开正损(超投)看板."""
        try:
            df = self.mw._get_master_df()
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            candidates = [
                "订单日期", "订单类型", "流程订单", "物料编码", "物料名称", "物料描述",
                "工厂", "工厂名称",
                "车间", "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
                "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
            ]
            keep = [c for c in candidates if c in df.columns]
            sub = df[keep].copy() if keep else df.copy()
            if "半成品重分类" not in sub.columns:
                sub["半成品重分类"] = ""
            dialog = PosLossDashboardDialog(sub, self.mw)
            self._open_dialog(dialog, "pos_loss")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开正损看板失败: {e}")

    def show_data_stability_dashboard(self):
        """打开数据稳定性看板."""
        try:
            name_map = {}
            try:
                name_map.update(get_material_names())
            except Exception:
                pass
            try:
                df = self.mw._get_master_df()
                if (df is not None and '物料编码' in df.columns
                        and '物料名称' in df.columns):
                    for code, nm in zip(df['物料编码'], df['物料名称']):
                        c = normalize_text(code)
                        n = normalize_text(nm)
                        if c and n:
                            name_map[c] = n
            except Exception:
                pass
            dialog = DataStabilityDialog(self.mw, code_name_map=name_map)
            self._open_dialog(dialog, "data_stability")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开数据稳定性看板失败: {e}")

    def show_quarantine_review_dashboard(self):
        """打开隔离区闭环复盘看板."""
        try:
            dialog = QuarantineReviewDialog(self.mw)
            self._open_dialog(dialog, "quarantine_review")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开隔离区闭环看板失败: {e}")

    def show_alt_chain_dashboard(self):
        """打开替代料长链预警看板."""
        try:
            dialog = AltChainDialog(self.mw)
            self._open_dialog(dialog, "alt_chain")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开替代料长链看板失败: {e}")

    def show_material_profile(self, code=None, name=None):
        """打开物料画像窗口."""
        code = normalize_text(code)
        name = normalize_text(name)
        if not code or not name:
            try:
                sel = self.mw.table_view.selectionModel().selectedIndexes()
                rows = {self.mw.proxy_model.mapToSource(ix).row() for ix in sel}
                if rows:
                    r = sorted(rows)[0]
                    row_data = self.mw.source_model.getDataFrame().iloc[r]
                    if not code:
                        code = normalize_text(row_data.get('物料编码', ''))
                    if not name:
                        name = normalize_text(row_data.get('物料名称', ''))
            except Exception:
                pass
        if not code:
            QMessageBox.information(
                self, "提示",
                "请先在主表选中一个物料，再点「🪪 查看物料画像」（或右键该行选择）。")
            return
        try:
            dialog = MaterialProfileDialog(code, self.mw, name=name or '')
            self._open_dialog(dialog, "material_profile")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开物料画像失败: {e}")

    def show_semi_dashboard(self):
        """打开半成品看板."""
        try:
            df = self.mw._get_master_df()
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            code_col = next((c for c in ("物料编码", "组件物料号") if c in df.columns), None)
            if code_col:
                sub = df[df[code_col].astype(str).str.strip().str.startswith(("400", "410"), na=False)]
            else:
                sub = df
            if sub.empty:
                QMessageBox.information(self, "提示", "当前数据无 400/410 开头的物料")
                return
            candidates = [
                "订单日期", "订单类型", "流程订单", "物料编码", "物料名称", "物料描述",
                "车间", "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
                "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
            ]
            keep = [c for c in candidates if c in sub.columns]
            sub = sub[keep].copy() if keep else sub.copy()
            dialog = SemiDashboardDialog(sub, self.mw)
            self._open_dialog(dialog, "semi")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开半成品看板失败: {e}")

    def show_dashboard(self):
        """打开管理看板."""
        try:
            audit_df = self.mw.view_model.df
            if audit_df is None or audit_df.empty:
                QMessageBox.warning(self, "提示", "无数据，请先进行分析")
                return
            dialog = DashboardDialog(audit_df, None, parent=self.mw, main_window=self.mw)
            dialog.focus_requested.connect(self.mw._apply_board_focus)
            self._open_dialog(dialog, "dashboard")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开管理看板失败: {e}")
