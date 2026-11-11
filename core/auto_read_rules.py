# -*- coding: utf-8 -*-
"""
自动已读 — 业务规则（可配置 · 多规则版）

规则通过 config/auto_read_rules.json 配置，本模块每次执行实时读取，无需重启。
配置结构：
  {
    "enabled": true,                 # 总开关；False 则完全不自动已读
    "rules": [                       # 规则列表，多条规则 OR 并存
      {
        "name": "偏差数量=0",         # 规则名称（仅界面展示用，不落库）
        "enabled": true,             # 单条规则开关
        "conditions": [              # 组内多条件 AND，全部满足才命中
          {"type": "dev_qty_eq", "params": {"value": 0}}
        ],
        "ignore_exclude_unfed": false,   # 本条豁免全局「排除未投料」
        "ignore_exclude_units": false    # 本条豁免全局「排除单位」
      }
    ]
  }

匹配语义（关键）：
  - 多条规则之间为 OR（并集）：一条记录命中任意一条「启用」的规则即自动已读。
  - **列表顺序不改变哪些行被读掉**，只影响反馈文案里「这条归谁」的统计口径：
    ``mark_read_batch`` 落库时只记 read_source='auto'，不记规则名，所以不存在
    「靠前的规则优先、后面的规则被抢走」这种自动隔离式优先级。
  - 单条规则内可有多条件（AND）；条件「开着，但数据里没有对应列」→ 该项不匹配
    （False），整条规则随之不匹配，保守不误伤。

向后兼容：旧版单条配置（顶层直接是 enabled/name/type/params...）会在 load 时自动包成 rules[0]。

说明：
  - 本模块只负责返回命中掩码（union + 逐规则），真正的 mark_read_batch / 列标记
    由 GUI 层完成，与手动标记已读走同一套落库路径。
  - 列名在不同 SAP 导出可能不同，故用候选名依次探测，缺失则对应条件判为不匹配。
"""

import json
import logging
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))


def _resolve_config_path(filename):
    """返回配置文件的【持久化】绝对路径（读写均用此路径，重启后仍可读回）。

    源码模式：使用项目内 config/ 目录（与源码配置同处），__file__ 稳定。
    exe 模式（PyInstaller onefile 每次解压到随机临时目录 _MEIxxxx）：
      __file__ 不可信；_MEIPASS 是临时解压目录，退出即删，**绝不作为写入目标**。
      配置【只】持久化到项目 config 目录，默认 E:\\zpp011_v2\\config（与源码配置
      同处、重启后仍在、且不与 exe 同目录），可用环境变量 ZPP011_PROJECT_ROOT
      覆盖。读不到持久化文件时，load 会回退到打包内置默认（见 _bundle_config_path），
      保证首次启动仍有默认规则。
    """
    if getattr(sys, "frozen", False):
        project_root = os.environ.get("ZPP011_PROJECT_ROOT")
        if project_root:
            # ZPP011_PROJECT_ROOT 直接指向 config 目录（如 E:\zpp011_v2\config）
            return os.path.join(project_root, filename)
        # 未设置环境变量时，默认本机部署固定 config 目录（不与 exe 同目录）
        return os.path.join("E:\\zpp011_v2", "config", filename)
    return os.path.join(_HERE, "..", "config", filename)


