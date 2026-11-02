# -*- coding: utf-8 -*-
"""
UI 管理器（ARC-003 v43）

负责封装所有与 UI 相关的操作，包括：
- 进度条、标签、时间显示
- 表格状态更新
- 按钮状态
- 进度面板控制
"""

import time
import os

import PySide6.QtCore as QtCore
from PySide6.QtWidgets import QMessageBox

from gui_pyside6.widgets.toast import toast


class ViewManager:
    """管理主窗口 UI 更新（独立于业务逻辑）."""

    def __init__(self, main_window):
        self.mw = main_window
        self._countdown_timer = None
        self._analysis_start_ts = 0.0

    # ==================== 分析阶段 UI ====================

    def run_ui_start(self, speed=None):
        """开始分析时的 UI 初始化 ."""
        self.mw.progress_bar.setValue(0)
        self.mw.progress_bar.setVisible(True)
        self.mw.start_btn.setEnabled(False)
        self._analysis_start_ts = time.perf_counter()
        self._current_step = "准备中"
        self.mw.main_table.reset_step_icons()
        self.mw.main_table.set_progress_visible(True)
        self.mw.timer_lbl.setText("00:00")
        self._countdown_seconds = 0
        try:
            _mode = "自动" if getattr(self.mw, "_monitor_auto_loading", False) else "手动"
            self.mw._analysis_time_label.setText(f"分析中…（{_mode}）")
        except RuntimeError:
            pass
        if self._countdown_timer is None:
            self._countdown_timer = QtCore.QTimer(self.mw)
            self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)
        self.mw._heavy_busy = True

    def run_ui_progress(self, percent, step_name):
        """更新进度 UI (线程同步到主线程) ."""
        current = self.mw.progress_bar.value()
        if percent < current:
            self._current_step = step_name
            self.mw.progress_label.setText(f"{step_name}  （进度 {current}%）")
            return
        self.mw.progress_bar.setValue(percent)
        self._current_step = step_name
        self.mw.main_table.update_step_icons(percent, step_name)
        elapsed = int(time.perf_counter() - self._analysis_start_ts)
        m, s = divmod(elapsed, 60)
        self.mw.timer_lbl.setText(f"{m:02d}:{s:02d}")
        self.mw.progress_label.setText(f"{step_name}  {percent}%")

    def run_ui_finished(self, df, processed_df):
        """分析完成后的 UI 更新 ."""
        _analysis_mode = "自动" if getattr(self.mw, "_monitor_auto_loading", False) else "手动"
        self.mw._monitor_auto_loading = False
        self.mw._monitor_current_key = None
        self._update_analysis_time_label(_analysis_mode)
        self.mw.progress_bar.setValue(100)
        self.mw.main_table.complete_step_icons()
        self.mw.progress_bar.setVisible(False)
        self.mw.start_btn.setEnabled(True)
        elapsed = self._format_elapsed()
        self.mw.progress_label.setText(f"完成 ({elapsed})")
        toast(f"分析完成，共 {len(df)} 条记录 ({elapsed})", "success", parent=self.mw)
        self.mw.statusBar().showMessage("分析完成，正在加载结果...")
        self.mw.application().processEvents()
        self.reset_filters()
        self.on_factory_changed('全部')
        self.mw.application().processEvents()

        try:
            if processed_df is None or processed_df.empty:
                if '_read' in df.columns:
                    processed_df = df
                else:
                    processed_df = self.mw.data_service.preprocess_audit_data(df)
            else:
                processed_df = df if '_read' in df.columns else self.mw.data_service.preprocess_audit_data(df)
            self.mw._auto_read_by_rules(processed_df)
            self.mw._reconcile_quarantine_read_status(processed_df)
            self.mw.source_model.setDataFrame(processed_df)
            self.mw.application().processEvents()
            self.schedule_unread_summary()
            self.mw.view_model.df = processed_df
            self.mw._update_read_counter()
            self.mw._analysis_params = self.mw.analysis_controller.get_analysis_params()
            self.mw._set_column_widths()
            self.mw.application().processEvents()
            self.mw.statusBar().showMessage(f"分析完成，共加载 {len(processed_df)} 行 × {len(processed_df.columns)} 列")
            self._update_summary()
            self.mw.application().processEvents()
            self.mw.main_table.summary_container.raise_()
            self.mw.main_table.summary_container.repaint()
            self.mw.application().processEvents()
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self._stop_countdown()
            self.mw._heavy_busy = False
            QMessageBox.critical(self.mw, "错误", f"加载结果失败：{e}")
            return
        finally:
            if not self.mw.alert_monitor.isRunning():
                self.mw.alert_monitor.start()

        # 隔离区和过期处理
        self.auto_collapse_progress_after_analysis()  # 注意：这个应该在本方法后由 orchestrator 触发? 已直接调用? 
        self.mw._auto_move_to_quarantine(manual=False)
        self.mw._scan_expired_quarantine_after_analysis(ApplySheetsFrom=0)

    def on_cache_progress_ui(self, percent, step_name):
        """完整报告缓存阶段进度 UI 更新 ."""
        try:
            self.mw.progress_label.setText(f"完整报告缓存：{step_name}（{percent}%）")
        except RuntimeError:
            pass

    def finish_cache_phase(self):
        """完整报告缓存结束 ."""
        _w = getattr(self.mw.analysis_controller, "worker", None)
        if _w and _w.isRunning():
            return
        self._stop_countdown()
        # 6s 后自动收起进度面板
        QtCore.QMetaObject.invokeMethod(
            self, "auto_collapse_progress_after_analysis", QtCore.QMetaObject.ConnectionMethod.AutoConnection)
        try:
            self.mw.statusBar().showMessage("完整报告缓存已生成（Sheet6~10 + Excel）", 4000)
        except RuntimeError:
            pass

    def run_ui_error(self, error_msg):
        """处理分析错误，更新 UI 并弹出提示 ."""
        self.mw._heavy_busy = False
        self.mw._heavy_busy = False
        self._stop_countdown()
        self.mw.progress_bar.setVisible(False)
        try:
            _analysis_mode = "自动" if getattr(self.mw, "_monitor_auto_loading", False) else "手动"
            self.mw._analysis_time_label.setText(
                f"分析失败（{_analysis_mode}）{time.strftime('%m-%d %H:%M:%S')}"
            )
        except RuntimeError:
            pass
        if getattr(self.mw, "_monitor_auto_loading", False):
            self.mw._monitor_auto_loading = False
            self.mw.start_btn.setEnabled(True)
            self.mw.progress_label.setText("监控加载失败")
            self.mw.main_table.reset_step_icons()
            if self.mw._monitor_current_key:
                self.mw._monitor_loaded.discard(self.mw._monitor_current_key)
                self.mw._monitor_pending.discard(self.mw._monitor_current_key)
                self.mw._monitor_current_key = None
            _fn = os.path.basename(self.mw.current_input_file or "新文件")
            if "被占用" in error_msg or "锁文件" in error_msg:
                toast(f"文件仍被占用，监控将自动重试：{_fn}", "warning", parent=self.mw)
                self.mw.log(f"监控自动加载失败（将重试）：{error_msg}", "warning")
            else:
                toast(f"监控自动加载失败：{error_msg}", "warning", parent=self.mw)
                self.mw.log(f"监控自动加载失败：{error_msg}", "error")
            return
        self.mw.progress_label.setText("错误（可重试）")
        self.mw.start_btn.setEnabled(True)
        self.mw.main_table.reset_step_icons()
        QMessageBox.critical(self.mw, "错误", error_msg)

    # ==================== 工具 ====================

    def auto_collapse_progress_after_analysis(self):
        """6 秒后自动收起进度面板 ."""
        from PySide6.QtCore import QTimer
        QTimer.singleShot(6000, self.mw._auto_collapse_progress_after_analysis)
        try:
            self.mw.statusBar().showMessage("完整报告缓存已生成（Sheet6~10 + Excel）", 4000)
        except RuntimeError:
            pass

    def reset_filters(self):
        """清空所有筛选条件 ."""
        try:
            if self.mw.proxy_model is not None:
                self.mw.proxy_model.clearFilters()
            if getattr(self.mw, '_filtered_col_set', None):
                self.mw._filtered_col_set.clear()
                if hasattr(self.mw, "_sort_header"):
                    self.mw._sort_header.update()
            self.mw._update_col_filter_hint()
            if hasattr(self.mw, 'filter_panel') and self.mw.filter_panel is not None:
                self.mw.filter_panel.blockSignals(True)
                try:
                    self.mw.filter_panel.reset_filters()
                finally:
                    self.mw.filter_panel.blockSignals(False)
        except Exception as _e:
            print(f"[WARN] 分析完成后清筛选失败 (不影响主流程): {_e}", flush=True)

    def on_factory_changed(self, val):
        """简化的工厂切换方法 ."""
        pass

    def schedule_unread_summary(self):
        """调度显示未读摘要窗 ."""
        if hasattr(self.mw, '_schedule_unread_summary'):
            self.mw._schedule_unread_summary()

    def update_analysis_time_label(self, analysis_mode):
        self.mw._analysis_time_label.setText(f"分析完成（{analysis_mode}）")

    def update_summary(self):
        """更新统计摘要卡片 ."""
        if hasattr(self.mw, '_update_summary'):
            self.mw._update_summary()

    def format_elapsed(self):
        elapsed = int(time.perf_counter() - self._analysis_start_ts)
        m, s = divmod(elapsed, 60)
        return f"{m}分{s}秒"

    def stop_countdown(self):
        """停止倒计时 ."""
        if self._countdown_timer:
            self._countdown_timer.stop()
            self._countdown_timer = None
        self._analysis_start_ts = 0.0

    def _update_countdown(self):
        """每秒更新倒计时标签 ."""
        elapsed = int(time.perf_counter() - self._analysis_start_ts)
        m, s = divmod(elapsed, 60)
        self.mw.timer_lbl.setText(f"{m:02d}:{s:02d}")

    # ==================== 其他辅助 ====================

    def capture_last_used_filter(self):
        """保存当前筛选为「上次使用」预设 ."""
        if hasattr(self.mw, '_capture_last_used_filter'):
            self.mw._capture_last_used_filter()

    def drop_stale_input_cache(self):
        """检查并丢弃陈旧输入缓存 ."""
        if hasattr(self.mw, '_drop_stale_input_cache'):
            return self.mw._drop_stale_input_cache()
        return False

    def set_column_widths(self):
        if hasattr(self.mw, '_set_column_widths'):
            self.mw._set_column_widths()

    def auto_read_by_rules(self, df):
        if hasattr(self.mw, 'quarantine_manager_controller'):
            self.mw.quarantine_manager_controller._auto_read_by_rules(df)

    def reconcile_quarantine_read_status(self, df):
        if hasattr(self.mw, '_reconcile_quarantine_read_status'):
            self.mw._reconcile_quarantine_read_status(df)

    def auto_move_to_quarantine(self, manual):
        if hasattr(self.mw, '_auto_move_to_quarantine'):
            self.mw._auto_move_to_quarantine(manual)

    def scan_expired_quarantine_after_analysis(self, ApplySheetsFrom=0):
        if hasattr(self.mw, '_scan_expired_quarantine_after_analysis'):
            self.mw._scan_expired_quarantine_after_analysis(ApplySheetsFrom)
