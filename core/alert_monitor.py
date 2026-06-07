# -*- coding: utf-8 -*-
"""
实时预警监控线程
后台定期扫描 audit_data，发现超阈值偏差时发射信号
裴哥 | 2026-06-04
"""
from PySide6.QtCore import QThread, Signal
import pandas as pd
import time


class AlertMonitor(QThread):
    """后台监控线程：定期扫描 audit_data，发现超阈值偏差时弹窗通知"""

    # 信号：传递超阈值的 DataFrame
    alert_triggered = Signal(pd.DataFrame)

    def __init__(self, data_provider, threshold=10, interval=60):
        """
        :param data_provider: 无参函数，返回当前 audit_data（DataFrame 或 None）
        :param threshold: 偏差率阈值（绝对值），默认 10%
        :param interval: 扫描间隔（秒），默认 60 秒
        """
        super().__init__()
        self.data_provider = data_provider
        self.threshold = threshold
        self.interval = interval
        self.last_alert_keys = set()   # 已预警过的记录标识，避免重复报警
        self._running = True

    def run(self):
        """后台循环扫描"""
        while self._running:
            df = self.data_provider()
            if df is not None and not df.empty:
                rate_col = next(
                    (c for c in ['偏差率(%)', '偏差率'] if c in df.columns),
                    None
                )
                if rate_col:
                    # 先转数字，避免字符串导致 abs() 崩溃
                    rate_series = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
                    high_dev = df[rate_series.abs() > self.threshold].copy()
                    if not high_dev.empty:
                        # 用业务主键生成唯一标识
                        keys = []
                        for _, row in high_dev.iterrows():
                            k = f"{row.get('订单日期','')}_{row.get('流程订单','')}_{row.get('物料编码','')}"
                            keys.append(k)
                        high_dev['_alert_key'] = keys
                        new_alerts = high_dev[~high_dev['_alert_key'].isin(self.last_alert_keys)]
                        if not new_alerts.empty:
                            self.last_alert_keys.update(new_alerts['_alert_key'].tolist())
                            # 只传需要的列给 UI
                            cols = [c for c in ['物料编码', '物料名称', '偏差率(%)', '偏差率', '偏差金额', '订单日期'] if c in new_alerts.columns]
                            self.alert_triggered.emit(new_alerts[cols])
            # 等待 interval 秒（每次循环检查 1 秒，可快速响应停止请求）
            for _ in range(self.interval):
                if not self._running:
                    return
                time.sleep(1)

    def stop(self):
        """停止监控线程"""
        self._running = False
        self.wait()
