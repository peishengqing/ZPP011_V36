# -*- coding: utf-8 -*-
"""
改进版分析控制器 (v2) - 试点重构

目标：将 MainWindow 的分析相关逻辑解耦为独立控制器，
作为 God Object 重构的第一块试点。

当前只处理两个核心方法：_start_analysis 和 _on_analysis_finished_ui
"""
import os
import time
import datetime
from PySide6.QtCore import QObject, Signal, QTimer

from gui_pyside6.widgets.toast import toast
from core.read_status import upsert_material_names


class AnalysisControllerV2(QObject):
    """分析流程控制器（试点）"""

    # 信号
    progress = Signal(int, str)  # (percent, step_name)
    analysis_finished = Signal(object)  # (df)
    analysis_error = Signal(str)  # (error_msg)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._start_ts = None

    def start_analysis(self, input_file, alt_pairs, start_date, end_date, material_search, dyn_thresh=None):
        """开始分析流程（对应 MainWindow._start_analysis）"""
        self._start_ts = time.time()

        # 置 busy 标志
        self.main_window._heavy_busy = True

        # 查是否有重复分析
        if self.main_window._full_analysis_cache_path == self.main_window.current_input_file:
            # 延迟 toast 让 UI 来得及刷新
            QTimer.singleShot(0, lambda: toast("本字段已分析过", level="info"))
            self.main_window._heavy_busy = False
            return

        # 设置分析参数
        self.main_window._analysis_params = {
            "input_file": input_file,
            "alt_pairs": alt_pairs,
            "start_date": start_date,
            "end_date": end_date,
            "material_search": material_search,
            "dyn_thresh": dyn_thresh,
        }

        # 启动后台分析
        self.progress.emit(0, "准备数据...")
        # ... 后续移除到大 DW 的逻辑

    def on_analysis_finished(self, df):
        """分析完成回调（对应 MainWindow._on_analysis_finished_ui）"""
        try:
            # 清理 busy 状态
            self.main_window._heavy_busy = False

            # 保存文件路径
            base_path, _ = os.path.splitext(self.main_window.current_input_file)
            analysis_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output_path = f"{base_path}_分析{analysis_time_str}.xlsx"
            self.main_window.analysis_output_path = output_path

            # 保存读状态
            try:
                upsert_material_names(self.main_window._audit_df)
            except Exception:
                pass

            # 更新已读计数
            self.main_window._update_analysis_time_label("手动")

            # 统计卡片重构
            # self._update_stats_cards(df)

            # 显示分析结果
            # self.main_window.source_model.set_df(df)

            # 完成提示
            # QTimer.singleShot(0, lambda: toast("分析完成！"))

            # 通知 UI
            self.main_window._on_analysis_finished_ui(df)
        except Exception:
            # 静默异常，通知 UI 已有错误处理
            pass

    def _update_analysis_time_label(self, mode):
        """更新状态栏分析时间标签"""
        self.main_window._analysis_time_label.setText(
            f"🕒 分析：{mode}"
        )

