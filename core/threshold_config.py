# -*- coding: utf-8 -*-
"""偏差率阈值与提醒 —— 全应用唯一真源（设计稿 v43.333 第四期E「同口径原则」）。

改造前这五处各写各的，「同一屏出现两种红」不是错觉而是事实：
  * ``models/data_frame_model.py`` 主表橙色高亮：``(rates.abs() >= 10) & ((rates - 100.0).abs() >= 1e-6) & (~no_input)``
  * ``AuditProxyModel`` 颜色筛选：``self._alert_threshold = 10.0``，而配套的
    ``set_alert_threshold()`` **零调用者**（写了没人按，永远停在 10）
  * ``controllers/dashboard_controller.py`` 偏差率预警看板：又一个 ``>= 10``
  * ``widgets/stats_cards.py`` KPI 偏差预警 / 真异常：``>= 10`` 与 ``> 30``
  * ``main_window.py`` 未读汇总与卡片点击：``>= 10`` 与 ``> 30``
  * 替代料看板与三个看板内容组件的颜色筛选（``dialogs/alert_dialog.py``、
    ``widgets/{neg_loss,pos_loss,semi}_content.py``）：各自 ``threshold = 10.0``
    再试着从 AlertMonitor 猜一个值，猜不到就用 10 —— 于是「看板里的橙色判定」
    和主表能不一致，而 ``AlertMonitor.threshold`` 本身没人更新
``core/config_loader.py`` 里那个 ``alert.threshold_percent`` 更是没有任何调用者，
属于「配置文件里写着、代码里没人读」的假真源。

本模块把判据收成一个函数 + 一份配置，默认值就是上面各处今天的字面量，
所以**不改默认值时行为逐字节不变**；改一次 = 五处一起变。

字段（``config/threshold_config.json``）：
  alert_dev_rate_pct    10.0  |偏差率| ≥ 此值 → 预警（主表橙色 / 颜色筛选 / 看板 / KPI）
  anomaly_dev_rate_pct  30.0  |偏差率| > 此值 且 非替代料 → 真异常（KPI「真异常」）
  ai_pass_rate_min_pct  80.0  AI 通过率低于此值 → KPI 卡片标红（此前没有任何下限）
  exclude_sap_zero_div  True  |偏差率| 恰为 +100.0%（定额=0 的 SAP 除零钳位假值）不计入
  exclude_unfed         True  实际=0 且 定额>0（未投料，恒 -100%）不计入预警

⚠️ ``exclude_unfed`` 与 ``config/auto_read_rules.json`` 的同名开关是两回事：
   那个管「自动已读要不要跳过未投料行」（默认关），这个只管显示口径（默认开，
   即改造前五处一致的口径）。红线不变：实际=0（未投料）永远留在隔离区待人工
   审计，本模块的任何取值都不改变它是否被自动已读。

两处刻意**没**并进来，别误当已统一：
  * 筛选面板「动态阈值」``dyn_thresh_spin``（默认 10.0）→ 只喂 Excel 导出的
    Sheet3「无备注预警」与 Sheet4「中间地带」的分界。它是每次分析前可手改的
    报表参数，和本模块的「界面判据」是两个用户可见概念；并成一个会让改一次阈值
    悄悄改变导出结果，需要单独决策。
  * 偏差率区间筛选下拉的档位（「绝对值>=10%」「>20%」「>30%」）是用户挑的过滤
    选项，不是阈值；跟着配置漂移反而会让保存后筛选条件莫名变宽/变窄。
"""

import json
import logging
import os

import pandas as pd

# 复用规则模块已有的配置路径解析：exe 模式下 __file__ 落在随机临时目录，
# 持久化必须写回项目 config，抄第三份那段分支只会多一个会漏改的地方。
from core.auto_read_rules import _resolve_config_path

CONFIG_PATH = _resolve_config_path("threshold_config.json")

