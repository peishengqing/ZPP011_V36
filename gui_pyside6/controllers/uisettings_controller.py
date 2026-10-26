# -*- coding: utf-8 -*-
"""
UI 设置控制器
负责：统计卡片更新、进度/状态标签管理、视图可见性控制
"""

import pandas as pd
import time
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QLabel, QProgressBar


class UISettingsController(QObject):
    """UI 状态更新控制器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

    # ------------------- 统计卡片更新 -------------------
    def update_summary(self):
        """从主窗口获取数据更新统计标签"""
        if not hasattr(self.main_window, 'view_model') or self.main_window.view_model.df is None:
            return

        df = self.main_window.view_model.df
        if df.empty:
            self.main_window.summary_quota.setText("配额: 0.00")
            self.main_window.summary_actual.setText("实际: 0.00")
            self.main_window.summary_amount.setText("偏差率: 0.00%")
            self.main_window.summary_qty.setText("偏差量: 0.00")
            return

        # 配额列
        quota_col = next((c for c in ["配额", "定额", "数量-定额", "quota"] if c in df.columns), None)
        actual_col = next((c for c in ["实际", "数量-实际", "actual"] if c in df.columns), None)
        rate_col = next((c for c in ["偏差率(%)", "偏差率"] if c in df.columns), None)
        qty_col = next((c for c in ["偏差数量", "数量偏差", "dev_qty"] if c in df.columns), None)
        net_rate_col = next((c for c in ["净偏差率(%)", "净偏差率"] if c in df.columns), None)

        quota_sum = df[quota_col].fillna(0).sum() if quota_col else 0
        actual_sum = df[actual_col].fillna(0).sum() if actual_col else 0

        # 偏差率平均值
        if rate_col:
            rates = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
            avg_rate = rates.mean()
            rate_str = f"{avg_rate:.2f}%"
        else:
            if actual_col and quota_col:
                avg_rate = ((df[actual_col].fillna(0) - df[quota_col].fillna(0)) / df[quota_col].fillna(0).replace(0, float('nan'))).mean()
                rate_str = f"{avg_rate:.2f}%"
            else:
                rate_str = "0.00%"
                avg_rate = 0

        # 净偏差率平均值
        if net_rate_col:
            net_rates = pd.to_numeric(df[net_rate_col], errors='coerce').fillna(0)
            net_rate_str = f"{net_rates.mean():.2f}%"
        else:
            net_rate_str = ""

        # 偏差量汇总
        if qty_col:
            qty_sum = df[qty_col].fillna(0).sum()
        elif actual_col and quota_col:
            qty_sum = (df[actual_col].fillna(0) - df[quota_col].fillna(0)).sum()
        else:
            qty_sum = 0

        self.main_window.summary_quota.setText(f"配额: {quota_sum:,.2f}")
        self.main_window.summary_actual.setText(f"实际: {actual_sum:,.2f}")
        if net_rate_str:
            self.main_window.summary_amount.setText(f"偏差率: {rate_str} | 净偏差率: {net_rate_str}")
        else:
            self.main_window.summary_amount.setText(f"偏差率: {rate_str}")
        self.main_window.summary_qty.setText(f"偏差量: {qty_sum:,.2f}")

    def update_mark_stats(self):
        """更新主表上方『标记统计』标签"""
        lbl = getattr(self.main_window.main_table, "mark_stats_label", None)
        if lbl is None:
            return

        sm = getattr(self.main_window, 'source_model', None)
        pm = getattr(self.main_window, 'proxy_model', None)
        if sm is None or pm is None:
            lbl.setText("标记统计：—")
            return

        alert = getattr(sm, "_alert_rows", set())
        sub = getattr(sm, "_substitute_rows", set())
        unused = getattr(sm, "_unused_rows", set())
        n_alert = n_sub = n_unused = 0

        rows = pm.rowCount()
        if rows:
            for r in range(rows):
                sr = pm.mapToSource(pm.index(r, 0)).row()
                if sr in alert:
                    n_alert += 1
                if sr in sub:
                    n_sub += 1
                if sr in unused:
                    n_unused += 1

        lbl.setText(
            "🔴 偏差预警 %d 条    🔵 替代料 %d 条    ⚪ 未投料 %d 条"
            % (n_alert, n_sub, n_unused)
        )

    def update_read_counter(self):
        """刷新状态栏常驻的「已读计数」标签（自动 N / 手动 M）"""
        try:
            self.main_window._read_counter_label.setText(
                f"📖 已读：自动 {self.main_window._auto_read_count} / 手动 {self.main_window._manual_read_count}"
            )
        except RuntimeError:
            pass  # 标签已被 deleteLater 回收（关窗时序），忽略

    def update_analysis_time_label(self, mode):
        """刷新状态栏常驻的「分析时间」标签。mode 为 '自动' 或 '手动'"""
        try:
            ts = time.strftime("%m-%d %H:%M:%S")
            self.main_window._analysis_time_label.setText(f"🕒 分析：{mode} {ts}")
        except RuntimeError:
            pass

    def toggle_stats_from_toolbar(self, visible):
        """从工具栏切换统计面板可见性"""
        if hasattr(self.main_window, 'stats_cards'):
            if visible:
                self.main_window.stats_cards.show_panel()
            else:
                self.main_window.stats_cards._toggle_cards(False)

    def toggle_progress_from_toolbar(self, visible):
        """从工具栏切换进度条可见性"""
        if hasattr(self.main_window, 'main_table'):
            self.main_window.main_table.set_progress_visible(visible)

    def auto_collapse_progress_after_analysis(self):
        """分析完成 6s 后自动收起进度面板；若新一轮分析已开始（_heavy_busy）则放弃"""
        if getattr(self.main_window, '_heavy_busy', False):
            return
        if hasattr(self.main_window, 'main_table'):
            self.main_window.main_table.set_progress_visible(False)

    def on_stats_visibility_changed(self, visible):
        """概览面板显隐变化时同步工具栏按钮文字和顶部容器可见性"""
        # v43.264：图标化后按钮文字去 emoji 前缀（图标常驻，文字只表状态）
        self.main_window.action_btn_toggle_stats.setText("概览" if visible else "显示概览")
        self.main_window.action_btn_toggle_stats.setToolTip("隐藏本次分析概览" if visible else "显示本次分析概览")
        self.main_window._update_top_panel_visibility()

    def on_progress_visibility_changed(self, visible):
        """进度面板显隐变化时同步工具栏按钮文字和顶部容器可见性"""
        self.main_window.action_btn_toggle_progress.setText("进度" if visible else "显示进度")
        self.main_window.action_btn_toggle_progress.setToolTip("隐藏分析进度" if visible else "显示分析进度")

    def update_top_panel_visibility(self):
        """两个面板都隐藏时，把顶部容器也隐藏，释放空间给表格"""
        stats_visible = not self.main_window.stats_cards._user_hidden
        progress_visible = not self.main_window.main_table._progress_hidden
        self.main_window.top_panel.setVisible(stats_visible or progress_visible)
