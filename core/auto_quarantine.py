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


CONFIG_PATH = _resolve_config_path("auto_quarantine_config.json")

DEFAULT_RULE = {
    "name": "包材箱类负损",
    "enabled": True,
    "exclude_alt": True,
    "category_required": True,
    "category_value": "包材",
    "name_keywords": ["箱", "手包袋"],
    "negative_loss_required": True,
    # —— 新增条件（默认关闭 / 空值，向后兼容旧配置）——
    "dev_rate_required": False,      # 是否要求偏差率落在范围
    "dev_rate_min": 10,              # 偏差率下限（开区间，不含端点）
    "dev_rate_max": 100,             # 偏差率上限
    "mat_code_prefix": "",           # 物料编码前缀（逗号分隔多值 OR；空=不限制）
    "workshop_required": False,      # 是否限定车间
    "workshop_value": "",            # 车间取值（空=不限制）
    "remark_mode": "off",            # 备注要求：off / has（有备注）/ none（无备注）
    "name_exclude_keywords": "",     # 物料名称不含（逗号分隔；空=不限制）
    "dev_qty_required": False,       # 是否要求偏差数量落在范围
    "dev_qty_min": 0,                # 偏差数量下限（开区间）
    "dev_qty_max": 1,                # 偏差数量上限
}

DEFAULT_CONFIG = {"enabled": True, "rules": [dict(DEFAULT_RULE)]}

# 单条规则的全部合法字段
_RULE_FIELDS = (
    "name", "enabled", "exclude_alt", "category_required",
    "category_value", "name_keywords", "negative_loss_required",
    "dev_rate_required", "dev_rate_min", "dev_rate_max",
    "mat_code_prefix", "workshop_required", "workshop_value",
    "remark_mode", "name_exclude_keywords",
    "dev_qty_required", "dev_qty_min", "dev_qty_max",
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
    # 新数字字段兜底为 float（JSON 中可能以字符串存储）
    for _nf in ("dev_rate_min", "dev_rate_max", "dev_qty_min", "dev_qty_max"):
        try:
            r[_nf] = float(r.get(_nf, DEFAULT_RULE[_nf]))
        except (TypeError, ValueError):
            r[_nf] = float(DEFAULT_RULE[_nf])
    # 备注模式仅接受合法三态
    if str(r.get("remark_mode", "off")).strip() not in ("off", "has", "none"):
        r["remark_mode"] = "off"
    return r


def load_auto_quarantine_config():
    """读取配置，兼容旧单条格式，返回 {'enabled': bool, 'rules': [规则...]}。

    读取优先级：① 持久化文件 CONFIG_PATH → ② 打包内置默认（_bundle_config_path，
    首次启动 / 持久化文件被删时兜底）→ ③ 代码内 DEFAULT_CONFIG。
    """
    cfg = {"enabled": DEFAULT_CONFIG["enabled"], "rules": [dict(DEFAULT_RULE)]}
    try:
        src = CONFIG_PATH
        if not os.path.exists(src):
            # 持久化文件不存在 → 回退打包内置默认（仅首次启动或文件被删）
            bundle = _bundle_config_path("auto_quarantine_config.json")
            if bundle and os.path.exists(bundle):
                src = bundle
        if os.path.exists(src):
            with open(src, "r", encoding="utf-8") as f:
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
    except Exception as e:
        logging.warning("自动隔离规则配置加载失败: %s", e)
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
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, CONFIG_PATH)
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
    # —— 新增条件预览 ——
    if rule.get("dev_rate_required", False):
        parts.append("偏差率∈(%s,%s)" % (rule.get("dev_rate_min"), rule.get("dev_rate_max")))
    prefix = [x.strip() for x in str(rule.get("mat_code_prefix", "")).replace("，", ",").split(",") if x.strip()]
    if prefix:
        parts.append("编码前缀（%s）" % "、".join(prefix))
    if rule.get("workshop_required", False) and str(rule.get("workshop_value", "")).strip():
        parts.append("车间=%s" % rule.get("workshop_value"))
    mode = str(rule.get("remark_mode", "off")).strip()
    if mode == "has":
        parts.append("有备注")
    elif mode == "none":
        parts.append("无备注")
    ex = [x.strip() for x in str(rule.get("name_exclude_keywords", "")).replace("，", ",").replace("、", ",").split(",") if x.strip()]
    if ex:
        parts.append("名称不含（%s）" % "、".join(ex))
    if rule.get("dev_qty_required", False):
        parts.append("偏差数量∈(%s,%s)" % (rule.get("dev_qty_min"), rule.get("dev_qty_max")))
    if not parts:
        return "（未配置任何条件）"
    return " · ".join(parts)