DEFAULTS = {
    "alert_dev_rate_pct": 10.0,
    "anomaly_dev_rate_pct": 30.0,
    "ai_pass_rate_min_pct": 80.0,
    "exclude_sap_zero_div": True,
    "exclude_unfed": True,
}

#: 数值型阈值（界面用 QDoubleSpinBox，落库统一 float）
_NUM_KEYS = ("alert_dev_rate_pct", "anomaly_dev_rate_pct", "ai_pass_rate_min_pct")
_BOOL_KEYS = ("exclude_sap_zero_div", "exclude_unfed")

RATE_COLS = ("偏差率(%)", "偏差率", "dev_rate")
ACTUAL_COLS = ("数量-实际", "实际")
QUOTA_COLS = ("数量-定额", "定额")
# 与 stats_cards 改造前的探测顺序一致：先找标记列，再找替代料组列
ALT_FLAG_COLS = ("是否替代料", "is_alt")
ALT_GROUP_COLS = ("_替代料组", "替代料组")

#: SAP 除零钳位假值恒为 +100.0%，用 1e-6 容差判等（改造前五处同一个写法）
_SAP_CLAMP_PCT = 100.0
_EPS = 1e-6
_ZERO_TOL = 0.001

_cache = None


# ------------------------------------------------------------------ 读写
def load_threshold_config():
    """读盘并合并默认值，返回 5 个键的完整配置（缺键/坏值一律回落默认）。

    读不到文件不算错误（首次启动），但文件存在却解析失败要留一行日志：
    那意味着用户改过的阈值正在被静默丢弃。
    """
    cfg = dict(DEFAULTS)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                cfg.update(user)
    except Exception as e:  # 坏文件回落默认，但不能静默
        logging.getLogger(__name__).warning("阈值配置读取失败，回落默认: %s", e)
    return _normalize(cfg)


def _normalize(cfg):
    out = {}
    for k in _NUM_KEYS:
        try:
            out[k] = float(cfg.get(k, DEFAULTS[k]))
        except (TypeError, ValueError):
            out[k] = float(DEFAULTS[k])
    for k in _BOOL_KEYS:
        out[k] = bool(cfg.get(k, DEFAULTS[k]))
    return out


