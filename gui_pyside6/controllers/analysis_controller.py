# -*- coding: utf-8 -*-
"""
分析控制器
负责：分析线程的启动、取消、进度/结果信号转发
"""

from PySide6.QtCore import QObject, Signal
from gui_pyside6.models.workers import AnalysisWorker, PreprocessWorker


class AnalysisController(QObject):
    """分析业务控制器，解耦界面与后台线程"""

    # 对外信号
    analysis_started = Signal()                     # 分析开始（UI更新）
    progress_updated = Signal(int, str)             # 进度(percent, step_name)
    log_message = Signal(str, str)                  # 日志(msg, level)
    worker_log = Signal(str)                        # 接收 worker 的单参数日志信号
    analysis_finished = Signal(object)              # 分析完成，传递DataFrame
    analysis_error = Signal(str)                    # 分析错误(error_msg)
    analysis_cancelled = Signal()                   # 分析被取消

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._analysis_params = {}                  # 缓存参数供导出使用

        self.factory_data = {}  # {工厂名: DataFrame}
        self.current_factory = None  # 当前选中的工厂
        # 注：preprocess 不再搬后台（worker 调 QObject DataService 会被跨线程 signal 拖慢 30s+），
        #     改在主线程 controller._on_finished 之后跑（repro 测 0.2s，亚秒级）。
        self._data_service = None
        self._previous_df = None

    def start_analysis(self, input_file, alt_pairs, start_date, end_date, material_search,
                       dev_rate_threshold=0.0, data_service=None, previous_df=None):
        """启动分析线程"""
        if self.worker and self.worker.isRunning():
            self.log_message.emit("分析任务已在运行", "warning")
            return

        # 缓存参数
        self._analysis_params = {
            'input_file': input_file,
            'alt_pairs': list(alt_pairs),
            'start_date': start_date,
            'end_date': end_date,
            'material_search': material_search,
            'dev_rate_threshold': dev_rate_threshold,
        }
        # 缓存 data_service / previous_df 给 _on_finished 跑预处理
        self._data_service = data_service
        self._previous_df = previous_df

        self.analysis_started.emit()
        self.worker = AnalysisWorker(
            input_file, alt_pairs, start_date, end_date, material_search,
            dev_rate_threshold
        )
        self.worker.progress.connect(self.progress_updated)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self.analysis_error)
        self.worker.log.connect(self._on_worker_log)
        self.worker.start()

    def _on_worker_log(self, msg):
        """桥接槽：将 worker 的单参数 log 信号转发为双参数 log_message 信号"""
        self.log_message.emit(msg, "info")

    def cancel(self):
        """取消分析"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            if not self.worker.wait(3000):
                self.worker.terminate()
                self.worker.wait()
            self.worker = None
            self.analysis_cancelled.emit()

    def _on_finished(self, df):
        """分析完成回调：重预处理挪到后台线程，主线程绝不阻塞"""
        import time as _t
        from datetime import datetime
        def _wall():
            return datetime.now().strftime('%H:%M:%S.%f')[:-3]
        _t0 = _t.perf_counter()
        if self.worker:
            self.worker.wait()                         # 等待底层线程完全退出
        self.worker = None
        self._pending_raw_df = df
        print(f"[{_wall()}] [PERF] controller._on_finished ENTER: t={_t.perf_counter()-_t0:.3f}s", flush=True)

        # 重预处理挪到后台线程（preprocess_audit_data 内含 load_read_status 等重 DB IO），
        # 后台跑时不受窗口前后台影响、主线程 GUI 不卡。仅在结束 emit 一次结果。
        if self._data_service is not None and df is not None and not df.empty:
            self._preprocess_worker = PreprocessWorker(
                self._data_service, df, previous_df=self._previous_df)
            self._preprocess_worker.finished.connect(self._on_preprocess_done)
            self._preprocess_worker.error.connect(self._on_preprocess_error)
            print(f"[{_wall()}] [PERF] controller start PreprocessWorker", flush=True)
            self._preprocess_worker.start()
        else:
            self._last_processed_df = df
            self._emit_analysis_finished(df)

    def _on_preprocess_done(self, processed_df):
        import time as _t
        from datetime import datetime
        def _wall():
            return datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self._last_processed_df = processed_df
        print(f"[{_wall()}] [PERF] controller preprocess OK shape={processed_df.shape}", flush=True)
        self._emit_analysis_finished(processed_df)
        if self._preprocess_worker is not None:
            self._preprocess_worker.deleteLater()
            self._preprocess_worker = None

    def _on_preprocess_error(self, msg):
        import traceback as _tb
        _tb.print_exc()
        self.log_message.emit(f"预处理失败，降级用原始结果: {msg}", "error")
        # 降级：用原始（未预处理）df 继续，不阻断主流程
        self._last_processed_df = self._pending_raw_df
        self._emit_analysis_finished(self._pending_raw_df)
        if self._preprocess_worker is not None:
            self._preprocess_worker.deleteLater()
            self._preprocess_worker = None

    def _emit_analysis_finished(self, df):
        import time as _t
        from datetime import datetime
        def _wall():
            return datetime.now().strftime('%H:%M:%S.%f')[:-3]
        _t0 = _t.perf_counter()
        # 按工厂拆分
        self.factory_data = {}
        if df is not None and not df.empty and '工厂' in df.columns:
            for factory, group in df.groupby('工厂'):
                self.factory_data[str(factory)] = group.copy()
        else:
            # 无工厂列或空数据，存为"全部"
            self.factory_data['全部'] = df
        print(f"[{_wall()}] [PERF] controller groupby: t={_t.perf_counter()-_t0:.3f}s n={len(self.factory_data)}", flush=True)

        # 设置当前工厂
        if self.factory_data:
            self.current_factory = list(self.factory_data.keys())[0]
        else:
            self.current_factory = None

        print(f"[{_wall()}] [PERF] controller emit analysis_finished: total={_t.perf_counter()-_t0:.3f}s", flush=True)
        self.analysis_finished.emit(df)


    def get_factory_list(self):
        """获取工厂列表"""
        return list(self.factory_data.keys()) if self.factory_data else []

    def get_factory_data(self, factory_name=None):
        """获取指定工厂的数据，若不指定则返回当前工厂数据"""
        if factory_name is None:
            factory_name = self.current_factory
        
        if factory_name and factory_name in self.factory_data:
            return self.factory_data[factory_name]
        return None

    def set_current_factory(self, factory_name):
        """设置当前工厂"""
        if factory_name in self.factory_data:
            self.current_factory = factory_name
            return True
        return False


    def get_analysis_params(self):
        """获取最近一次分析的参数（用于导出完整Excel）"""
        return self._analysis_params

    def get_last_processed_df(self):
        """返回上一次分析处理好的 df（供 worker 做同会话变动检测）"""
        return getattr(self, '_last_processed_df', None)
