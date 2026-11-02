# -*- coding: utf-8 -*-
"""
分析流程编排（v43 中全线程统管）
负责：分析启动、缓存管理、结果处理、UI 更新
"""

import os
import tempfile
import time
from datetime import datetime

import PySide6.QtCore as QtCore
from PySide6.QtWidgets import QMessageBox

from gui_pyside6.widgets.toast import toast
from gui_pyside6.workers.report_workers import _FileReadWorker, _FullCacheWorker


class AnalysisOrchestrator:
    """协调分析全流程：启动分析、进度追踪、缓存与结果处理。"""

    def __init__(self, main_window):
        self.mw = main_window
        self.ui_manager = self.mw.ui_manager
        self._heavy_busy = False
        self._analysis_start_ts = 0.0
        self._current_step = "准备中"
        self._countdown_seconds = 0
        self._countdown_timer = None
        self._cache_worker = None
        self._full_report_worker = None
        self._file_worker = None
        self._pending_analysis_after_reread = False
        self._cache_worker = None
        self._full_analysis_cache_path = None

    # ==================== 生命周期 ====================

    def reset(self):
        """复位本协调器状态（窗口关闭时调用）。"""
        self._stop_countdown()
        self._heavy_busy = False
        self.mw._heavy_busy = False
        self.mw._cache_worker = None

    def _stop_countdown(self):
        if self._countdown_timer:
            self._countdown_timer.stop()
            self._countdown_timer = None
        self._analysis_start_ts = 0.0

    # ==================== 启动分析 ====================

    def start_analysis(self):
        """供主窗口按钮调用的入口。"""
        if not self.mw.current_input_file:
            QMessageBox.warning(self.mw, "提示", "请先选择输入文件")
            return
        if self._heavy_busy:
            QMessageBox.information(self.mw, "提示", "分析/报告生成进行中，请稍候")
            return
        if self.mw.analysis_controller.worker and self.mw.analysis_controller.worker.isRunning():
            QMessageBox.information(self.mw, "提示", "分析任务已在后台运行")
            return

        # 记录当前筛选为「上次使用」预设（面板在分析完成后会重置）
        self._capture_last_used_filter()
        self.mw.current_input_file = os.path.normpath(self.mw.current_input_file)

        # 获取阈值、日期等参数
        dev_threshold = getattr(self.mw.filter_panel, 'dev_threshold_spin', None)
        dev_threshold_val = dev_threshold.value() if dev_threshold is not None else 0.0

        dyn_threshold = getattr(self.mw.filter_panel, 'dyn_thresh_spin', None)
        dyn_thresh_val = dyn_threshold.value() if dyn_threshold is not None else 10.0

        def _qdate_or_empty(edit):
            try:
                if edit.date() == edit.minimumDate():
                    return ""
            except Exception:
                return ""
            return edit.date().toString("yyyy-MM-dd")

        fp = self.mw.filter_panel
        if hasattr(fp, 'analysis_start_date_edit'):
            start_date = _qdate_or_empty(fp.analysis_start_date_edit)
            end_date = _qdate_or_empty(fp.analysis_end_date_edit)
        else:
            start_date, end_date = "", ""

        # 源文件被外部改过 → 先丢弃缓存，再后台重新读取，等读完再续跑分析
        if self._drop_stale_input_cache():
            if self._heavy_busy:
                QMessageBox.information(self.mw, "提示", "分析/报告生成进行中，请稍候")
                return
            if hasattr(self.mw, 'preview_label') and self.mw.preview_label:
                self.mw.preview_label.setText("源文件已修改，正在重新读取…")
            self._pending_analysis_after_reread = True
            self._file_worker = _FileReadWorker(self.mw.current_input_file)
            self._file_worker.loaded.connect(self._on_reread_then_analyze)
            self._file_worker.failed.connect(self._on_file_failed)
            self._file_worker.start()
            return

        # 启动分析
        self.mw.analysis_controller.start_analysis(
            self.mw.current_input_file,
            self.mw.alt_controller.get_pairs(),
            start_date,
            end_date,
            "",
            dev_threshold_val,
            self.mw.data_service,
            self.mw.analysis_controller.get_last_processed_df(),
            getattr(self.mw, '_cached_input_df', None),
            dyn_thresh=dyn_thresh_val,
        )

    # ==================== 重读续分析 ====================

    def _on_reread_then_analyze(self, df, file_path):
        """文件重读完成后，自动续跑刚才挂起的那次分析。"""
        if hasattr(self.mw, '_on_file_loaded'):
            self.mw._on_file_loaded(df, file_path)  # 复用原有装载逻辑
        if self._pending_analysis_after_reread:
            self._pending_analysis_after_reread = False
            # 异步调度到事件循环下一帧
            QtCore.QMetaObject.invokeMethod(
                self.start_analysis, "qt",
                QtCore.QMetaObject.ConnectionMethod.AutoConnection)

    def _on_file_failed(self, err):
        self._pending_analysis_after_reread = False
        QMessageBox.critical(self.mw, "错误", f"读取文件失败：{err}")
        self._heavy_busy = False

    # ==================== 进度与 UI ====================

    def _run_ui_start(self):
        """开始分析时的 UI 初始化。"""
        self.ui_manager.run_ui_start()

    def _run_ui_progress(self, percent, step_name):
        """更新进度 UI（线程同步到主线程）。"""
        self.ui_manager.run_ui_progress(percent, step_name)

    def _run_ui_finished(self, df, processed_df):
        # UI 更新委托
        try:
            self.ui_manager.run_ui_finished(df, processed_df)
        finally:
            # 启动完整报告缓存
            self._start_cache_worker()

    def _start_cache_worker(self):
        """启动或复用缓存生成线程。"""
        cache_dir = os.path.join(tempfile.gettempdir(), "zpp011_analysis")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"full_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        self.mw._full_analysis_cache_path = cache_path

        params = self.mw.analysis_controller.get_analysis_params()
        if self._cache_worker and self._cache_worker.isRunning():
            self._cache_worker.finished.connect(self._finish_cache_phase)
            self.mw.progress_label.setText("主分析完成 · 完整报告缓存生成中…")
        else:
            self._cache_worker = _FullCacheWorker(
                params['input_file'], params['alt_pairs'],
                params.get('start_date', ''), params.get('end_date', ''),
                params.get('material_search', ''), cache_path,
                dyn_thresh=params.get('dyn_thresh'),
            )
            _cw = self._cache_worker
            self._heavy_busy = True
            def _on_cache_done():
                self._heavy_busy = False
                if self._cache_worker is _cw:
                    self._cache_worker = None
                self._finish_cache_phase()
            self._cache_worker.finished.connect(_on_cache_done)
            self._cache_worker.progress.connect(self._on_cache_progress_ui)
            self._cache_worker.start()
            self.mw.progress_label.setText("主分析完成 · 完整报告缓存生成中…")

    def _on_cache_progress_ui(self, percent, step_name):
        """完整报告缓存阶段进度 UI 更新。"""
        self.ui_manager.on_cache_progress_ui(percent, step_name)

    def _finish_cache_phase(self):
        """完整报告缓存结束：计时器收口，6s 后自动收起进度面板。"""
        self.ui_manager.finish_cache_phase()

    # ==================== 工具 ====================

    def _update_countdown(self):
        """每秒更新倒计时标签。"""
        elapsed = int(time.perf_counter() - self._analysis_start_ts)
        m, s = divmod(elapsed, 60)
        self.mw.timer_lbl.setText(f"{m:02d}:{s:02d}")

    def _format_elapsed(self):
        elapsed = int(time.perf_counter() - self._analysis_start_ts)
        m, s = divmod(elapsed, 60)
        return f"{m}分{s}秒"

    def _reset_filters(self):
        """清空所有筛选条件，防止新分析被过滤成 0 行。"""
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
            print(f"[WARN] 分析完成后清筛选失败(不影响主流程): {_e}", flush=True)

    def _update_analysis_time_label(self, analysis_mode):
        self.mw._analysis_time_label.setText(f"分析完成（{analysis_mode}）")

    def _schedule_unread_summary(self):
        self.mw._schedule_unread_summary()  # 调用主窗口方法（已存在）

    def _on_factory_changed(self, val):
        """简化版：实际应调用界面相应的工厂切换方法。"""
        pass

    def _update_summary(self):
        """更新统计摘要卡片。"""
        self.mw._update_summary()  # 主窗口已有此方法

    def _auto_read_by_rules(self, df):
        return self.mw.quarantine_manager_controller._auto_read_by_rules(df)

    def _reconcile_quarantine_read_status(self, df):
        self.mw._reconcile_quarantine_read_status(df)

    def _auto_move_to_quarantine(self, manual):
        self.mw._auto_move_to_quarantine(manual)

    def _scan_expired_quarantine_after_analysis(self, ApplySheetsFrom=0):
        self.mw._scan_expired_quarantine_after_analysis(ApplySheetsFrom)

    def _capture_last_used_filter(self):
        """保存当前筛选为「上次使用」预设。"""
        self.mw._capture_last_used_filter()

    def _drop_stale_input_cache(self):
        """检查并丢弃陈旧输入缓存。"""
        return self.mw._drop_stale_input_cache()

    def _set_column_widths(self):
        self.mw._set_column_widths()

    def _format_preview_stats(self, df):
        return self.mw._format_preview_stats(df)

    def _auto_collapse_progress_after_analysis(self):
        """6 秒后自动收起进度面板。"""
        self.mw.ui_settings_controller.auto_collapse_progress_after_analysis()

    # ==================== 取消 ====================

    def request_cancel(self):
        """主线程调用：取消当前分析或缓存生成。"""
        self._heavy_busy = False
        self.mw._heavy_busy = False
        if self._cache_worker:
            self._cache_worker.request_cancel()
        if self.mw.analysis_controller.worker:
            self.mw.analysis_controller.cancel()

    def _run_ui_error(self, error_msg):
        """处理分析错误，更新 UI 并弹出提示。"""
        self.ui_manager.run_ui_error(error_msg)