def save_threshold_config(cfg):
    """原子写回，返回真正生效的配置（同时刷新进程内缓存）。"""
    merged = _normalize(cfg or {})
    d = os.path.dirname(CONFIG_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
    global _cache
    _cache = dict(merged)
    return merged


def get_thresholds():
    """进程内缓存读 —— 主表重算/逐行颜色判定这类热路径用它，别每次都读盘。"""
    global _cache
    if _cache is None:
        _cache = load_threshold_config()
    return _cache


def reload_thresholds():
    global _cache
    _cache = load_threshold_config()
    return _cache


# ------------------------------------------------------------------ 列探测与解析
def _first_col(df, candidates):
    cols = list(getattr(df, "columns", []))
    return next((c for c in candidates if c in cols), None)


def rate_series(df, col=None):
    """偏差率列 → float Series（NaN 记 0）。

    改造前五处解析方式并不一致：主表与颜色筛选会先 ``str.replace('%','')``
    再转数值，KPI/看板/汇总则直接 ``pd.to_numeric`` —— 于是同一份数据里
    「12.5%」这种带百分号的字符串在主表算命中、在 KPI 算 0，正是两种红的来源。
    这里统一取**更宽容**的那一种：数值列原样转，字符串列先剥 % 和空白。
    """
    col = col or _first_col(df, RATE_COLS)
    if col is None:
        return None
    raw = df[col]
    if pd.api.types.is_numeric_dtype(raw):
        return pd.to_numeric(raw, errors="coerce").fillna(0.0)
    s = raw.astype(str).str.replace("%", "", regex=False).str.strip()
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def unfed_mask(df):
    """实际=0 且 定额>0（未投料）；两列任一缺失时返回 None（无从判断）。"""
    act_col, qty_col = _first_col(df, ACTUAL_COLS), _first_col(df, QUOTA_COLS)
    if not (act_col and qty_col):
        return None
    a = pd.to_numeric(df[act_col], errors="coerce").fillna(0.0)
    q = pd.to_numeric(df[qty_col], errors="coerce").fillna(0.0)
    return (a.abs() <= _ZERO_TOL) & (q > _ZERO_TOL)


def substitute_mask(df):
    """替代料行；没有任何替代料相关列时返回 None。

    判定顺序照抄改造前 stats_cards 的写法：先看标记列（``是否替代料`` / ``is_alt``
    取「是/True/1」），否则看替代料组列（非空即替代料）。
    """
    flag = _first_col(df, ALT_FLAG_COLS)
    if flag is not None:
        return df[flag].astype(str).str.strip().isin(["是", "True", "true", "1"])
    grp = _first_col(df, ALT_GROUP_COLS)
    if grp is not None:
        return df[grp].notna() & (df[grp].astype(str).str.strip() != "")
    return None


# ------------------------------------------------------------------ 判据（唯一真源）
def dev_alert_mask(df, cfg=None):
    """偏差率预警掩码：主表橙色高亮 / 颜色筛选 / 预警看板 / KPI 卡片共用这一条。

    列缺失时保守返回全 False（与改造前一致：没有偏差率列就哪儿都不该亮）。
    """
    cfg = cfg or get_thresholds()
    if df is None or getattr(df, "empty", True):
        return None
    rates = rate_series(df)
    if rates is None:
        return None
    mask = rates.abs() >= cfg["alert_dev_rate_pct"]
    if cfg["exclude_sap_zero_div"]:
        mask &= (rates - _SAP_CLAMP_PCT).abs() >= _EPS
    if cfg["exclude_unfed"]:
        unfed = unfed_mask(df)
        if unfed is not None:
            mask &= ~unfed
    return pd.Series(mask, index=df.index)


def count_dev_alerts(df, cfg=None):
    m = dev_alert_mask(df, cfg)
    return 0 if m is None else int(m.sum())


def anomaly_mask(df, cfg=None):
    """真异常：|偏差率| > 阈值 且 非替代料（替代料的偏差走替代料看板）。"""
    cfg = cfg or get_thresholds()
    if df is None or getattr(df, "empty", True):
        return None
    rates = rate_series(df)
    if rates is None:
        return None
    mask = rates.abs() > cfg["anomaly_dev_rate_pct"]
    alt = substitute_mask(df)
    if alt is not None:
        mask &= ~alt
    return pd.Series(mask, index=df.index)


def count_anomalies(df, cfg=None):
    m = anomaly_mask(df, cfg)
    return 0 if m is None else int(m.sum())


def ai_pass_rate(df):
    """AI 通过率（%）；没有审核结果列或没有已审核记录时返回 None（说不准，不是 0）。"""
    if df is None or getattr(df, "empty", True):
        return None
    col = next((c for c in ("审核结果", "audit_result") if c in df.columns), None)
    if col is None:
        return None
    reviewed = df[df[col].notna() & (df[col].astype(str).str.strip() != "")]
    if reviewed.empty:
        return None
    return float((reviewed[col].astype(str).str.strip() == "合格").sum()) / len(reviewed) * 100.0


def describe_thresholds(cfg=None):
    """一句人读的口径描述，给预览条、状态条和看板提示复用。"""
    cfg = cfg or get_thresholds()
    parts = ["|偏差率| ≥ %.2f%% 计预警" % cfg["alert_dev_rate_pct"],
             "|偏差率| > %.2f%% 计真异常（排除替代料）" % cfg["anomaly_dev_rate_pct"],
             "AI 通过率下限 %.0f%%" % cfg["ai_pass_rate_min_pct"]]
    if cfg["exclude_sap_zero_div"]:
        parts.append("不计 SAP 除零假值（+100.0%）")
    if cfg["exclude_unfed"]:
        parts.append("不计未投料（实际=0）")
    return " · ".join(parts)
