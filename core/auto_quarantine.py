# -*- coding: utf-8 -*-
"""
自动移入隔离区 — 业务规则（可配置 · 多规则版）

规则通过 config/auto_quarantine_config.json 配置，本模块每次执行实时读取，无需重启。
配置结构：
  {
    "enabled": true,                 # 总开关；False 则完全不隔离
    "rules": [                       # 规则列表，多条规则 OR 并存
      {
        "name": "包材箱类负损",       # 规则名称（写入隔离原因列，便于追溯）
        "enabled": true,             # 单条规则开关
        "exclude_alt": true,         # 是否排除替代料
        "category_required": true,   # 是否限定物料类别
        "category_value": "包材",     # 类别取值
        "name_keywords": ["箱", "手包袋"],  # 物料名称包含任一关键词即命中（字面量匹配）
        "negative_loss_required": true      # 是否要求负损（实际>0 且 实际<定额）
      }
    ]
  }

匹配语义（关键）：
  - 多条规则之间为 OR：一条记录命中任意一条「启用」的规则即进隔离区。
  - 同一条记录命中多条规则时，隔离原因取列表顺序靠前的那条规则（列表顺序即优先级）。
  - 单条规则内部各条件为 AND（与旧版一致）。
  - 任一条件「关掉 / 没填」→ 该项视为不限制（True）
  - 条件「开着，但数据里没有对应列」→ 该项不匹配（False），保守不误伤
  - 例外：exclude_alt 开着但无替代料列时 → True（无法识别就不排除，放行避免误杀）

向后兼容：旧版单条配置（顶层直接是 enabled/name_keywords...）会在 load 时自动包成 rules[0]。

说明：
  - 隔离区是引用模式（仅存 data_id），本模块只负责返回「应隔离的 data_id → 原因」映射，
    真正的 add_quarantine / 列标记由 GUI 层完成，保持与手动移入一致。
  - 列名在不同 SAP 导出可能不同，故用候选名依次探测，缺失则对应条件判为不匹配。
"""

import json
import os

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_HERE, "..", "config", "auto_quarantine_config.json")

DEFAULT_RULE = {
    "name": "包材箱类负损",
    "enabled": True,
    "exclude_alt": True,
    "category_required": True,
    "category_value": "包材",
    "name_keywords": ["箱", "手包袋"],
    "negative_loss_required": True,
}

DEFAULT_CONFIG = {"enabled": True, "rules": [dict(DEFAULT_RULE)]}

# 单条规则的全部合法字段
_RULE_FIELDS = (
    "name", "enabled", "exclude_alt", "category_required",
    "category_value", "name_keywords", "negative_loss_required",
)


def _first_col(df: pd.DataFrame, candidates):
    """返回 df 中第一个存在的候选列名，都不存在则返回 None。"""
    for c in candidates:
        if c in df.columns:
            return c
    return None


# --------------------------------------------------------------------------- 配置读写
def _normalize_rule(rule):
    """补齐字段，保证每条规则都有完整键。"""
    r = dict(DEFAULT_RULE)
    if isinstance(rule, dict):
        for k in _RULE_FIELDS:
            if k in rule:
                r[k] = rule[k]
        nm = rule.get("name")
        if nm not in (None, ""):
            r["name"] = str(nm).strip()  # 否则保留 DEFAULT_RULE 的默认名
    r["name_keywords"] = [
        str(k).strip() for k in (r.get("name_keywords") or []) if str(k).strip()
    ]
    r["category_value"] = str(r.get("category_value") or "包材").strip() or "包材"
    return r


def load_auto_quarantine_config():
    """读取配置，兼容旧单条格式，返回 {'enabled': bool, 'rules': [规则...]}。"""
    cfg = {"enabled": DEFAULT_CONFIG["enabled"], "rules": [dict(DEFAULT_RULE)]}
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                if "rules" in user and isinstance(user["rules"], list):
                    # 新格式
                    cfg["enabled"] = bool(user.get("enabled", True))
                    rules = [_normalize_rule(r) for r in user["rules"] if isinstance(r, dict)]
                    cfg["rules"] = rules if rules else [dict(DEFAULT_RULE)]
                else:
                    # 旧单条格式：包成 rules[0]
                    old = _normalize_rule(user)
                    if old["name"] == "未命名规则":
                        old["name"] = "包材箱类负损"
                    cfg["rules"] = [old]
    except Exception:
        pass
    return cfg


def save_auto_quarantine_config(cfg):
    """合并默认配置后写回文件，返回最终生效配置（{'enabled', 'rules'}）。"""
    merged = {
        "enabled": bool(cfg.get("enabled", True)),
        "rules": [_normalize_rule(r) for r in (cfg.get("rules") or [])],
    }
    if not merged["rules"]:
        merged["rules"] = [dict(DEFAULT_RULE)]
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged


