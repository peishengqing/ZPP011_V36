# -*- coding: utf-8 -*-
"""
隔离区状态管理
使用 SQLite 持久化存储（与 read_status 共用同一数据库文件）

设计核心：引用模式
- 只存 data_id（即 uid），不存数据副本
- 隔离行的实际数量/状态实时从主表读取
- 因此主表某行被改（如 实际数量 500 -> 550）后重新导入，隔离区记录自动同步，无需额外代码
"""
import sqlite3
import os
import math
from datetime import datetime
from typing import List, Dict, Set

from core.read_status import DB_PATH


def _get_conn():
    """获取数据库连接，自动创建隔离区表结构（与 read_status 共用同一 DB 文件）

    表结构向后兼容：reason_basis 为 v42.37 新增的「入区判定依据快照」列，
    旧行该列为空字符串，复核时降级按 reason 文本判断。
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quarantine_records (
            uid TEXT PRIMARY KEY,
            reason TEXT DEFAULT '',
            quarantined_at TIMESTAMP,
            restored_at TIMESTAMP NULL,
            reason_basis TEXT DEFAULT ''
        )
    """)
    # 旧库兼容：缺列则补加（ALTER TABLE 幂等于捕获异常）
    try:
        conn.execute("ALTER TABLE quarantine_records ADD COLUMN reason_basis TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE quarantine_records ADD COLUMN exempted BOOL DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # 已存在
    return conn


def add_quarantine(uid: str, reason: str = "", basis: str = ""):
    """将一条记录移入隔离区（uid 即 data_id）。已存在则刷新为活跃状态。

    basis: 入区判定依据快照（如「负损:实际>0且实际<定额」「自动规则[第1条]」
           「手动:财务要求隔离」），供后续失效复核比对。缺省留空，复核时降级按 reason。
    """
    conn = _get_conn()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO quarantine_records (uid, reason, quarantined_at, restored_at, reason_basis)
        VALUES (?, ?, ?, NULL, ?)
        ON CONFLICT(uid) DO UPDATE SET
            reason=excluded.reason,
            reason_basis=excluded.reason_basis,
            quarantined_at=excluded.quarantined_at,
            restored_at=NULL
    """, (str(uid), str(reason), now, str(basis)))
    conn.commit()
    conn.close()


def add_quarantine_batch(items: list):
    """批量移入隔离区：items=[(uid, reason), ...] 或 [(uid, reason, basis), ...]。

    单事务 executemany 替代循环 connect/commit/close，
    数百条记录耗时从几秒降到几十毫秒，避免 UI「未响应」。
    """
    if not items:
        return
    conn = _get_conn()
    now = datetime.now().isoformat()
    rows = []
    for it in items:
        if len(it) >= 3:
            uid, reason, basis = it[0], it[1], it[2]
        else:
            uid, reason, basis = it[0], it[1], ""
        rows.append((str(uid), str(reason), now, str(basis)))
    conn.executemany("""
        INSERT INTO quarantine_records (uid, reason, quarantined_at, restored_at, reason_basis)
        VALUES (?, ?, ?, NULL, ?)
        ON CONFLICT(uid) DO UPDATE SET
            reason=excluded.reason,
            reason_basis=excluded.reason_basis,
            quarantined_at=excluded.quarantined_at,
            restored_at=NULL
    """, rows)
    conn.commit()
    conn.close()


def remove_quarantine(uid: str):
    """将一条记录移出隔离区（软删除：记录恢复时间，便于追溯）"""
    conn = _get_conn()
    conn.execute(
        "UPDATE quarantine_records SET restored_at = ? WHERE uid = ?",
        (datetime.now().isoformat(), str(uid))
    )
    conn.commit()
    conn.close()


def remove_quarantine_batch(uids: List[str]):
    """批量移出隔离区：单事务 executemany，替代循环 connect/commit/close"""
    if not uids:
        return
    conn = _get_conn()
    now = datetime.now().isoformat()
    conn.executemany(
        "UPDATE quarantine_records SET restored_at = ? WHERE uid = ?",
        [(now, str(uid)) for uid in uids]
    )
    conn.commit()
    conn.close()


def update_quarantine_reason(uid: str, reason: str):
    """仅更新隔离原因（人工修正），不动 reason_basis / quarantined_at / restored_at。"""
    conn = _get_conn()
    conn.execute(
        "UPDATE quarantine_records SET reason = ? WHERE uid = ?",
        (str(reason), str(uid))
    )
    conn.commit()
    conn.close()


def is_quarantined(uid: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT 1 FROM quarantine_records WHERE uid = ? AND restored_at IS NULL",
        (str(uid),)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_quarantined_ids() -> Set[str]:
    """返回当前处于隔离区（未恢复）的 uid 集合，供数据加载时水合 _quarantined 列"""
    conn = _get_conn()
    cur = conn.execute("SELECT uid FROM quarantine_records WHERE restored_at IS NULL")
    result = {row[0] for row in cur.fetchall()}
    conn.close()
    return result


# --------------------------------------------------------------------------- 失效复核
def _col(df, *candidates):
    """返回 df 中第一个存在的候选列名，都不存在返回 None。"""
    for c in candidates:
        if c in df.columns:
            return c
    return None


# 失效复核：理由已不成立、建议移出隔离区的状态集合
INVALID_QUARANTINE_STATUSES = {
    "neg_loss_resolved", "neg_loss_over", "rule_no_match",
    "manual_over_quota",
}

# v43.327 超额投料待人工复核阈值（百分点）。裴哥 2026-11-09 确认口径：
#   (实际 - 定额) / 定额 × 100 > 10%  → 属于超额投料，必须留在隔离区人工复核，
#   既不算失效（不进失效复核列表），也不能自动已读。
OVERFEED_REVIEW_THRESHOLD_PCT = 10.0


def is_overfeed_needs_review(actual, quota,
                             threshold_pct=OVERFEED_REVIEW_THRESHOLD_PCT) -> bool:
    """隔离区「超额投料待人工复核」唯一判据（失效复核 + 已读对账共用）。

    口径：定额 > 0 且 (实际 - 定额) / 定额 * 100 > threshold_pct（严格大于）。

    为什么排除定额<=0：源表对「定额=0、实际>0」恒给 +100% 的 SAP 除零钳位假值，
    本期约 1093 行；若不排除会把整批误判为「超额投料待复核」。
    NaN / None / 非数值一律返回 False（保守，沿用旧逻辑，不新增失效路径）。
    负损（实际<定额）与相符（实际=定额）均不命中。
    """
    try:
        a = float(actual)
        q = float(quota)
    except (TypeError, ValueError):
        return False
    if math.isnan(a) or math.isnan(q) or math.isinf(a) or math.isinf(q):
        return False
    if q <= 0 or a <= q:
        return False
    return (a - q) / q * 100.0 > float(threshold_pct)


def scan_expired_quarantine(df, cfg=None) -> List[Dict]:
    """扫描隔离区中「仍存在于主表」的记录，判定其入区依据是否因数据变动而失效。

    仅返回「已失效」的记录（理由已不成立、建议移出隔离区），每条含：
        uid, reason, basis, detail, actual, quota, status
    status ∈ {'neg_loss_resolved', 'neg_loss_over', 'rule_no_match'}
    basis 为空（旧行）时降级按 reason 文本是否含「负损」/「自动规则」判断。

    注意：
    - 主表中已找不到该 uid 的行（如订单被新导出删除）→ 不翻标，返回结果不包含。
    - 手动隔离 + 原因非负损（basis 以「手动:」开头且无负损关键词）→ 无数据可复核依据，不翻标。
    - v43.327：超额投料（(实际-定额)/定额 > 10%）一律不判失效，保留在隔离区
      由人工复核；该规则不区分当初入区原因，也不受 basis 影响（见
      is_overfeed_needs_review）。
    """
    try:
        import pandas as pd
    except ImportError:
        return []
    if df is None or not hasattr(df, "empty") or df.empty or "data_id" not in df.columns:
        return []

    from core.auto_quarantine import compute_auto_quarantine_ids
    if cfg is None:
        from core.auto_quarantine import load_auto_quarantine_config
        cfg = load_auto_quarantine_config()

    # 当前自动规则命中集（用于「自动规则类」失效判定）
    still_matched = set(compute_auto_quarantine_ids(df, cfg).keys())
    # 规则序号 -> 规则配置（解析「自动规则[第N条]」用），用于判断某记录是否因负损入区
    rules_by_idx = {}
    for i, rl in enumerate(cfg.get("rules", []), 1):
        rules_by_idx[i] = rl

    import re as _re
    auto_rule_pat = _re.compile(r"第(\d+)条")

    actual_col = _col(df, "数量-实际", "实际", "实际数量", "数量 - 实际", "actual")
    quota_col = _col(df, "数量-定额", "定额", "定额数量", "数量 - 定额", "quota")

    records = get_quarantine_records()
    if not records:
        return []
    # O(1) 索引：主表 data_id → row，消除原 O(n*m) 全表扫描
    # 先 drop_duplicates 防止重复 data_id 导致 df_index.loc[uid] 返回 DataFrame 而非 Series
    try:
        df_index = df.drop_duplicates(subset='data_id', keep='first').set_index(df["data_id"].astype(str))
    except Exception:
        df_index = None  # 降级回逐行查找
    result = []
    for rec in records:
        uid = str(rec["uid"])
        # ---------------------------- 新增：跳过已标记豁免的记录 ----------------------------
        if is_exempted(uid):
            continue
        # -----------------------------------------------------------------------------------
        basis = (rec.get("reason_basis") or "").strip()
        reason = (rec.get("reason") or "").strip()
        # 优先用 basis，缺省降级用 reason
        basis_key = basis if basis else reason

        try:
            row = df_index.loc[uid] if df_index is not None else None
        except KeyError:
            row = None
        if row is None:
            continue  # 主表已无此行，不翻标
        actual = quota = None
        if actual_col:
            actual = pd.to_numeric(row.get(actual_col), errors="coerce")
            actual = None if pd.isna(actual) else float(actual)
        if quota_col:
            quota = pd.to_numeric(row.get(quota_col), errors="coerce")
            quota = None if pd.isna(quota) else float(quota)

        # v43.327：超额投料必须人工复核 —— 在一切失效判定之前短路。
        # 覆盖三类入区来源（负损类 / 自动规则类 / 手动类），不受 basis 影响；
        # 命中即 continue，既不进失效列表，也不会被「一键移出隔离区」波及。
        if is_overfeed_needs_review(actual, quota):
            continue

        is_neg_loss_now = None
        if actual is not None and quota is not None:
            is_neg_loss_now = (actual > 0) and (actual < quota)

        is_auto = ("自动规则" in basis_key) or basis_key.startswith("自动规则")
        # 是否「当初因负损入区」：basis 文本含负损，或 是自动规则且对应规则要求负损
        is_neg_loss_basis = ("负损" in basis_key) or ("实际>0 且 实际<定额" in basis_key) \
            or basis_key.startswith("负损")
        if not is_neg_loss_basis and is_auto:
            # 优先按规则名称匹配（规则增删/重排后序号会变，名称更稳定）
            rl = None
            for i, r in enumerate(cfg.get("rules", []), 1):
                if r.get("name", "").strip() in basis_key:
                    rl = r
                    break
            # 降级：按旧格式「自动规则[第N条]」用序号反查（向后兼容）
            if rl is None:
                m = auto_rule_pat.search(basis_key)
                if m:
                    rl = rules_by_idx.get(int(m.group(1)))
            if rl and rl.get("negative_loss_required", False):
                is_neg_loss_basis = True

        # ── 负损类：实时重判（数据驱动，最精准）──
        if is_neg_loss_basis:
            if is_neg_loss_now is False:
                if actual is not None and quota is not None and actual >= quota:
                    if actual == quota:
                        status, detail = "neg_loss_resolved", "补投后实际=定额，已相符"
                    else:
                        status, detail = "neg_loss_over", "补投过量，实际>定额（多耗用）"
                elif actual is not None and actual <= 0:
                    # v43.330：实际=0（未投料/非耗用）属异常，须人工审计：
                    # 不是「已解决」、也不判失效，保留在隔离区等待确认，不进失效列表。
                    continue
                else:
                    status, detail = "neg_loss_resolved", "负损条件已不满足"
                result.append({
                    "uid": uid, "reason": reason, "basis": basis_key,
                    "detail": detail, "actual": actual, "quota": quota, "status": status,
                })
            continue

        # ── 自动规则类：重跑规则看是否还在命中集 ──
        if is_auto:
            if uid not in still_matched:
                result.append({
                    "uid": uid, "reason": reason, "basis": basis_key,
                    "detail": "已不再命中任何自动隔离规则",
                    "actual": actual, "quota": quota, "status": "rule_no_match",
                })
            continue

        # ── 手动 + 非负损：补充自动判据 ──
        # 若负损条件仍成立（0<actual<quota），不加入失效列表
        if actual is not None and quota is not None and 0 < actual < quota:
            continue
        # 若实际>定额，直接判为失效
        if actual is not None and quota is not None and actual > quota:
            result.append({
                "uid": uid, "reason": reason, "basis": basis_key,
                "detail": f"手动隔离但实际({actual})>定额({quota})，已无需隔离",
                "actual": actual, "quota": quota, "status": "manual_over_quota",
            })
        else:
            # 无自动判据，列入失效复核供人工确认
            result.append({
                "uid": uid, "reason": reason, "basis": basis_key,
                "detail": "手动隔离，无自动失效判据，请人工确认隔离理由是否仍成立",
                "actual": actual, "quota": quota, "status": "manual_needs_review",
            })
    return result


def get_quarantine_records() -> List[Dict]:
    """返回当前隔离区明细（供弹窗展示），含 reason / quarantined_at / reason_basis / exempted"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT uid, reason, quarantined_at, reason_basis, exempted FROM quarantine_records "
        "WHERE restored_at IS NULL ORDER BY quarantined_at DESC"
    )
    columns = ['uid', 'reason', 'quarantined_at', 'reason_basis', 'exempted']
    result = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return result


