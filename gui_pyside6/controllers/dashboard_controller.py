# -*- coding: utf-8 -*-
"""
看板/弹窗展示控制器（ARC-003 拆分产物，v43.196）

负责：11 个看板/弹窗的取数 → 校验 → 筛选 → 裁列 → 打开窗口流程。当前覆盖：
替代料看板 / 偏差率预警看板 / 负损看板 / 正损看板 / 数据稳定性看板 /
隔离区复盘看板 / 替代料长链看板 / 物料画像 / 半成品看板 / 半成品明细窗口 / 管理看板。

模式：组合式。持有 MainWindow 引用（self.mw），方法体从 MainWindow 原样搬迁、
逻辑零改动；MainWindow 侧保留同名薄壳转发，故既有绑定不变：
  - components/menu_bar.py:76  alert_action.triggered.connect(self.mw._show_alert_dashboard)
  - components/left_panel.py:316  self.mw._show_semi_detail_window(category)

各方法保留的硬编码列白名单（candidates / required_cols）是刻意不动：它们是各看板
双击定位与 data_id 生成的依据，抽成公共函数反而会掩盖各看板口径差异。
"""

import pandas as pd

from PySide6.QtWidgets import QMessageBox

from gui_pyside6.dialogs.alert_dialog import AlertDialog
from gui_pyside6.dialogs.alt_chain_dialog import AltChainDialog
from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog
from gui_pyside6.dialogs.data_stability_dialog import DataStabilityDialog
from gui_pyside6.dialogs.deviation_warning_dialog import DeviationWarningDialog
from gui_pyside6.dialogs.material_profile_dialog import MaterialProfileDialog
from gui_pyside6.dialogs.neg_loss_dashboard_dialog import NegLossDashboardDialog
from gui_pyside6.dialogs.pos_loss_dashboard_dialog import PosLossDashboardDialog
from gui_pyside6.dialogs.quarantine_review_dialog import QuarantineReviewDialog
from gui_pyside6.dialogs.semi_dashboard_dialog import SemiDashboardDialog
from core.alert_monitor import filter_alt_alerts
from core.read_status import get_material_names
from gui_pyside6.dialogs.material_profile_dialog import normalize_text


