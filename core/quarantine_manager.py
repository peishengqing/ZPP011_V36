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
    "neg_loss_resolved", "neg_loss_over", "neg_loss_zeroed", "rule_no_match",
    "manual_over_quota",
}


def scan_expired_quarantine(df, cfg=None) -> List[Dict]:
    """扫描隔离区中「仍存在于主表」的记录，判定其入区依据是否因数据变动而失效。

    仅返回「已失效」的记录（理由已不成立、建议移出隔离区），每条含：
        uid, reason, basis, detail, actual, quota, status
    status ∈ {'neg_loss_resolved', 'neg_loss_zeroed', 'neg_loss_over', 'rule_no_match'}
    basis 为空（旧行）时降级按 reason 文本是否含「负损」/「自动规则」判断。

    注意：
    - 主表中已找不到该 uid 的行（如订单被新导出删除）→ 不翻标，返回结果不包含。
    - 手动隔离 + 原因非负损（basis 以「手动:」开头且无负损关键词）→ 无数据可复核依据，不翻标。
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
    try:
        df_index = df.set_index(df["data_id"].astype(str))
    except Exception:
        df_index = None  # 降级回逐行查找
    result = []
    for rec in records:
        uid = str(rec["uid"])
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

        is_neg_loss_now = None
        if actual is not None and quota is not None:
            is_neg_loss_now = (actual > 0) and (actual < quota)

        is_auto = ("自动规则" in basis_key) or basis_key.startswith("自动规则")
        # 是否「当初因负损入区」：basis 文本含负损，或 是自动规则且对应规则要求负损
        is_neg_loss_basis = ("负损" in basis_key) or ("实际>0 且 实际<定额" in basis_key) \
            or basis_key.startswith("负损")
        if not is_neg_loss_basis and is_auto:
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
                    status, detail = "neg_loss_zeroed", "实际已归零（非耗用）"
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

        # ── 手动 + 非负损：补充自动判据（实际>定额即失效）──
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
    """返回当前隔离区明细（供弹窗展示），含 reason / quarantined_at / reason_basis"""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT uid, reason, quarantined_at, reason_basis FROM quarantine_records "
        "WHERE restored_at IS NULL ORDER BY quarantined_at DESC"
    )
    columns = ['uid', 'reason', 'quarantined_at', 'reason_basis']
    result = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return result
