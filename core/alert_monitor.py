# -*- coding: utf-8 -*-
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

    def __init__(self, data_source_func, threshold=10, interval=60, only_alt=True):
        super().__init__()
        self.data_source_func = data_source_func
        self.threshold = threshold
        self.interval = interval
        self.only_alt_materials = only_alt
        self._stop_flag = False
        self._thread = None
        self._seen_alerts = set()

    def isRunning(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.isRunning():
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

    def update_config(self, threshold=None, only_alt=None):
        """动态更新预警参数（线程安全）"""
        if threshold is not None:
            self.threshold = threshold
        if only_alt is not None:
            self.only_alt_materials = only_alt
        # 不重置 _seen_alerts，避免重复弹窗

    def _check_alerts(self, df):
        if '偏差率(%)' not in df.columns:
            return
        df_copy = df.copy()
        # 如果配置了仅替代料，过滤非替代料物料
        if self.only_alt_materials and '是否替代料' in df_copy.columns:
            df_copy = df_copy[df_copy['是否替代料'] == '是']
            if df_copy.empty:
                return
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
