#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建新的 core/alert_monitor.py（替换原文件）"""

import os

new_content = '''# -*- coding: utf-8 -*-
"""
实时预警监控线程
后台定期扫描 audit_data，发现超阈值偏差时发射信号
裴哥 | 2026-06-08 修改（使用 threading.Thread 替代 QThread）
"""
import threading
import time
import pandas as pd
from PySide6.QtCore import QObject, Signal


class AlertMonitor(QObject):
    alert_triggered = Signal(pd.DataFrame)

    def __init__(self, data_source_func, threshold=10, interval=60):
        super().__init__()
        self.data_source_func = data_source_func
        self.threshold = threshold
        self.interval = interval
        self._stop_flag = False
        self._thread = None
        self._seen_alerts = set()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_flag = False
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag = True
        if self._thread:
            self._thread.join(timeout=2)

    def _monitor_loop(self):
        while not self._stop_flag:
            try:
                df = self.data_source_func()
                if df is not None and not df.empty:
                    self._check_alerts(df)
            except Exception as e:
                print(f"预警监控错误: {e}")
            time.sleep(self.interval)

    def _check_alerts(self, df):
        if '偏差率(%)' not in df.columns:
            return
        df_copy = df.copy()
        df_copy['_alert_id'] = df_copy['订单日期'].astype(str) + '|' + df_copy['流程订单'].astype(str) + '|' + df_copy['物料编码'].astype(str)
        over_df = df_copy[df_copy['偏差率(%)'].abs() > self.threshold]
        if over_df.empty:
            return
        new_ids = set(over_df['_alert_id']) - self._seen_alerts
        if new_ids:
            self._seen_alerts.update(new_ids)
            new_alerts = df_copy[df_copy['_alert_id'].isin(new_ids)].copy()
            if '_alert_id' in new_alerts.columns:
                new_alerts.drop(columns=['_alert_id'], inplace=True)
            self.alert_triggered.emit(new_alerts)
'''

fp = r"E:\zpp011_dev\模块化脚本\core\alert_monitor.py"
with open(fp, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Done! Created new alert_monitor.py")
print(f"File: {fp}")
