# -*- coding: utf-8 -*-
"""偏差率预警口径的**单一事实来源**（v43.134）。

## 为什么要这个模块
同一概念「偏差率预警」此前在三个地方各写一份判定，且口径不一致：

| 位置 | 阈值 | 排除替代料 | 排除未投料 |
|---|---|---|---|
| 未读概览浮窗 `_count_unread_items` | >= 10% | 否（用 alert_monitor 命中） | **是** |
| 统计卡片「真异常」 `_update_anomaly` | **> 30%** | **是** | **否** |
| 点击卡片后的状态栏提示 | **> 30%** | **否** | **否** |

实测后果（构造 5 行样本复现）：
* 一行 |偏差率|=20% —— 浮窗/看板算它，卡片「真异常」不算；
* 一行 |偏差率|=35% 且是否替代料=是 —— 卡片**文案说**「已排除替代料」，
  `_update_anomaly` 里确实排除了，但 `main_window.py:3007` 的状态栏提示**没排除**；
* 一行未投料（实际=0、定额>0、偏差率 -100%）—— 浮窗/看板排除它，卡片算它。

同一个数在界面上出现两个值，用户会认为是 bug。

## 本模块的口径（裴哥 2026-10-04 决定：统一成 10%，取消「真异常」独立档）
`|偏差率| >= 10%` 且 **非替代料** 且 **非未投料**。

* 「非替代料」：优先用 `是否替代料 == '是'`；该列不存在时回退看 `_替代料组` 非空。
* 「非未投料」：与模型层 `data_frame_model._unused_only` 同源
  —— `实际 ≈ 0 且 定额 > 0`（未投料的偏差率恒为 -100%，是 BOM 推算的机械结果）。

## 用法
```python
from gui_pyside6.utils.alert_rules import deviation_alert_mask, ALERT_RATE_THRESHOLD
mask = deviation_alert_mask(df, rate_col='偏差率(%)')
n = int(mask.sum())
```
"""
import pandas as pd

# 全项目唯一的偏差率预警阈值（%）。此前浮窗/看板用 10、卡片用 30，现统一为 10。
ALERT_RATE_THRESHOLD = 10.0

# 判定「未投料」的容差：|实际| <= 该值视为 0（与 data_frame_model.py 的 _unused_only 口径一致）
_ZERO_TOL = 0.001


def _first_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def unused_mask(df):
    """未投料掩码：实际≈0 且 定额>0（偏差率恒 -100% 的机械结果）。"""
    act = _first_col(df, ['数量-实际', '实际', '数量 - 实际'])
    qty = _first_col(df, ['数量-定额', '定额', '数量 - 定额'])
    if act is None or qty is None:
        return pd.Series(False, index=df.index)
    a = pd.to_numeric(df[act], errors='coerce').fillna(0)
    q = pd.to_numeric(df[qty], errors='coerce').fillna(0)
    return (a.abs() <= _ZERO_TOL) & (q > _ZERO_TOL)


def alt_mask(df):
    """替代料掩码；无任何替代料列时返回全 False（表示「没有替代料」而非「全是替代料」）。"""
    col = _first_col(df, ['是否替代料', 'is_alt'])
    if col is not None:
        return df[col].astype(str).str.strip().isin(['是', 'True', 'true', '1'])
    grp = _first_col(df, ['_替代料组', '替代料组'])
    if grp is not None:
        return df[grp].notna() & (df[grp].astype(str).str.strip() != '')
    return pd.Series(False, index=df.index)


def deviation_alert_mask(df, rate_col=None, threshold=None):
    """偏差率预警掩码：|偏差率| >= threshold 且 非替代料 且 非未投料。

    参数
    ----
    df        : 主表或任意含相关列的 DataFrame
    rate_col  : 偏差率列名；不给则自动探测（偏差率(%) / 偏差率 / dev_rate）
    threshold : 阈值（%），默认 ``ALERT_RATE_THRESHOLD``（10.0）

    返回
    ----
    与 df.index 对齐的布尔 Series。缺偏差率列时返回全 False。
    """
    if df is None or len(df) == 0:
        return pd.Series([], dtype=bool)
    if rate_col is None:
        rate_col = _first_col(df, ['偏差率(%)', '偏差率', 'dev_rate'])
    if rate_col is None:
        return pd.Series(False, index=df.index)
    thr = ALERT_RATE_THRESHOLD if threshold is None else float(threshold)
    rates = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
    return (rates.abs() >= thr) & (~alt_mask(df)) & (~unused_mask(df))
