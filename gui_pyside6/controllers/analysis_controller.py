# -*- coding: utf-8 -*-
"""
分析控制器
负责：分析线程的启动、取消、进度/结果信号转发
"""

from PySide6.QtCore import QObject, Signal
from gui_pyside6.models.workers import AnalysisWorker


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

    def start_analysis(self, input_file, alt_pairs, start_date, end_date, material_search):
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
        }

        self.analysis_started.emit()
        self.worker = AnalysisWorker(
            input_file, alt_pairs, start_date, end_date, material_search
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
        """分析完成回调：按工厂拆分数据"""
        self.worker = None
        
        # 按工厂拆分
        self.factory_data = {}
        if df is not None and not df.empty and '工厂' in df.columns:
            for factory, group in df.groupby('工厂'):
                self.factory_data[str(factory)] = group.copy()
        else:
            # 无工厂列或空数据，存为"全部"
            self.factory_data['全部'] = df
        
        # 设置当前工厂
        if self.factory_data:
            self.current_factory = list(self.factory_data.keys())[0]
        else:
            self.current_factory = None
        
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
