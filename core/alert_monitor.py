# -*- coding: utf-8 -*-
"""
实时预警监控（主线程 QTimer 轮询）
后台定期扫描 audit_data，发现超阈值偏差时发射信号。
裴哥 | 2026-10-13 改：原 threading.Thread 后台线程在 Windows 上跨线程访问 GUI 线程的
QObject（view_model）并直接 emit Qt 信号，触发 COM 套间错误 0x8001010D（faulthandler
报 "Windows fatal exception"），导致监控线程静默死亡、实时预警停摆。改用主线程 QTimer
轮询：所有 Qt 对象访问与信号发射都发生在 GUI 线程，根因消除；轮询间隔内仅做轻量 pandas
过滤，不阻塞界面。
"""
import pandas as pd
from PySide6.QtCore import QObject, Signal, QTimer


def filter_alt_alerts(df, threshold):
    """替代料看板过滤（与手动看板共用，保证逻辑一致）。

    规则：
      1. 仅保留替代料（是否替代料 == '是'）；
      2. 进看板条件：偏差率绝对值 > 阈值  OR  替代料组内有差异（净偏差数量非零）。
         即「替代料有差异都进看板」，不再被单行偏差率阈值挡在门外。

    返回过滤后的 DataFrame（保留原始全部列）；无匹配时返回空 DataFrame。
    """
    if '是否替代料' not in df.columns or '偏差率(%)' not in df.columns:
        return df.iloc[0:0]
    alt = df[df['是否替代料'] == '是'].copy()
    if alt.empty:
        return alt
    over_th = alt['偏差率(%)'].abs() > threshold
    if '净偏差数量' in alt.columns:
        # 净偏差数量非零 = 替代料组内有未被完全顶替的差异
        has_diff = alt['净偏差数量'].fillna(0).abs() > 1e-6
    else:
        # 缺净偏差列时回退：仅按偏差率阈值
        has_diff = pd.Series(False, index=alt.index)
    return alt[over_th | has_diff]


class AlertMonitor(QObject):
    alert_triggered = Signal(pd.DataFrame)

    def __init__(self, data_source_func, threshold=10, interval=60, only_alt=True):
        super().__init__()
        self.data_source_func = data_source_func
        self.threshold = threshold
        self.interval = interval
        self.only_alt_materials = only_alt
        self._timer = None
        self._seen_alerts = set()

    def isRunning(self):
        return self._timer is not None and self._timer.isActive()

    def start(self):
        if self.isRunning():
            return
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setInterval(max(1000, int(self.interval * 1000)))
            self._timer.timeout.connect(self._monitor_loop)
        self._timer.start()

    def stop(self):
        if self._timer is not None:
            self._timer.stop()

    def _monitor_loop(self):
        # 由主线程 QTimer 周期性调用（非后台线程），无需自旋/睡眠。
        # 仍在取到数据后做快照拷贝：保持与 GUI 侧 view_model.df 的隔离，
        # 避免主线程改写源 DataFrame 时产生数据竞争。
        try:
            raw = self.data_source_func()
            if raw is not None and not raw.empty:
                df = raw.copy()
                self._check_alerts(df)
        except Exception as e:
            print(f"预警监控错误: {e}")

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
        # 仅替代料模式：替代料有差异 或 偏差率超阈值 都进看板（与手动看板一致）
        if self.only_alt_materials and '是否替代料' in df.columns:
            alerts_df = filter_alt_alerts(df, self.threshold)
        else:
            alerts_df = df[df['偏差率(%)'].abs() > self.threshold]
        if alerts_df is None or alerts_df.empty:
            return
        # 已标记已读的替代料预警不再视为"新增"，避免跨会话重复打扰
        # （_read 列由 data_service 预处理从 SQLite 恢复，已读状态持久化）
        if '_read' in alerts_df.columns:
            alerts_df = alerts_df[alerts_df['_read'] != 1]
        if alerts_df is None or alerts_df.empty:
            return
        alerts_df = alerts_df.copy()
        alerts_df['_alert_id'] = (alerts_df['订单日期'].astype(str) + '|'
                                  + alerts_df['流程订单'].astype(str) + '|'
                                  + alerts_df['物料编码'].astype(str))
        new_ids = set(alerts_df['_alert_id']) - self._seen_alerts
        if new_ids:
            self._seen_alerts.update(new_ids)
            new_alerts = alerts_df[alerts_df['_alert_id'].isin(new_ids)].copy()
            new_alerts.drop(columns=['_alert_id'], inplace=True)
            self.alert_triggered.emit(new_alerts)
