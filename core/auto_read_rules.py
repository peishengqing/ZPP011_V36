# -*- coding: utf-8 -*-
"""
自动已读 — 业务规则（可配置 · 多规则版）

规则通过 config/auto_read_rules.json 配置，本模块每次执行实时读取，无需重启。
配置结构：
  {
    "enabled": true,                 # 总开关；False 则完全不自动已读
    "rules": [                       # 规则列表，多条规则 OR 并存
      {
        "name": "偏差数量=0",         # 规则名称（写入已读原因列便于追溯）
        "enabled": true,             # 单条规则开关
        "type": "dev_qty_eq",        # 条件类型（见 CONDITION_TYPES）
        "params": {"value": 0}       # 条件参数（按 type 取值）
      },
      {
        "name": "物料600开头",
        "enabled": true,
        "type": "mat_code_prefix",
        "params": {"value": "600"}
      }
    ]
  }

匹配语义（关键）：
  - 多条规则之间为 OR：一条记录命中任意一条「启用」的规则即自动已读。
  - 同一条记录命中多条规则时，已读原因取列表顺序靠前的那条规则（列表顺序即优先级）。
  - 单条规则即一个条件（自动已读场景下条件足够清晰，无需 AND 组合）。
  - 条件「开着，但数据里没有对应列」→ 该项不匹配（False），保守不误伤。

向后兼容：旧版单条配置（顶层直接是 enabled/name/type/params...）会在 load 时自动包成 rules[0]。

说明：
  - 本模块只负责返回「应自动已读的 data_id → 原因」映射与命中掩码，
    真正的 mark_read_batch / 列标记由 GUI 层完成，保持与手动标记已读一致。
  - 列名在不同 SAP 导出可能不同，故用候选名依次探测，缺失则对应条件判为不匹配。
"""

import json
import logging
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))


def _resolve_config_path(filename):
    """解析配置文件绝对路径。

    源码模式：使用项目内 config/ 目录（与源码配置同处），__file__ 稳定。
    exe 模式（PyInstaller onefile 每次解压到随机临时目录 _MEIxxxx）：
    __file__ 不可信，强制指向项目真实 config 目录，与 column_widths.json、
    auto_quarantine_config.json 等真实配置同处，避免写进临时解压目录或 dist
    导致重启后规则丢失。可用环境变量 ZPP011_PROJECT_ROOT 覆盖项目根。
    """
    if getattr(sys, "frozen", False):
        # PyInstaller onefile 解压到临时目录 _MEIxxxx，config/ 在其中的相对路径
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass is not None:
            return os.path.join(meipass, "config", filename)
        # 回退：exe 所在目录的 config/（便携模式 / 未解压）
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        fallback = os.path.join(exe_dir, "config", filename)
        if os.path.exists(fallback):
            return fallback
        # 最后：环境变量覆盖
        project_root = os.environ.get("ZPP011_PROJECT_ROOT")
        if project_root is not None:
            return os.path.join(project_root, "config", filename)
        # 实在找不到才报错
        raise RuntimeError(
            f"exe 模式下无法定位 config/ 目录，已尝试：\n"
            f"  1. sys._MEIPASS\\config\\{filename}\n"
            f"  2. exe 同目录\\config\\{filename}\n"
            f"  3. 环境变量 ZPP011_PROJECT_ROOT\n"
            "请确认 config/ 目录与 exe 同处，或设置 ZPP011_PROJECT_ROOT。"
        )
    return os.path.join(_HERE, "..", "config", filename)


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
    """读取配置，兼容旧单条格式，返回 {'enabled': bool, 'rules': [规则...]}。"""
    cfg = {"enabled": DEFAULT_CONFIG["enabled"], "rules": [dict(r) for r in DEFAULT_RULES],
           "exclude_unfed": DEFAULT_CONFIG.get("exclude_unfed", False),
           "exclude_units": DEFAULT_CONFIG.get("exclude_units", False),
           "excluded_units": DEFAULT_CONFIG.get("excluded_units", "")}
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
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
        return "%s「%s」" % (spec["label"], str(val.get("value", "")).strip())
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
def compute_auto_read_mask(df: pd.DataFrame, cfg=None):
    """返回 (union_mask, per_rule)。

    union_mask : bool Series（与 df.index 对齐），标记命中任意一条「启用」规则的行。
    per_rule   : list of (rule_dict, matched_mask)，matched_mask 为 bool Series。
                 用于上层在「未读」范围内统计每条规则命中数做反馈。

    - 多条规则 OR 合并；同一条记录命中多条时取列表靠前的规则（优先级）。
    - 数据缺失必要条件 → 该规则整条不匹配（保守）。
    """
    empty = pd.Series(dtype=bool)  # 占位，真正缺失时按 df.index 重建
    if df is None or df.empty or "data_id" not in df.columns:
        return empty, []
    if cfg is None:
        cfg = load_auto_read_rules_config()
    if not cfg.get("enabled", True):
        return pd.Series(False, index=df.index), []
    rules = cfg.get("rules", [])
    if not rules:
        return pd.Series(False, index=df.index), []

    # 全局「排除未投料（实际数量=0）」开关：开了之后，默认把实际=0 的行挡在自动已读外；
    # 但若某条规则显式 ignore_exclude_unfed=True（如 600 规则），则该规则不受此开关影响。
    exclude_unfed = bool(cfg.get("exclude_unfed", False))
    actual_gt0 = None
    if exclude_unfed:
        actual_col = _first_col(df, _ACTUAL_QTY_CANDIDATES)
        if actual_col is not None:
            actual_gt0 = pd.to_numeric(df[actual_col], errors="coerce") > 0

    # 全局「排除单位」开关：开了且清单非空后，默认把单位命中清单的行挡在自动已读外；
    # 若某条规则显式 ignore_exclude_units=True，则该规则不受此开关影响。
    # 清单支持中英文逗号分隔、自动去空格、忽略大小写（如 "G,个" / "G，个"）。
    exclude_units = bool(cfg.get("exclude_units", False))
    excluded_units = [u.strip().lower() for u in
                      str(cfg.get("excluded_units", "")).replace("，", ",").split(",") if u.strip()]
    unit_outside = None
    if exclude_units and excluded_units:
        unit_col = _first_col(df, _UNIT_CANDIDATES)
        if unit_col is not None:
            unit_outside = ~df[unit_col].astype(str).fillna("").str.strip().str.lower().isin(excluded_units)

    result_union = pd.Series(False, index=df.index)
    per_rule = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        m = _match_single_rule(df, rule)
        if exclude_unfed and actual_gt0 is not None and not rule.get("ignore_exclude_unfed", False):
            m = m & actual_gt0
        if exclude_units and unit_outside is not None and not rule.get("ignore_exclude_units", False):
            m = m & unit_outside
        per_rule.append((rule, m))
        result_union = result_union | m
    return result_union, per_rule


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
        return pd.to_numeric(col, errors="coerce").fillna(0) == target
    if op == "startswith":
        s = col.astype(str).fillna("")
        return s.str.startswith(str(val.get("value", "")).strip(), na=False)
    if op == "contains":
        s = col.astype(str).fillna("")
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
        s = col.astype(str).fillna("")
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
        s = col.astype(str).fillna("")
        return s.isin(items)
    if op == "eq_str":
        s = col.astype(str).fillna("")
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