class DashboardController:
    """看板/弹窗展示控制器（纯 UI 取数与弹窗编排，不触碰 analyzer 口径层）。"""

    def __init__(self, mw):
        self.mw = mw

    def _show_alert_dashboard(self):
        """手动打开替代料看板"""
        try:
            df = self.mw._get_master_df()  # 与未读弹窗同源，避免两边数对不上
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            if "偏差率(%)" not in df.columns:
                QMessageBox.information(self, "提示", "当前数据无偏差率列")
                return
            # 筛选替代料：有差异 或 偏差率超阈值 都进看板
            threshold = getattr(self.mw.alert_monitor, 'threshold', 10)
            if "是否替代料" in df.columns:
                alerts_df = filter_alt_alerts(df, threshold)
            else:
                alerts_df = df[df["偏差率(%)"].abs() > threshold]
            if alerts_df.empty:
                QMessageBox.information(self, "提示", "没有替代料预警记录")
                return
            # 只保留关键列（含"工厂"以便 dialog 生成正确的 data_id 与主表匹配）
            required_cols = [c for c in [
                "工厂", "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
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
            dialog = AlertDialog(alerts_df, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开替代料看板失败: {e}")


    def _show_deviation_warning_dialog(self):
        """手动打开偏差率预警看板（|偏差率| >= 10%）"""
        try:
            df = self.mw._get_master_df()  # 与未读弹窗同源，避免两边数对不上
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            if "偏差率(%)" not in df.columns:
                QMessageBox.information(self, "提示", "当前数据无偏差率列")
                return
            # 偏差率预警：|偏差率| >= 10%，且排除「实际=0 且 定额>0」的行
            # （偏差率恒为 -100%，是未真实投料的机械结果，不是真偏差；与主表橙色高亮、颜色筛选一致）
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
            # 注入原表行号，供看板双击定位主表使用
            warnings_df["原表行号"] = warnings_df.index
            if warnings_df.empty:
                QMessageBox.information(self, "提示", "没有偏差率预警记录（|偏差率| ≥ 10%）")
                return
            # 只保留关键列（含"工厂"保证 data_id 匹配）
            # 注意：不要同时列「组件物料号」和「物料编码」——sheet5_full 已把组件物料号统一映射为物料编码，
            # 两个来源列并存会让列顺序被打乱（表现为流程订单列显示日期、物料编码列显示流程订单号）。
            candidates = [
                "工厂", "订单日期", "流程订单", "原表行号", "产品物料号码", "产品物料描述",
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
            dialog = DeviationWarningDialog(warnings_df, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开偏差率预警看板失败: {e}")


    def _show_neg_loss_dashboard(self):
        """手动打开负损(含未投料)看板：名称含关键词 且 负损(含未投料)，独立于隔离区。"""
        try:
            df = self.mw._get_master_df()  # 与主表同源，避免两边数对不上
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            # 保留关键列（含数量-实际/数量-定额 供负损计算，备注列供优先展示）
            # 同偏差率预警看板：不列「组件物料号」，统一用「物料编码」，避免两来源列并存打乱列序
            candidates = [
                "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
                # 🔴 工厂筛选必需（v43.176）：v43.169 在负损看板加了「工厂:」下拉，
                # 但白名单里既无「工厂」也无「工厂名称」，真实入口裁列后工厂列被整条丢掉
                # → 看板走「无该列」分支把控件隐藏，表现为「加了工厂筛选却看不见」。
                # 两个都带上：看板优先用可读的「工厂名称」，无则回退「工厂」编码列。
                "工厂", "工厂名称",
                "车间", "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
                "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
            ]
            keep = [c for c in candidates if c in df.columns]
            sub = df[keep].copy() if keep else df.copy()
            # v43.148：若主表列名与看板期望不一致（如「组件物料类型」在、「半成品重分类」不在），
            # 看板会走「无该列」分支。负损看板已支持缺列兜底（物料编码前缀推断），故此处
            # 仅在完全缺列时补一个空列，保证看板能识别到列存在并正常初始化筛选器。
            if "半成品重分类" not in sub.columns:
                sub["半成品重分类"] = ""
            dialog = NegLossDashboardDialog(sub, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开负损看板失败: {e}")


    def _show_pos_loss_dashboard(self):
        """手动打开正损(超投)看板：名称含关键词 且 实际>定额 且 定额>0（v43.178）。

        与负损看板「0<=实际<定额（含未投料）」互补：本看板看的是**超投**那一侧，
        实测 2026-10-10 数据正损子集 614 行（负损 785 / 未投料 131 / 疑似投错 238
        / 持平 397）。判定在 `PosLossDashboardDialog._pos_loss_mask` 内，本方法只负责取数。
        """
        try:
            df = self.mw._get_master_df()  # 与主表同源，避免两边数对不上
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            # 列白名单与负损看板保持一致（正损看板是它的完整复制件），
            # 差别只在对话框内部的口径，故同步维护 v43.176 补的工厂列。
            candidates = [
                "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
                "工厂", "工厂名称",
                "车间", "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
                "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
            ]
            keep = [c for c in candidates if c in df.columns]
            sub = df[keep].copy() if keep else df.copy()
            # 与负损看板同：缺「半成品重分类」时补空列，保证看板识别到列存在
            #（其 `_semi_class_mask` 有 v43.148 三层兜底，不靠该列也筛得出来）
            if "半成品重分类" not in sub.columns:
                sub["半成品重分类"] = ""
            dialog = PosLossDashboardDialog(sub, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开正损看板失败: {e}")


    def _show_data_stability_dashboard(self):
        """v43.181 数据稳定性看板：读 audit.db deviation_history，展示数据反复修改情况。

        v43.185：audit.db 里没有物料名称，故从主表当前数据（_get_master_df，
        与未读计数同源）抽一份「物料编码→物料名称」映射传给看板；主表未加载
        或查不到该物料时，看板名称列留空（不猜测）。
        """
        try:
            # v43.186：先取持久缓存（含历史月份名称），再用当前主表覆盖（当前优先）
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
            dialog = DataStabilityDialog(self, code_name_map=name_map)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开数据稳定性看板失败: {e}")


    def _show_quarantine_review_dashboard(self):
        """v43.181 隔离区闭环复盘：读 audit.db quarantine_records，展示隔离进出闭环。"""
        try:
            dialog = QuarantineReviewDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开隔离区闭环看板失败: {e}")


    def _show_alt_chain_dashboard(self):
        """v43.181 替代料长链预警：读 alt_pairs.json，展示出现在多组的物料。"""
        try:
            dialog = AltChainDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开替代料长链看板失败: {e}")


    def _show_material_profile(self, code=None, name=None):
        """v43.182 物料画像：按物料编码聚合 audit.db 三表，弹卡片式浮层。

        入口 1：主表右键「🪪 查看物料画像」→ 传入该行物料编码（名称也从该行取）。
        入口 2：「📊 看板 ▾」菜单「🪪 物料画像」→ code/name 均空，取主表当前选中行。
        """
        code = normalize_text(code)   # v43.184 修：单元格值可能是 numpy.int64，勿直接 .strip()
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
            dialog = MaterialProfileDialog(code, self, name=name or '')
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开物料画像失败: {e}")


    def _show_semi_dashboard(self):
        """手动打开半成品看板：400/410 开头物料，按半成品重分类 + 投料状态筛选。

        与隔离区/负损看板完全解耦：半成品量大（400/410 约占全表 19%），
        走自动隔离会淹没隔离区，故只做只读查询 + 手动逐条加入隔离区。
        """
        try:
            df = self.mw._get_master_df()
            if df is None or df.empty:
                QMessageBox.information(self, "提示", "暂无数据，请先分析")
                return
            # 先筛 400/410 开头：与半成品重分类的排除法口径一致（analyzer ③ 号规则），
            # 只认物料编码前缀，不依赖描述文字/工厂名
            code_col = next((c for c in ("物料编码", "组件物料号") if c in df.columns), None)
            if code_col:
                sub = df[df[code_col].astype(str).str.strip().str.startswith(("400", "410"), na=False)]
            else:
                sub = df
            if sub.empty:
                QMessageBox.information(self, "提示", "当前数据无 400/410 开头的物料")
                return
            # 列白名单与负损看板一致（含数量-实际/数量-定额 供投料状态计算）
            # 注意：不要同时列「组件物料号」和「物料编码」——两来源列并存会打乱列顺序
            candidates = [
                "订单日期", "流程订单", "物料编码", "物料名称", "物料描述",
                "车间", "组件物料类型", "组件物料类型描述", "单位",
                "数量-定额", "定额", "数量-实际", "实际", "偏差数量", "偏差率(%)",
                "偏差金额", "净偏差数量", "净偏差金额", "是否替代料",
                "备注", "备注原因", "备注来源", "半成品重分类", "data_id", "_read",
            ]
            keep = [c for c in candidates if c in sub.columns]
            sub = sub[keep].copy() if keep else sub.copy()
            dialog = SemiDashboardDialog(sub, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开半成品看板失败: {e}")


    def _show_semi_detail_window(self, category: str):
        """弹出明细窗口显示该分类的物料列表"""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QTableWidget, QTableWidgetItem, QHeaderView
        )

        df = self.mw._get_master_df()
        if df is None or df.empty:
            QMessageBox.warning(self, "提示", "主表暂无数据")
            return
        if '半成品重分类' not in df.columns:
            QMessageBox.warning(self, "提示", "当前数据无半成品重分类列")
            return

        # 筛选该分类的所有物料
        mask = df['半成品重分类'].astype(str) == category
        detail_df = df[mask].copy()
        if detail_df.empty:
            QMessageBox.information(self, "提示", f"{category}：无匹配记录")
            return

        count = len(detail_df)

        # 创建窗口
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{category} — {count} 条物料明细")
        dialog.resize(1000, 500)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)

        # 说明标签
        tip_label = QLabel(f"共 {count} 条物料。双击任意行可定位到主表对应记录。")
        tip_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(tip_label)

        # 表格
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["工厂", "订单日期", "流程订单", "组件物料号", "物料描述"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)

        # 填充数据
        for i, (_, row) in enumerate(detail_df.iterrows()):
            table.setItem(i, 0, QTableWidgetItem(str(row.get('工厂', ''))))
            table.setItem(i, 1, QTableWidgetItem(str(row.get('订单日期', ''))))
            table.setItem(i, 2, QTableWidgetItem(str(row.get('流程订单', ''))))
            table.setItem(i, 3, QTableWidgetItem(str(row.get('组件物料号', ''))))
            table.setItem(i, 4, QTableWidgetItem(str(row.get('组件物料描述', ''))))

        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.resizeSection(0, 80)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.resizeSection(1, 100)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.resizeSection(2, 120)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.resizeSection(3, 120)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)

        # 双击定位到主表
        def _on_double_click(row, col):
            data_id = detail_df.iloc[row].get('data_id')
            if data_id:
                self.mw._locate_row_in_main_table(str(data_id))
            dialog.close()

        table.cellDoubleClicked.connect(_on_double_click)
        layout.addWidget(table)

        # 按钮区
        btn_row = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()


    def _show_dashboard(self):
        audit_df = self.mw.view_model.df
        if audit_df is None or audit_df.empty:
            QMessageBox.warning(self, "提示", "无数据，请先进行分析")
            return
        # material_df 暂无独立来源，传 None（DashboardDialog 内部仅预留）
        dialog = DashboardDialog(audit_df, None, parent=self, main_window=self)
        # 「到主表」芯片桥：看板内点芯片 → 主表联动钻取（降级模式信号不触发）
        dialog.focus_requested.connect(self.mw._apply_board_focus)
        dialog.exec()
