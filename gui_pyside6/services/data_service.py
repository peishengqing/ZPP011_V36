# -*- coding: utf-8 -*-
"""
统一数据服务层
协调各个专业服务，提供完整的数据处理工作流
"""

import pandas as pd
from PySide6.QtCore import QObject, Signal

from .data_preprocessor import DataPreprocessor, snapshot_qty_for, snapshot_note_for, build_data_id
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

        # 共享信号
        self.preprocessor.log_signal.connect(self.log_signal)
        self.read_status_service.log_signal.connect(self.log_signal)
        self.audit_result_service.log_signal.connect(self.log_signal)
        self.quarantine_service.log_signal.connect(self.log_signal)

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def preprocess_audit_data(self, df: pd.DataFrame, previous_df: pd.DataFrame = None) -> pd.DataFrame:
        """完整的数据处理工作流"""
        if df is None or df.empty:
            return df

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
            self.log(f"数据预处理失败: {e}", "error")
            import traceback
            traceback.print_exc()
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
