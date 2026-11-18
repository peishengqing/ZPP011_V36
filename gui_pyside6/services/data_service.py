# -*- coding: utf-8 -*-
"""
统一数据服务层
协调各个专业服务，提供完整的数据处理工作流
"""

import pandas as pd
from PySide6.QtCore import QObject, Signal

from .data_preprocessor import DataPreprocessor, snapshot_qty_for, snapshot_note_for, snapshot_net_for, build_data_id

# 快照工具函数为对外再导出（各看板/控制器统一从 data_service 导入）；
# 写入 __all__ 既表明再导出语义，也让 pyflakes 不再按「未使用 import」计新issue。
__all__ = [
    'DataService',
    'DataPreprocessor',
    'ReadStatusService',
    'AuditResultService',
    'QuarantineService',
    'snapshot_qty_for',
    'snapshot_note_for',
    'snapshot_net_for',
    'build_data_id',
]
from .read_status_service import ReadStatusService
from .audit_result_service import AuditResultService
from .quarantine_service import QuarantineService


class DataService(QObject):
    """综合数据服务 - 协调各子服务"""

    log_signal = Signal(str, str)  # (msg, level)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 初始化各子服务
        self.preprocessor = DataPreprocessor(self)
        self.read_status_service = ReadStatusService(self)
        self.audit_result_service = AuditResultService(self)
        self.quarantine_service = QuarantineService(self)

        # v43.406（审核整改 P0-3）：上一次预处理的失败原因。
        # None = 本次预处理完整走完；否则为异常描述字符串。
        # 调用方必须读它（或 df.attrs['preprocess_failed']）才能区分
        # “处理成功”与“降级返回了半成品数据”。
        self.last_preprocess_error = None

        # 共享信号
        self.preprocessor.log_signal.connect(self.log_signal)
        self.read_status_service.log_signal.connect(self.log_signal)
        self.audit_result_service.log_signal.connect(self.log_signal)
        self.quarantine_service.log_signal.connect(self.log_signal)

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def preprocess_audit_data(self, df: pd.DataFrame, previous_df: pd.DataFrame = None) -> pd.DataFrame:
        """完整的数据处理工作流。

        失败语义（v43.406 整改）：
        - 成功：`last_preprocess_error is None`，且 `df.attrs['preprocess_failed']` 不存在；
        - 失败：不抛异常仍返回 df（保留旧行为，避免界面白屏），但会同时
          置 `last_preprocess_error`、写 `df.attrs['preprocess_failed']`，并以
          level="error" 发 log_signal。调用方必须检查，不得当成功处理。
        """
        if df is None or df.empty:
            return df

        self.last_preprocess_error = None
        try:
            # 1. 预处理：清理、规范、增强
            df = self.preprocessor.clean_columns(df)
            df = self.preprocessor.convert_numeric_cols(df)
            df = self.preprocessor.normalize_alt_flag(df)
            df = self.preprocessor.add_data_id_and_fingerprint(df)

            # 2. 恢复状态
            df = self.read_status_service.restore_read_status(df)
            df = self.quarantine_service.restore_quarantine_status(df)
            df = self.audit_result_service.restore_audit_results(df)

            # 3. 变动检测（如果提供了旧数据）
            if previous_df is not None and not previous_df.empty:
                self.read_status_service.detect_and_notify_changes(previous_df, df)

            # 4. 列重排
            df = self.preprocessor.reorder_columns(df)

            # 5. 列名统一（审核结果 vs audit_result）
            if '审核结果' in df.columns and 'audit_result' in df.columns:
                df = df.drop(columns=['审核结果'])
                df = df.rename(columns={'audit_result': '审核结果'})
            elif '审核结果' in df.columns:
                df = df.drop(columns=['audit_result'], errors='ignore')
            elif 'audit_result' in df.columns:
                df = df.rename(columns={'audit_result': '审核结果'})

            # 6. 去除重复列
            dup = df.columns[df.columns.duplicated(keep='first')]
            if len(dup) > 0:
                df = df.loc[:, ~df.columns.duplicated(keep='first')]

            return df
        except Exception as e:
            # v43.406：原实现只打一行日志就 return 半成品，调用方无从分辨。
            # 现在显式留痕：属性 + DataFrame.attrs + error 级日志三处可查。
            self.last_preprocess_error = f"{type(e).__name__}: {e}"
            self.log(f"数据预处理失败（已降级返回，数据可能不完整）: {e}", "error")
            import traceback
            traceback.print_exc()
            try:
                df.attrs['preprocess_failed'] = self.last_preprocess_error
            except Exception:
                pass
            return df

    def get_audit_changes(self, df):
        return self.read_status_service.get_audit_changes(df)

    def mark_changes_as_read(self, changes, df):
        return self.read_status_service.mark_changes_as_read(changes, df)

    def get_factory_data(self, df):
        """获取按工厂分组的数据"""
        from .data_grouping import process_analysis_results
        return process_analysis_results(df, '工厂')

    def get_combined_factory_data(self, df):
        """获取工厂分组和全部数据"""
        from .data_grouping import get_combined_factory_data
        return get_combined_factory_data(df, '工厂')
