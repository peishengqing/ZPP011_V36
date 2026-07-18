# -*- coding: utf-8 -*-
"""
自动移入隔离区 — 业务规则（可配置版）

规则通过 config/auto_quarantine_config.json 配置，本模块每次执行实时读取，无需重启。
配置字段：
  - enabled              总开关；False 则完全不隔离
  - exclude_alt          是否排除替代料
  - category_required    是否限定物料类别
  - category_value       类别取值（默认「包材」）
  - name_keywords        物料名称包含任一关键词即命中（字面量匹配，非正则）
  - negative_loss_required 是否要求负损（实际>0 且 实际<定额）

匹配语义（关键）：
  - 任一条件「关掉 / 没填」→ 该项视为不限制（True）
  - 条件「开着，但数据里没有对应列」→ 该项不匹配（False），保守不误伤
  - 例外：exclude_alt 开着但无替代料列时 → True（无法识别就不排除，放行避免误杀）

说明：
  - 隔离区是引用模式（仅存 data_id），本模块只负责返回「应隔离的 data_id 集合」，
    真正的 add_quarantine / 列标记由 GUI 层完成，保持与手动移入一致。
  - 列名在不同 SAP 导出可能不同，故用候选名依次探测，缺失则对应条件判为不匹配。
"""

import json
import os

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_HERE, "..", "config", "auto_quarantine_config.json")

DEFAULT_CONFIG = {
    "enabled": True,
    "exclude_alt": True,
    "category_required": True,
    "category_value": "包材",
    "name_keywords": ["箱", "手包袋"],
    "negative_loss_required": True,
}


def _first_col(df: pd.DataFrame, candidates):
    """返回 df 中第一个存在的候选列名，都不存在则返回 None。"""
    for c in candidates:
        if c in df.columns:
            return c
    return None


# --------------------------------------------------------------------------- 配置读写
def load_auto_quarantine_config():
    """读取配置，缺失/损坏时回退默认配置。"""
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                cfg.update({k: v for k, v in user.items() if k in DEFAULT_CONFIG})
    except Exception:
        pass
    return cfg


def save_auto_quarantine_config(cfg):
    """合并默认配置后写回文件，返回最终生效配置。"""
    merged = dict(DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        merged.update({k: v for k, v in cfg.items() if k in DEFAULT_CONFIG})
    # 基础校验：关键词去空
    merged["name_keywords"] = [
        str(k).strip() for k in (merged.get("name_keywords") or []) if str(k).strip()
    ]
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged


def build_rule_summary(cfg=None):
    """生成给人看的规则预览文本。"""
    cfg = cfg or DEFAULT_CONFIG
    if not cfg.get("enabled", True):
        return "（自动隔离已关闭）"
    parts = []
    if cfg.get("exclude_alt", True):
        parts.append("非替代料")
    if cfg.get("category_required", True):
        parts.append("属于「%s」" % str(cfg.get("category_value", "包材")).strip())
    kws = [str(k).strip() for k in (cfg.get("name_keywords") or []) if str(k).strip()]
    if kws:
        parts.append("名称含「%s」" % "/".join(kws))
    if cfg.get("negative_loss_required", True):
        parts.append("实际>0 且 实际<定额")
    if not parts:
        return "（未配置任何条件）"
    return " · ".join(parts)


def build_rule_reason(cfg=None):
    """生成写进隔离原因列的文本。"""
    return "自动规则:" + build_rule_summary(cfg).replace(" · ", "·")


# --------------------------------------------------------------------------- 核心匹配
def compute_auto_quarantine_ids(df: pd.DataFrame, cfg=None) -> set:
    """根据配置返回应移入隔离区的 data_id 集合（字符串）。无匹配返回空集。"""
    if df is None or df.empty or "data_id" not in df.columns:
        return set()
    if cfg is None:
        cfg = load_auto_quarantine_config()
    if not cfg.get("enabled", True):
        return set()

    alt_col = _first_col(df, ["是否替代料", "替代料", "is_alt"])
    cat_col = _first_col(df, ["物料分类", "物料大类", "物料类型", "组件物料类型描述"])
    name_col = _first_col(df, ["组件物料描述", "物料名称", "物料描述", "material_name"])
    actual_col = _first_col(df, ["数量-实际", "实际", "实际数量", "数量 - 实际", "actual"])
    quota_col = _first_col(df, ["数量-定额", "定额", "定额数量", "数量 - 定额", "quota"])

    # 1. 排除替代料
    if cfg.get("exclude_alt", True):
        if alt_col:
            m_alt = df[alt_col].astype(str).str.strip() != "是"
        else:
            m_alt = pd.Series(True, index=df.index)  # 无列则放行
    else:
        m_alt = pd.Series(True, index=df.index)

    # 2. 类别限定
    if cfg.get("category_required", True):
        if cat_col:
            val = str(cfg.get("category_value", "包材")).strip()
            m_cat = df[cat_col].astype(str).str.strip() == val
        else:
            m_cat = pd.Series(False, index=df.index)  # 开着无列 → 不匹配
    else:
        m_cat = pd.Series(True, index=df.index)

    # 3. 名称关键词（字面量匹配，避免正则特殊字符干扰）
    kws = [str(k).strip() for k in (cfg.get("name_keywords") or []) if str(k).strip()]
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
    if cfg.get("negative_loss_required", True):
        if actual_col and quota_col:
            actual = pd.to_numeric(df[actual_col], errors="coerce")
            quota = pd.to_numeric(df[quota_col], errors="coerce")
            m_qty = actual.notna() & (actual > 0) & quota.notna() & (actual < quota)
        else:
            m_qty = pd.Series(False, index=df.index)  # 开着无列 → 不匹配
    else:
        m_qty = pd.Series(True, index=df.index)

    mask = m_alt & m_cat & m_name & m_qty
    return set(df.loc[mask, "data_id"].astype(str).tolist())