def build_rule_reason(rule=None, idx=None):
    """生成写进隔离原因列的单条规则文本。

    idx: 规则在配置列表中的 1-based 序号（与「⚙ 自动隔离规则」对话框的
         1. 2. 3. 编号一致，含已停用的规则也占位）。传入时返回简短形式
         '自动规则[第N条]'，隔离区列宽更友好；不传则回退带名称+条件的
         长文本（向后兼容 / 非自动隔离场景）。
    """
    if idx is not None:
        try:
            return "自动规则[第%d条]" % int(idx)
        except (TypeError, ValueError):
            pass
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
    rules = cfg.get("rules", [])
    if not rules:
        return {}

    alt_col = _first_col(df, ["是否替代料", "替代料", "is_alt"])
    cat_col = _first_col(df, ["物料分类", "物料大类", "物料类型", "组件物料类型描述"])
    name_col = _first_col(df, ["组件物料描述", "物料名称", "物料描述", "material_name"])
    actual_col = _first_col(df, ["数量-实际", "实际", "实际数量", "数量 - 实际", "actual"])
    quota_col = _first_col(df, ["数量-定额", "定额", "定额数量", "数量 - 定额", "quota"])
    # —— 新增条件所用列探测 ——
    dev_rate_col = _first_col(df, ["偏差率(%)", "偏差率", "偏差率%"])
    mat_code_col = _first_col(df, ["物料编码", "组件物料号", "物料号"])
    workshop_col = _first_col(df, ["车间", "工厂车间", "生产车间", "work_shop", "车间号"])
    remark_col = _first_col(df, ["备注", "备注原因", "remark", "备注说明"])
    dev_qty_col = _first_col(df, ["偏差数量", "偏差量", "差异数量"])

    result = {}  # data_id -> reason（只记靠前规则）
    for idx, rule in enumerate(rules, 1):
        if not rule.get("enabled", True):
            continue
        mask = _match_single_rule(
            df, rule, alt_col, cat_col, name_col, actual_col, quota_col,
            dev_rate_col, mat_code_col, workshop_col, remark_col, dev_qty_col,
        )
        for uid in df.loc[mask, "data_id"].astype(str):
            if uid not in result:  # 已被靠前规则命中的不再覆盖
                result[uid] = build_rule_reason(rule, idx)
    return result


def _match_single_rule(df, rule, alt_col, cat_col, name_col, actual_col, quota_col,
                       dev_rate_col=None, mat_code_col=None, workshop_col=None,
                       remark_col=None, dev_qty_col=None):
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

    # 5. 偏差率范围（开区间，不含端点；无列 → 不匹配）
    if rule.get("dev_rate_required", False):
        if dev_rate_col:
            rate = pd.to_numeric(df[dev_rate_col], errors="coerce")
            mn = float(rule.get("dev_rate_min", 0))
            mx = float(rule.get("dev_rate_max", 100))
            m_rate = rate.notna() & (rate > mn) & (rate < mx)
        else:
            m_rate = pd.Series(False, index=df.index)
    else:
        m_rate = pd.Series(True, index=df.index)

    # 6. 物料编码前缀（逗号分隔多值 OR；空 → 不限制）
    prefix = str(rule.get("mat_code_prefix", "")).strip()
    if prefix:
        if mat_code_col:
            s = df[mat_code_col].astype(str).fillna("")
            items = [x.strip() for x in prefix.replace("，", ",").split(",") if x.strip()]
            if items:
                m_prefix = pd.Series(False, index=df.index)
                for it in items:
                    m_prefix |= s.str.startswith(it, na=False)
            else:
                m_prefix = pd.Series(True, index=df.index)
        else:
            m_prefix = pd.Series(False, index=df.index)  # 开着无列 → 不匹配
    else:
        m_prefix = pd.Series(True, index=df.index)

    # 7. 车间限定（填了才限制；开着没填 → 不限制）
    if rule.get("workshop_required", False):
        if workshop_col:
            val = str(rule.get("workshop_value", "")).strip()
            if val:
                m_ws = df[workshop_col].astype(str).fillna("").str.strip() == val
            else:
                m_ws = pd.Series(True, index=df.index)
        else:
            m_ws = pd.Series(False, index=df.index)  # 开着无列 → 不匹配
    else:
        m_ws = pd.Series(True, index=df.index)

    # 8. 是否备注（has=有备注 / none=无备注；无列 → 不匹配，保守）
    mode = str(rule.get("remark_mode", "off")).strip()
    if mode in ("has", "none"):
        if remark_col:
            filled = df[remark_col].astype(str).fillna("").str.strip() != ""
            m_remark = filled if mode == "has" else ~filled
        else:
            m_remark = pd.Series(False, index=df.index)
    else:
        m_remark = pd.Series(True, index=df.index)

    # 9. 偏差数量范围（开区间；无列 → 不匹配）
    if rule.get("dev_qty_required", False):
        if dev_qty_col:
            q = pd.to_numeric(df[dev_qty_col], errors="coerce")
            mn = float(rule.get("dev_qty_min", 0))
            mx = float(rule.get("dev_qty_max", 1))
            m_dq = q.notna() & (q > mn) & (q < mx)
        else:
            m_dq = pd.Series(False, index=df.index)
    else:
        m_dq = pd.Series(True, index=df.index)

    # 10. 名称不含（逗号分隔多值；任一命中即排除，即 NOT(含A OR 含B)）
    ex = [str(k).strip() for k in
          str(rule.get("name_exclude_keywords", "")).replace("，", ",").replace("、", ",").split(",")
          if str(k).strip()]
    if ex:
        if name_col:
            name_str = df[name_col].astype(str).fillna("")
            m_ex = pd.Series(False, index=df.index)
            for kw in ex:
                m_ex = m_ex | name_str.str.contains(kw, regex=False)
            m_ex = ~m_ex
        else:
            m_ex = pd.Series(False, index=df.index)  # 开着无列 → 不匹配
    else:
        m_ex = pd.Series(True, index=df.index)  # 没填 → 不限制

    return m_alt & m_cat & m_name & m_qty & m_rate & m_prefix & m_ws & m_remark & m_dq & m_ex