# --------------------------------------------------------------------------- 文案生成
def build_rule_summary(rule=None):
    """生成单条规则的预览文本。"""
    rule = rule or DEFAULT_RULE
    if not rule.get("enabled", True):
        return "（已停用）"
    parts = []
    if rule.get("exclude_alt", True):
        parts.append("非替代料")
    if rule.get("category_required", True):
        parts.append("属于「%s」" % str(rule.get("category_value", "包材")).strip())
    kws = [str(k).strip() for k in (rule.get("name_keywords") or []) if str(k).strip()]
    if kws:
        parts.append("名称含「%s」" % "/".join(kws))
    if rule.get("negative_loss_required", True):
        parts.append("实际>0 且 实际<定额")
    if not parts:
        return "（未配置任何条件）"
    return " · ".join(parts)


def build_rule_reason(rule=None):
    """生成写进隔离原因列的单条规则文本（带规则名）。"""
    rule = rule or DEFAULT_RULE
    name = str(rule.get("name") or "未命名规则").strip() or "未命名规则"
    return "自动规则[%s]:%s" % (name, build_rule_summary(rule).replace(" · ", "·"))


def build_all_summary(cfg=None):
    """整体预览（给主窗口 tooltip / 空结果提示）。"""
    cfg = cfg or load_auto_quarantine_config()
    if not cfg.get("enabled", True):
        return "（自动隔离已关闭）"
    active = [r for r in cfg.get("rules", []) if r.get("enabled", True)]
    if not active:
        return "（无启用的规则）"
    names = "、".join(r.get("name", "未命名") for r in active)
    return "启用规则(%d)：%s" % (len(active), names)


# --------------------------------------------------------------------------- 核心匹配
def compute_auto_quarantine_ids(df: pd.DataFrame, cfg=None) -> dict:
    """返回 {data_id: 该条命中的规则 reason 文本}。

    - 多条规则 OR 合并；同一条记录命中多条时取列表靠前的规则（优先级）。
    - 无匹配返回空 dict。
    """
    if df is None or df.empty or "data_id" not in df.columns:
        return {}
    if cfg is None:
        cfg = load_auto_quarantine_config()
    if not cfg.get("enabled", True):
        return {}
    rules = [r for r in cfg.get("rules", []) if r.get("enabled", True)]
    if not rules:
        return {}

    alt_col = _first_col(df, ["是否替代料", "替代料", "is_alt"])
    cat_col = _first_col(df, ["物料分类", "物料大类", "物料类型", "组件物料类型描述"])
    name_col = _first_col(df, ["组件物料描述", "物料名称", "物料描述", "material_name"])
    actual_col = _first_col(df, ["数量-实际", "实际", "实际数量", "数量 - 实际", "actual"])
    quota_col = _first_col(df, ["数量-定额", "定额", "定额数量", "数量 - 定额", "quota"])

    result = {}  # data_id -> reason（只记靠前规则）
    for rule in rules:
        mask = _match_single_rule(df, rule, alt_col, cat_col, name_col, actual_col, quota_col)
        for uid in df.loc[mask, "data_id"].astype(str):
            if uid not in result:  # 已被靠前规则命中的不再覆盖
                result[uid] = build_rule_reason(rule)
    return result


def _match_single_rule(df, rule, alt_col, cat_col, name_col, actual_col, quota_col):
    """单条规则的 AND 匹配，返回 bool 掩码。"""
    # 1. 排除替代料
    if rule.get("exclude_alt", True):
        if alt_col:
            m_alt = df[alt_col].astype(str).str.strip() != "是"
        else:
            m_alt = pd.Series(True, index=df.index)  # 无列则放行
    else:
        m_alt = pd.Series(True, index=df.index)

    # 2. 类别限定
    if rule.get("category_required", True):
        if cat_col:
            val = str(rule.get("category_value", "包材")).strip()
            m_cat = df[cat_col].astype(str).str.strip() == val
        else:
            m_cat = pd.Series(False, index=df.index)  # 开着无列 → 不匹配
    else:
        m_cat = pd.Series(True, index=df.index)

    # 3. 名称关键词（字面量匹配，避免正则特殊字符干扰）
    kws = [str(k).strip() for k in (rule.get("name_keywords") or []) if str(k).strip()]
    if kws:
        if name_col:
            name_str = df[name_col].astype(str).fillna("")
            m_name = pd.Series(False, index=df.index)
            for kw in kws:
                m_name = m_name | name_str.str.contains(kw, regex=False)
        else:
            m_name = pd.Series(False, index=df.index)  # 开着无列 → 不匹配
    else:
        m_name = pd.Series(True, index=df.index)  # 没填关键词 → 不限制

    # 4. 负损
    if rule.get("negative_loss_required", True):
        if actual_col and quota_col:
            actual = pd.to_numeric(df[actual_col], errors="coerce")
            quota = pd.to_numeric(df[quota_col], errors="coerce")
            m_qty = actual.notna() & (actual > 0) & quota.notna() & (actual < quota)
        else:
            m_qty = pd.Series(False, index=df.index)  # 开着无列 → 不匹配
    else:
        m_qty = pd.Series(True, index=df.index)

    return m_alt & m_cat & m_name & m_qty