def _bundle_config_path(filename):
    """exe 模式下返回打包进 exe 的默认配置文件路径（只读兜底）；

    仅当持久化文件尚不存在时由 load 回退使用，避免「首次启动无默认规则」。
    非 exe 模式，或打包副本不存在时返回 None。
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass is not None:
            p = os.path.join(meipass, "config", filename)
            if os.path.exists(p):
                return p
    return None


CONFIG_PATH = _resolve_config_path("auto_read_rules.json")

# --------------------------------------------------------------------------- 条件类型注册表
# 每个条件类型约定：
#   label      : 下拉框显示名
#   field      : 命中判定的目标列（候选名依次探测）
#   op         : 比较算子（eq / startswith / contains / in）
#   value_type : 参数输入控件类型（number / text / textlist）
#   default    : 默认参数值
#   hint       : 编辑区占位提示
CONDITION_TYPES = {
    "dev_qty_eq": {
        "label": "偏差数量等于",
        "field_candidates": ["偏差数量"],
        "op": "eq",
        "value_type": "number",
        "default": 0,
        "hint": "例如 0 表示偏差数量为零的记录自动已读",
    },
    "mat_code_prefix": {
        "label": "物料编码前缀为",
        "field_candidates": ["物料编码", "组件物料号", "物料号"],
        "op": "startswith",
        "value_type": "text",
        "default": "600",
        "hint": "例如 600 表示物料编码以 600 开头的记录自动已读",
    },
    "mat_code_in": {
        "label": "物料编码属于",
        "field_candidates": ["物料编码", "组件物料号", "物料号"],
        "op": "in",
        "value_type": "textlist",
        "default": "",
        "hint": "逗号分隔的编码列表，命中任一即已读，例如 600123,600456",
    },
    "mat_name_contains": {
        "label": "物料名称包含",
        "field_candidates": ["物料名称", "组件物料描述", "物料描述"],
        "op": "contains",
        "value_type": "text",
        "default": "",
        "hint": "物料名称包含该关键字即已读",
    },
    "mat_name_not_contains": {
        "label": "物料名称不含",
        "field_candidates": ["物料名称", "组件物料描述", "物料描述"],
        "op": "not_contains",
        "value_type": "text",
        "default": "",
        "hint": "物料名称不含该关键字才已读；逗号分隔多值表示「且不含其中任一」，例如 箱,彩罐",
    },
    "mat_type_eq": {
        "label": "物料类型等于",
        "field_candidates": ["物料类型", "物料分类", "物料大类"],
        "op": "eq_str",
        "value_type": "text",
        "default": "包材",
        "hint": "例如 包材 / 原料",
    },
    "factory_eq": {
        "label": "工厂等于",
        "field_candidates": ["工厂", "工厂名称"],
        "op": "eq_str",
        "value_type": "text",
        "default": "云南达利-饮料厂",
        "hint": "例如 云南达利-饮料厂 表示仅该工厂的记录自动已读（可用于把某条规则限定到饮料厂/食品厂）",
    },
    "dev_qty_range": {
        "label": "偏差数量在范围(开区间)",
        "field_candidates": ["偏差数量"],
        "op": "range",
        "value_type": "range",
        "default": {"min": 0, "max": 1},
        "param_label": "偏差数量在",
        "hint": "开区间 (min, max)，不含端点，例如 (0, 1) 表示 0<偏差数量<1",
    },
    "dev_qty_gt": {
        "label": "偏差数量大于",
        "field_candidates": ["偏差数量"],
        "op": "gt",
        "value_type": "number",
        "default": 0,
        "hint": "偏差数量 > x",
    },
    "dev_qty_lt": {
        "label": "偏差数量小于",
        "field_candidates": ["偏差数量"],
        "op": "lt",
        "value_type": "number",
        "default": 0,
        "hint": "偏差数量 < x",
    },
    "dev_qty_gte": {
        "label": "偏差数量大于等于",
        "field_candidates": ["偏差数量"],
        "op": "gte",
        "value_type": "number",
        "default": 0,
        "hint": "偏差数量 ≥ x",
    },
    "dev_qty_lte": {
        "label": "偏差数量小于等于",
        "field_candidates": ["偏差数量"],
        "op": "lte",
        "value_type": "number",
        "default": 0,
        "hint": "偏差数量 ≤ x",
    },
    # —— 实际数量（用于排除未投料：实际数量=0）——
    "actual_qty_eq": {
        "label": "实际数量等于",
        "field_candidates": ["数量-实际", "实际", "实际数量", "实际耗用"],
        "op": "eq",
        "value_type": "number",
        "default": 0,
        "hint": "实际数量 = x",
    },
    "actual_qty_gt": {
        "label": "实际数量大于",
        "field_candidates": ["数量-实际", "实际", "实际数量", "实际耗用"],
        "op": "gt",
        "value_type": "number",
        "default": 0,
        "hint": "实际数量 > x（常用：> 0 排除未投料）",
    },
    "actual_qty_gte": {
        "label": "实际数量大于等于",
        "field_candidates": ["数量-实际", "实际", "实际数量", "实际耗用"],
        "op": "gte",
        "value_type": "number",
        "default": 0,
        "hint": "实际数量 ≥ x",
    },
    "actual_qty_lt": {
        "label": "实际数量小于",
        "field_candidates": ["数量-实际", "实际", "实际数量", "实际耗用"],
        "op": "lt",
        "value_type": "number",
        "default": 0,
        "hint": "实际数量 < x",
    },
    "actual_qty_lte": {
        "label": "实际数量小于等于",
        "field_candidates": ["数量-实际", "实际", "实际数量", "实际耗用"],
        "op": "lte",
        "value_type": "number",
        "default": 0,
        "hint": "实际数量 ≤ x",
    },
    # —— 偏差率（百分比，与看板预警阈值口径一致；保护小单位物料）——
    "dev_rate_eq": {
        "label": "偏差率等于",
        "field_candidates": ["偏差率(%)", "偏差率"],
        "op": "eq",
        "value_type": "number",
        "default": 0,
        "hint": "偏差率 = x%（如 0 表示零偏差）",
    },
    "dev_rate_range": {
        "label": "偏差率在范围(开区间)",
        "field_candidates": ["偏差率(%)", "偏差率"],
        "op": "range",
        "value_type": "range",
        "default": {"min": 0, "max": 10},
        "param_label": "偏差率在",
        "hint": "开区间 (min, max)，不含端点，例如 (0, 10) 表示 0%<偏差率<10%",
    },
    "dev_rate_gt": {
        "label": "偏差率大于",
        "field_candidates": ["偏差率(%)", "偏差率"],
        "op": "gt",
        "value_type": "number",
        "default": 10,
        "hint": "偏差率 > x%",
    },
    "dev_rate_lt": {
        "label": "偏差率小于",
        "field_candidates": ["偏差率(%)", "偏差率"],
        "op": "lt",
        "value_type": "number",
        "default": 10,
        "hint": "偏差率 < x%（常用：保护小单位，只有偏差率足够小才自动已读）",
    },
    "dev_rate_gte": {
        "label": "偏差率大于等于",
        "field_candidates": ["偏差率(%)", "偏差率"],
        "op": "gte",
        "value_type": "number",
        "default": 10,
        "hint": "偏差率 ≥ x%",
    },
    "dev_rate_lte": {
        "label": "偏差率小于等于",
        "field_candidates": ["偏差率(%)", "偏差率"],
        "op": "lte",
        "value_type": "number",
        "default": 10,
        "hint": "偏差率 ≤ x%（常用：偏差率不超过 x% 才自动已读）",
    },
}

# 实际数量候选列（排除未投料逻辑使用）
_ACTUAL_QTY_CANDIDATES = ["数量-实际", "实际", "实际数量", "实际耗用"]

# 单位候选列（排除单位逻辑使用）
_UNIT_CANDIDATES = ["单位", "组件单位", "基本单位", "计量单位"]

DEFAULT_RULES = [
    {"name": "偏差数量=0", "enabled": True, "type": "dev_qty_eq", "params": {"value": 0}, "ignore_exclude_units": True},
    # 600 物料拥有最高优先级：永远直接自动已读，因此默认豁免「排除未投料」与「排除单位」。
    {"name": "物料600开头", "enabled": True, "type": "mat_code_prefix", "params": {"value": "600"},
     "ignore_exclude_unfed": True, "ignore_exclude_units": True},
]

DEFAULT_CONFIG = {"enabled": True, "rules": [dict(r) for r in DEFAULT_RULES],
                  "exclude_unfed": False, "exclude_units": False, "excluded_units": ""}


def _first_col(df: pd.DataFrame, candidates):
    """返回 df 中第一个存在的候选列名，都不存在则返回 None。"""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _is_600_rule_raw(rule):
    """判断一条规则（原始 dict，兼容新旧格式）是否为「600 开头物料」规则。"""
    if not isinstance(rule, dict):
        return False
    if rule.get("type") == "mat_code_prefix" and \
            str(rule.get("params", {}).get("value", "")).strip().startswith("600"):
        return True
    for c in rule.get("conditions") or []:
        if isinstance(c, dict) and c.get("type") == "mat_code_prefix" and \
                str(c.get("params", {}).get("value", "")).strip().startswith("600"):
            return True
    return False


# --------------------------------------------------------------------------- 配置读写
def _normalize_condition(cond):
    """把单条条件（type + params）补齐为合法结构。"""
    if not isinstance(cond, dict):
        cond = {}
    t = cond.get("type")
    if t not in CONDITION_TYPES:
        t = "dev_qty_eq"
    spec = CONDITION_TYPES[t]
    params = cond.get("params") if isinstance(cond.get("params"), dict) else {}
    if spec["value_type"] == "range":
        # range：min / max 两个数字
        mn = _to_num(params.get("min", spec["default"].get("min", 0)))
        mx = _to_num(params.get("max", spec["default"].get("max", 1)))
        norm_params = {"min": mn, "max": mx}
    elif spec["value_type"] == "number":
        val = _to_num(params.get("value", spec["default"]))
        norm_params = {"value": val}
    else:  # text / textlist
        val = str(params.get("value", spec["default"])).strip()
        norm_params = {"value": val}
    return {"type": t, "params": norm_params}


def _normalize_rule(rule):
    """补齐字段，保证每条规则都有完整键。

    兼容两种历史/目标结构：
      - 旧单条件：{name, enabled, type, params}
      - 新多条件：{name, enabled, conditions:[{type, params}, ...]}
    若两者都有，conditions 优先；只有旧 type 时自动包成 conditions[0]。
    """
    r = {
        "name": "未命名规则",
        "enabled": True,
        "ignore_exclude_unfed": False,
        "ignore_exclude_units": False,
        "conditions": [dict(_normalize_condition({"type": "dev_qty_eq",
                                                  "params": {"value": CONDITION_TYPES["dev_qty_eq"]["default"]}}))],
    }
    if isinstance(rule, dict):
        if rule.get("name") not in (None, ""):
            r["name"] = str(rule["name"]).strip()
        if "enabled" in rule:
            r["enabled"] = bool(rule["enabled"])
        if "ignore_exclude_unfed" in rule:
            r["ignore_exclude_unfed"] = bool(rule["ignore_exclude_unfed"])
        if "ignore_exclude_units" in rule:
            r["ignore_exclude_units"] = bool(rule["ignore_exclude_units"])
        conds = rule.get("conditions")
        if isinstance(conds, list) and conds:
            r["conditions"] = [_normalize_condition(c) for c in conds if isinstance(c, dict)]
        elif "type" in rule:
            # 旧单条件格式
            r["conditions"] = [_normalize_condition(rule)]
    return r


def load_auto_read_rules_config():
    """读取配置，兼容旧单条格式，返回 {'enabled': bool, 'rules': [规则...]}。

    读取优先级：① 持久化文件 CONFIG_PATH → ② 打包内置默认（_bundle_config_path，
    首次启动 / 持久化文件被删时兜底）→ ③ 代码内 DEFAULT_RULES。
    """
    cfg = {"enabled": DEFAULT_CONFIG["enabled"], "rules": [dict(r) for r in DEFAULT_RULES],
           "exclude_unfed": DEFAULT_CONFIG.get("exclude_unfed", False),
           "exclude_units": DEFAULT_CONFIG.get("exclude_units", False),
           "excluded_units": DEFAULT_CONFIG.get("excluded_units", "")}
    try:
        src = CONFIG_PATH
        if not os.path.exists(src):
            # 持久化文件不存在 → 回退打包内置默认（仅首次启动或文件被删）
            bundle = _bundle_config_path("auto_read_rules.json")
            if bundle and os.path.exists(bundle):
                src = bundle
        if os.path.exists(src):
            with open(src, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                if "rules" in user and isinstance(user["rules"], list):
                    # 新格式
                    cfg["enabled"] = bool(user.get("enabled", True))
                    cfg["exclude_unfed"] = bool(user.get("exclude_unfed", False))
                    cfg["exclude_units"] = bool(user.get("exclude_units", False))
                    cfg["excluded_units"] = str(user.get("excluded_units", "")).strip()
                    raw_rules = [r for r in user["rules"] if isinstance(r, dict)]
                    # 迁移：600 开头物料拥有最高优先级，自动补上单位排除豁免（仅当未显式设置时）。
                    for r in raw_rules:
                        if _is_600_rule_raw(r) and "ignore_exclude_units" not in r:
                            r["ignore_exclude_units"] = True
                    rules = [_normalize_rule(r) for r in raw_rules]
                    cfg["rules"] = rules if rules else [_normalize_rule(r) for r in DEFAULT_RULES]
                else:
                    # 旧单条格式：包成 rules[0]
                    old = _normalize_rule(user)
                    cfg["rules"] = [old]
    except Exception as e:
        logging.warning("自动已读规则配置加载失败: %s", e)
    return cfg


def save_auto_read_rules_config(cfg):
    """合并默认配置后写回文件，返回最终生效配置（{'enabled', 'rules', 'exclude_unfed', 'exclude_units', 'excluded_units'}）。"""
    merged = {
        "enabled": bool(cfg.get("enabled", True)),
        "exclude_unfed": bool(cfg.get("exclude_unfed", False)),
        "exclude_units": bool(cfg.get("exclude_units", False)),
        "excluded_units": str(cfg.get("excluded_units", "")).strip(),
        "rules": [_normalize_rule(r) for r in (cfg.get("rules") or [])],
    }
    if not merged["rules"]:
        merged["rules"] = [dict(r) for r in DEFAULT_RULES]
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, CONFIG_PATH)
    return merged


# --------------------------------------------------------------------------- 文案生成
def build_condition_summary(cond):
    """生成单条条件（conditions 数组元素）的预览文本。"""
    spec = CONDITION_TYPES.get(cond.get("type"), CONDITION_TYPES["dev_qty_eq"])
    val = cond.get("params", {})
    if spec["op"] == "eq":
        return "%s = %s" % (spec["label"], _to_num(val.get("value", 0)))
    if spec["op"] == "startswith":
        raw = str(val.get("value", "")).strip()
        if "," in raw:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            return "%s（%s）" % (spec["label"], "、".join(items) if items else "未填")
        return "%s「%s」" % (spec["label"], raw)
    if spec["op"] == "contains":
        raw = str(val.get("value", "")).strip()
        if "," in raw:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            return "%s（%s）" % (spec["label"], "、".join(items) if items else "未填")
        return "%s「%s」" % (spec["label"], raw)
    if spec["op"] == "not_contains":
        raw = str(val.get("value", "")).strip()
        if "," in raw:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            return "%s（%s）" % (spec["label"], "、".join(items) if items else "未填")
        return "%s「%s」" % (spec["label"], raw)
    if spec["op"] == "in":
        items = [x.strip() for x in str(val.get("value", "")).split(",") if x.strip()]
        return "%s（%s）" % (spec["label"], "、".join(items) if items else "未填")
    if spec["op"] == "eq_str":
        return "%s「%s」" % (spec["label"], str(val.get("value", "")).strip())
    if spec["op"] == "range":
        return "%s (%s, %s)" % (spec["label"], _to_num(val.get("min", 0)), _to_num(val.get("max", 1)))
    if spec["op"] == "gt":
        return "%s %s" % (spec["label"], _to_num(val.get("value", 0)))
    if spec["op"] == "lt":
        return "%s %s" % (spec["label"], _to_num(val.get("value", 0)))
    if spec["op"] == "gte":
        return "%s %s" % (spec["label"], _to_num(val.get("value", 0)))
    if spec["op"] == "lte":
        return "%s %s" % (spec["label"], _to_num(val.get("value", 0)))
    return spec["label"]


def build_rule_summary(rule=None):
    """生成单条规则的预览文本（多条件 AND 拼接）。"""
    if rule is None:
        return "（未配置）"
    if not rule.get("enabled", True):
        return "（已停用）"
    conds = rule.get("conditions") or []
    if not conds:
        return "（无生效条件）"
    parts = [build_condition_summary(c) for c in conds]
    return " 且 ".join(parts)


def build_all_summary(cfg=None):
    """整体预览（给主窗口 tooltip / 空结果提示）。"""
    cfg = cfg or load_auto_read_rules_config()
    if not cfg.get("enabled", True):
        return "（自动已读已关闭）"
    active = [r for r in cfg.get("rules", []) if r.get("enabled", True)]
    if not active:
        return "（无启用的规则）"
    names = "、".join(r.get("name", "未命名") for r in active)
    base = "启用规则(%d)：%s" % (len(active), names)
    if cfg.get("exclude_units") and str(cfg.get("excluded_units", "")).strip():
        base += "；排除单位：%s" % str(cfg.get("excluded_units", "")).strip()
    return base


# --------------------------------------------------------------------------- 核心匹配
def _read_global_masks(df, cfg):
    """全局两个排除开关 → (实际>0 掩码, 单位不在清单 掩码, 单位清单文本)。

    生产匹配与只读命中预览共用这一份逻辑：两个开关若各写一遍，预览就会和真跑
    不一致（这正是设计稿 rules.html 改进点 4 点名的问题）。列不存在时返回 None，
    含义是「这个开关在这份数据上不起作用」，而不是「把所有行都排掉」。
    """
    cfg = cfg or {}
    actual_gt0 = None
    if cfg.get("exclude_unfed", False):
        col = _first_col(df, _ACTUAL_QTY_CANDIDATES)
        if col is not None:
            actual_gt0 = pd.to_numeric(df[col], errors="coerce") > 0
    unit_outside = None
    unit_text = str(cfg.get("excluded_units", "") or "").strip()
    if cfg.get("exclude_units", False):
        excluded = [u.strip().lower() for u in unit_text.replace("，", ",").split(",") if u.strip()]
        if excluded:
            col = _first_col(df, _UNIT_CANDIDATES)
            if col is not None:
                unit_outside = ~df[col].fillna("").astype(str).str.strip().str.lower().isin(excluded)
    return actual_gt0, unit_outside, unit_text


def _iter_read_rule_masks(df, cfg=None, include_disabled=False):
    """按列表顺序产出 ``(序号, 规则, 掩码)``，全局排除已按各规则的豁免标志叠加。

    序号是**列表位置**（1 起）：停用规则也占一个号、不重排，用户在规则列表里看到
    的行号必须和这里对得上。``include_disabled=False`` 时跳过停用规则 —— 生产口径
    就是只看启用规则；预览要回答「若启用会命中多少」，所以那里传 True。
    """
    if df is None or getattr(df, "empty", True) or "data_id" not in df.columns:
        return
    if cfg is None:
        cfg = load_auto_read_rules_config()
    if not cfg.get("enabled", True):
        return
    rules = cfg.get("rules", []) or []
    if not rules:
        return
    actual_gt0, unit_outside, _text = _read_global_masks(df, cfg)
    for idx, rule in enumerate(rules, 1):
        active = bool(rule.get("enabled", True))
        if not active and not include_disabled:
            continue
        m = _match_single_rule(df, rule)
        if actual_gt0 is not None and not rule.get("ignore_exclude_unfed", False):
            m = m & actual_gt0
        if unit_outside is not None and not rule.get("ignore_exclude_units", False):
            m = m & unit_outside
        yield idx, rule, m


def compute_auto_read_mask(df: pd.DataFrame, cfg=None):
    """返回 (union_mask, per_rule)。

    union_mask : bool Series（与 df.index 对齐），标记命中任意一条「启用」规则的行。
    per_rule   : list of (rule_dict, matched_mask)，matched_mask 为 bool Series。
                 用于上层在「未读」范围内统计每条规则命中数做反馈。

    - 多条规则 OR（并集）合并：**列表顺序不影响哪些行被读掉**，per_rule 只是逐条
      掩码，供上层在「未读」范围内统计每条命中数做反馈。
    - 数据缺失必要条件 → 该规则整条不匹配（保守）。
    - 全局「排除未投料 / 排除单位」默认生效，规则可用 ``ignore_exclude_unfed`` /
      ``ignore_exclude_units`` 豁免；实现见 :func:`_iter_read_rule_masks`。
    """
    empty = pd.Series(dtype=bool)  # 占位，真正缺失时按 df.index 重建
    if df is None or df.empty or "data_id" not in df.columns:
        return empty, []
    if cfg is None:
        cfg = load_auto_read_rules_config()
    if not cfg.get("enabled", True) or not (cfg.get("rules") or []):
        return pd.Series(False, index=df.index), []
    result_union = pd.Series(False, index=df.index)
    per_rule = []
    for _idx, rule, m in _iter_read_rule_masks(df, cfg):
        per_rule.append((rule, m))
        result_union = result_union | m
    return result_union, per_rule


# --------------------------------------------------------------------------- 只读命中预览
def match_read_rule_mask(df, rule, globals_=None):
    """单条规则的命中掩码（只读）。刻意**不看** ``enabled`` 与总开关。

    规则中心要对一条还没保存的草稿回答「这样改会命中多少行」，此时草稿的
    启用状态与总开关都不该参与；但全局两个排除开关要参与 —— 它们决定真跑时
    这些行会不会真的被已读，调用方把当前草稿的全局设置用 ``globals_`` 传进来。
    """
    if df is None or getattr(df, "empty", True) or "data_id" not in df.columns:
        return pd.Series(False, index=(df.index if df is not None else []))
    m = _match_single_rule(df, rule)
    actual_gt0, unit_outside, _text = _read_global_masks(df, globals_)
    if actual_gt0 is not None and not rule.get("ignore_exclude_unfed", False):
        m = m & actual_gt0
    if unit_outside is not None and not rule.get("ignore_exclude_units", False):
        m = m & unit_outside
    return m


def compute_read_rule_hit_counts(df, cfg=None):
    """逐条规则的只读命中统计，供规则中心左列展示。

    返回 ``[{'index','name','enabled','hits','net_hits'}]``：
      hits     —— 本条规则单独匹配的行数（停用规则照样给，含义是「若启用会命中多少」）
      net_hits —— 更靠前的启用规则**没**覆盖到的行数。注意自动已读是并集，被覆盖
                  并不影响结果（不像自动隔离那样「命中即停」），这个数字只用来让
                  用户看清「这条其实没在独自起作用」。
    总开关关闭、表不可用时全部为 0。
    """
    if cfg is None:
        cfg = load_auto_read_rules_config()
    rules = cfg.get("rules", []) or []
    master_on = bool(cfg.get("enabled", True))
    stats = {}
    if master_on:
        taken = set()
        for idx, rule, mask in _iter_read_rule_masks(df, cfg, include_disabled=True):
            ids = {str(u) for u in df.loc[mask, "data_id"].astype(str)}
            if rule.get("enabled", True):
                stats[idx] = (len(ids), len(ids - taken))
                taken |= ids
            else:
                stats[idx] = (len(ids), 0)
    out = []
    for idx, rule in enumerate(rules, 1):
        hits, net = stats.get(idx, (0, 0))
        out.append({
            "index": idx,
            "name": rule.get("name", "未命名规则"),
            "enabled": bool(rule.get("enabled", True)) and master_on,
            "hits": hits,
            "net_hits": net,
        })
    return out


def _read_sample_text(df, row):
    """样例文本：物料描述（定 X / 实 Y）—— 与表格底部「偏差合计」同一套数字写法。"""
    name_col = _first_col(df, CONDITION_TYPES["mat_name_contains"]["field_candidates"])
    actual_col = _first_col(df, _ACTUAL_QTY_CANDIDATES)
    quota_col = _first_col(df, ["数量-定额", "定额", "计划数量"])
    label = str(row[name_col]) if name_col else str(row.get("data_id", ""))
    actual = _fmt_qty(row[actual_col]) if actual_col else "—"
    quota = _fmt_qty(row[quota_col]) if quota_col else "—"
    return "%s（定 %s / 实 %s）" % (label, quota, actual)


def _fmt_qty(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return str(int(f)) if abs(f - int(f)) < 1e-9 else ("%.2f" % f)


def read_scope_mask(df):
    """生产落库范围掩码：**未读 且 不在隔离区**（与隔离区控制器的判据一致）。

    自动已读真跑时只动这个范围内的行（已读过的不重复处理，隔离区记录由
    「隔离区已读对账」专门管，规则中心不碰）。只读命中预览要说「真跑会读掉 N 条」，
    就必须按同一个口径算，否则预览报 6 条、真跑读 0 条。
    ``_read`` 列不存在（表还没分析过）时返回 None，由调用方决定怎么说这句诚实的话。
    """
    if df is None or getattr(df, "empty", True) or "data_id" not in df.columns:
        return None
    if "_read" not in df.columns:
        return None
    unread = df["_read"] == 0
    if "_quarantined" not in df.columns:
        return unread
    q = pd.to_numeric(df["_quarantined"], errors="coerce").fillna(0).astype(int)
    return unread & ~(q == 1)


def count_unfed_rows(df, mask=None):
    """``mask`` 范围内有几行「实际=0（未投料）」。

    实际数量列在这份数据里不存在时返回 **None**（无从判断），调用方此时不许把
    它当成 0 说成「不含未投料」。
    """
    if df is None or getattr(df, "empty", True):
        return None
    col = _first_col(df, _ACTUAL_QTY_CANDIDATES)
    if col is None:
        return None
    num = pd.to_numeric(df[col], errors="coerce")
    if mask is None:
        mask = pd.Series(True, index=df.index)
    return int((mask & num.notna() & (num == 0)).sum())


def describe_read_rule_hits(df, rule, globals_=None, samples=3):
    """本条（草稿）规则在真实主表上的命中情况，供预览条与悬浮提示。

    除了命中数/占比/样例，还必须回答一个红线问题：**这些行里有几条是
    「实际=0（未投料）」**。自动已读默认会把它们一起读掉（除非勾了「排除未投料」），
    所以预览把它单列出来，而不是让「命中 6 条」把这件事糊过去。

    字段口径：
      raw_hits     —— 只按条件算的命中数（还没过全局排除）
      hits         —— 过完全局排除后的命中数（真跑时「符合规则」的行数）
      pending_hits —— hits 里未读且不在隔离区的部分，即真跑**实际会读掉**的条数；
                      主表没有 ``_read`` 列时 ``pending_known`` 为 False，
                      调用方此时不许把 0 说成「一条都读不掉」
      unfed_hits / unfed_text —— 红线：hits 里有几条实际=0
      blocked_by   —— 哪个全局开关挡掉了行（没挡掉就不列）
      samples      —— 前 N 条样例文本
    """
    total = 0 if df is None else len(df)
    base = {"hits": 0, "total": total, "ratio": 0.0, "samples": [],
            "unfed_hits": 0, "unfed_text": "—", "blocked_by": [], "raw_hits": 0,
            "pending_hits": 0, "pending_known": False}
    if not total or "data_id" not in df.columns:
        return base
    raw = _match_single_rule(df, rule)
    base["raw_hits"] = int(raw.sum())
    m = match_read_rule_mask(df, rule, globals_)
    blocked = []
    actual_gt0, unit_outside, unit_text = _read_global_masks(df, globals_)
    if actual_gt0 is not None and not rule.get("ignore_exclude_unfed", False) \
            and int((raw & actual_gt0).sum()) < base["raw_hits"]:
        blocked.append("排除未投料（实际=0）")
    if unit_outside is not None and not rule.get("ignore_exclude_units", False) \
            and int((raw & unit_outside).sum()) < base["raw_hits"]:
        blocked.append("排除单位（清单：%s）" % (unit_text or "—"))
    base["blocked_by"] = blocked

    hits = int(m.sum())
    base["hits"] = hits
    base["ratio"] = (hits / float(total)) if total else 0.0
    unfed = count_unfed_rows(df, m)
    base["unfed_hits"] = unfed if unfed is not None else 0
    if unfed is None:
        base["unfed_text"] = "这份数据里没有「实际数量」列，未投料几条无从判断"
    elif unfed:
        base["unfed_text"] = "其中 %d 条实际=0（未投料）—— 现在会被一起自动已读" % unfed
    else:
        base["unfed_text"] = "不含实际=0（未投料）行"
    scope = read_scope_mask(df)
    base["pending_known"] = scope is not None
    base["pending_hits"] = int((m & scope).sum()) if scope is not None else hits
    if hits:
        base["samples"] = [_read_sample_text(df, row)
                           for _, row in df.loc[m].head(samples).iterrows()]
    return base



def _match_single_condition(df, cond):
    """单条条件的匹配，返回 bool 掩码。"""
    spec = CONDITION_TYPES.get(cond.get("type"), CONDITION_TYPES["dev_qty_eq"])
    field = _first_col(df, spec["field_candidates"])
    if field is None:
        return pd.Series(False, index=df.index)  # 无列 → 不匹配
    op = spec["op"]
    val = cond.get("params", {})
    col = df[field]

    if op == "eq":
        target = _to_num(val.get("value", 0))
        # v43.105 修复：缺失(NaN)不再被 fillna(0) 兜底当成 0 ——「偏差数量=0」类
        # 规则只对真实等于 0 的行生效，缺失行保守不命中（宁可留在未读）。
        num = pd.to_numeric(col, errors="coerce")
        return num.notna() & (num == target)
    if op == "startswith":
        s = col.fillna("").astype(str)
        raw = str(val.get("value", "")).strip()
        # 支持逗号分隔多值 OR（与 contains 行为一致）
        if "," in raw:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            if not items:
                return pd.Series(False, index=df.index)
            mask = pd.Series(False, index=df.index)
            for item in items:
                mask |= s.str.startswith(item, na=False)
            return mask
        return s.str.startswith(raw, na=False)
    if op == "contains":
        s = col.fillna("").astype(str)
        raw = str(val.get("value", "")).strip()
        # 支持逗号分隔多值 OR（与「物料编码属于/in」行为一致）
        if "," in raw:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            if not items:
                return pd.Series(False, index=df.index)
            mask = pd.Series(False, index=df.index)
            for item in items:
                mask |= s.str.contains(item, regex=False, na=False)
            return mask
        return s.str.contains(raw, regex=False, na=False)
    if op == "not_contains":
        s = col.fillna("").astype(str)
        raw = str(val.get("value", "")).strip()
        # 取反：不含任一关键字才命中。逗号分隔多值 = 且不含其中任一（NOT(含A OR 含B)）
        if "," in raw:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            if not items:
                return pd.Series(False, index=df.index)  # 未填值不误吞
            mask = pd.Series(False, index=df.index)
            for item in items:
                mask |= s.str.contains(item, regex=False, na=False)
            return ~mask
        return ~s.str.contains(raw, regex=False, na=False)
    if op == "in":
        items = [x.strip() for x in str(val.get("value", "")).split(",") if x.strip()]
        if not items:
            return pd.Series(False, index=df.index)
        s = col.fillna("").astype(str)
        return s.isin(items)
    if op == "eq_str":
        s = col.fillna("").astype(str)
        return s == str(val.get("value", "")).strip()
    if op == "range":
        num = pd.to_numeric(col, errors="coerce")
        mn = _to_num(val.get("min", 0))
        mx = _to_num(val.get("max", 1))
        # 开区间 (min, max)，不含端点
        return (num > mn) & (num < mx)
    if op == "gt":
        target = _to_num(val.get("value", 0))
        return pd.to_numeric(col, errors="coerce") > target
    if op == "lt":
        target = _to_num(val.get("value", 0))
        return pd.to_numeric(col, errors="coerce") < target
    if op == "gte":
        target = _to_num(val.get("value", 0))
        return pd.to_numeric(col, errors="coerce") >= target
    if op == "lte":
        target = _to_num(val.get("value", 0))
        return pd.to_numeric(col, errors="coerce") <= target
    return pd.Series(False, index=df.index)


def _match_single_rule(df, rule):
    """单条规则（多条件 AND）的匹配，返回 bool 掩码。"""
    conds = rule.get("conditions") or []
    if not conds:
        return pd.Series(False, index=df.index)
    # 所有条件 AND：缺列 = 该条件 False → 整条 False（保守）
    mask = pd.Series(True, index=df.index)
    for c in conds:
        mask = mask & _match_single_condition(df, c)
    return mask
