# -*- coding: utf-8 -*-
"""
阈值控制器（v43.367）

负责：统一阈值配置（core/threshold_config）的加载与应用；把新值推给所有需要消耗的活对象。

模式：
  · 持有 MainWindow 引用（self.mw）
  · 对内的私有方法，被 MainWindow 的薄壳调用
  · 对外的公共方法：`apply_thresholds()`（由 RulesCenter 保存后触发）
"""

from core import threshold_config as _thr


class ThresholdController:
    """阈值控制器。"""

    def __init__(self, mw):
        self.mw = mw

    def apply_thresholds(self):
        """阈值页保存后把新值推给所有活对象。

        「同一屏两种红」的根因是阈值写在五处；真源统一后还差这一步——改完当场生效，
        不靠重启。set_alert_threshold 从写下来就没有调用者，这里就是它的调用者。
        """
        cfg = _thr.reload_thresholds()
        if getattr(self.mw, "alert_monitor", None) is not None:
            self.mw.alert_monitor.update_config(threshold=cfg["alert_dev_rate_pct"])
        if getattr(self.mw, "proxy_model", None) is not None:
            self.mw.proxy_model.set_alert_threshold(cfg["alert_dev_rate_pct"])
        if getattr(self.mw, "source_model", None) is not None:
            self.mw.source_model.refresh_threshold_colors()
        self.mw._on_view_model_data_changed()
