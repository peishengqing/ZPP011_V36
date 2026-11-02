# -*- coding: utf-8 -*-
"""
隔离区服务
负责：从数据库读取隔离 data_id 集合，为主表添加隔离标记
"""

import pandas as pd
from PySide6.QtCore import QObject, Signal

from core.quarantine_manager import get_quarantined_ids


class QuarantineService(QObject):
    """隔离区状态管理服务"""

    log_signal = Signal(str, str)  # (msg, level)

    def __init__(self, parent=None):
        super().__init__(parent)

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def restore_quarantine_status(self, df: pd.DataFrame) -> pd.DataFrame:
        """水合隔离区状态：从 SQLite 读取当前隔离的 data_id 集合，给主表加 _quarantined 列。

        引用模式——只存 data_id，实际数据实时从主表读取；因此主表数量被改（如500->550）
        后重新导入，隔离行会自动同步为新值，无需额外同步代码。
        """
        try:
            qids = get_quarantined_ids()
        except Exception as e:
            self.log(f"加载隔离区状态失败: {e}", "error")
            qids = set()

        df['_quarantined'] = 0
        if qids and 'data_id' in df.columns:
            df.loc[df['data_id'].isin(qids), '_quarantined'] = 1
        return df
