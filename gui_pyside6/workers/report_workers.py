# -*- coding: utf-8 -*-
"""
后台工作线程（v43.140 从 gui_pyside6/main_window.py 迁出）

_FullReportWorker   后台生成完整多 Sheet 报告
_PptReportWorker    后台生成净偏差口径 PPT
_FileReadWorker     后台读取 SAP Excel（避免大文件阻塞主线程）

迁出原因：main_window.py 已 5000+ 行、承载过多职责，本模块把「后台任务」职责单独成文件。
三者都是纯 QThread，不持有 MainWindow 引用，不含 GUI 逻辑。

路径约定：统一用 config.paths.BASE_DIR 取项目根，**不要**再用 __file__ 上溯——
本模块位于 gui_pyside6/workers/（比原位置深一层），上溯层数与 main_window 不同。
"""
from PySide6.QtCore import QThread, Signal


class _FullReportWorker(QThread):
    """后台生成完整多Sheet报告，进度/完成/失败均通过信号回主线程。"""
    progress = Signal(int, str)      # (百分比, 步骤名)
    finished_ok = Signal(str)        # (输出路径)
    failed = Signal(str)             # (错误信息)

    def __init__(self, input_file, alt_pairs, start_date, end_date,
                 material_search, output_path, parent=None, dyn_thresh=None):
        super().__init__(parent)
        self.input_file = input_file
        self.alt_pairs = alt_pairs
        self.start_date = start_date
        self.end_date = end_date
        self.material_search = material_search
        self.output_path = output_path
        self.dyn_thresh = dyn_thresh
        self._cancel = False

    def request_cancel(self):
        self._cancel = True

    def run(self):
        from analysis.analyzer import do_analysis_v2
        from core.config_manager import ConfigManager
        try:
            _cfg = ConfigManager()
            do_analysis_v2(
                input_file=self.input_file, output_dir=None,
                alt_pairs=self.alt_pairs,
                progress_callback=lambda step_idx, step_name, percent: (
                    self.progress.emit(percent, step_name),
                    self._cancel,
                )[1] if self._cancel_check() else self.progress.emit(percent, step_name),
                cancel_check=self._cancel_check,
                start_date=self.start_date, end_date=self.end_date,
                material_search=self.material_search,
                output_path=self.output_path,
                enable_net_offset=_cfg.get_net_offset_enabled(),
                return_dataframe=False,
                dyn_thresh=self.dyn_thresh,
            )
            if self._cancel:
                self.failed.emit("已取消")
                return
            self.finished_ok.emit(self.output_path)
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self.failed.emit(str(e))

    def _cancel_check(self, *args):
        return self._cancel


class _PptReportWorker(QThread):
    """后台调用 build_ppt_net.build_net_report 生成净偏差口径 PPT（不锁界面）。"""
    progress = Signal(int, str)      # (百分比, 步骤名)
    finished_ok = Signal(str)        # (输出路径)
    failed = Signal(str)             # (错误信息)
    _log = Signal(str, str)          # (msg, level) -> 主线程日志

    def __init__(self, df, output_path, src_name=None, parent=None):
        super().__init__(parent)
        self.df = df
        self.output_path = output_path
        self.src_name = src_name

    def run(self):
        try:
            # v43.140：本类原在 gui_pyside6/main_window.py 内，靠 __file__ 上溯两层
            # 取项目根。搬到 gui_pyside6/workers/ 后只上溯一层会指向 gui_pyside6/，
            # 导致 `from build_ppt_net import build_net_report` 失败。
            # 改用 config.paths.BASE_DIR（config/paths.py:9 定义，已实测 == 项目根，
            # 且打包 onefile 成 exe 后依然正确，不受临时解压目录影响）。
            import sys as _sys
            from config.paths import BASE_DIR as _root
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            from build_ppt_net import build_net_report
            build_net_report(self.df, self.output_path, src_name=self.src_name)
            self.finished_ok.emit(self.output_path)
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self.failed.emit(str(e))


class _FileReadWorker(QThread):
    """后台读取 SAP Excel，避免大文件阻塞主线程（文件选择卡顿修复）"""
    loaded = Signal(object, str)   # (df, file_path)
    failed = Signal(str)           # (错误信息)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            from utils.excel_io import open_excel_book  # calamine 优先（快 5x），openpyxl 兜底
            xl = open_excel_book(self.file_path)
            sheets = xl.sheet_names
            target = "Data" if "Data" in sheets else sheets[0]
            df = xl.parse(target)  # 复用已打开的工作簿，不重复解析整个文件
            self.loaded.emit(df, self.file_path)
        except Exception as e:
            self.failed.emit(str(e))