def set_exempted(uid: str, exempted: bool) -> None:
    """设置或取消隔离记录的豁免状态"""
    conn = _get_conn()
    conn.execute(
        "UPDATE quarantine_records SET exempted = ? WHERE uid = ?",
        (bool(exempted), str(uid))
    )
    conn.commit()
    conn.close()


def is_exempted(uid: str) -> bool:
    """检查隔离记录是否已标记为豁免"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT exempted FROM quarantine_records WHERE uid = ?",
        (str(uid),)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None and row[0] == 1


def get_exempted_uids() -> Set[str]:
    """当前处于「人工已豁免」状态的 uid 集合。

    刻意**不**加 `restored_at IS NULL`：标记豁免的那一步会同时把记录移出隔离区
    （见 quarantine_dialog._toggle_exempted），若按在区过滤，豁免就只在那一刻生效，
    下一次自动隔离又会把它抓回来 —— 这正是「豁免看起来没生效」的根因。
    语义是「这条记录人被人工判过了」，与它此刻在不在区里无关。
    """
    conn = _get_conn()
    cur = conn.execute("SELECT uid FROM quarantine_records WHERE exempted = 1")
    result = {str(row[0]) for row in cur.fetchall()}
    conn.close()
    return result


def get_exempted_records() -> List[Dict]:
    """豁免台账：所有 exempted=1 的记录，含 restored_at（供界面区分「已移出/仍在区」）。"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT uid, reason, reason_basis, quarantined_at, restored_at FROM quarantine_records "
        "WHERE exempted = 1 ORDER BY quarantined_at DESC"
    )
    columns = ['uid', 'reason', 'reason_basis', 'quarantined_at', 'restored_at']
    result = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return result


def clear_exempted_batch(uids: List[str]) -> int:
    """批量作废豁免（审核后又被改动时用）。传入的应当确实是已豁免的 uid，
    返回值就是作废条数（调用方已用 get_exempted_uids 筛过）。"""
    if not uids:
        return 0
    conn = _get_conn()
    conn.executemany(
        "UPDATE quarantine_records SET exempted = 0 WHERE uid = ?",
        [(str(uid),) for uid in uids]
    )
    conn.commit()
    conn.close()
    return len(uids)
