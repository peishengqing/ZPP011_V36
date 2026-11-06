# -*- coding: utf-8 -*-
"""F1 审核结果可解释报告：证据底座（纯逻辑，无 PyQt，可 offscreen 单测）。

两张新表，挂在 audit.db（与 read_status / quarantine_records / closing_status 同库），
不改动任何既有表：

  audit_report(audit_id PK, data_id, verdict, confidence, needs_human,
               suggestion, report_version, rule_version, model_version, created_at)
  audit_evidence(id PK, audit_id, data_id, evidence_type, evidence_json,
                 rule_version, model_version, created_at)

设计原则（裴哥 F1 铁律）：
  - 只记录、不自动改数据；每个结论带 rule_version / model_version + 置信度。
  - 低置信度显式标 needs_human（建议人工复核）。
  - 证据用 JSON1 存，加 data_id / audit_id / created_at 索引；批量写走事务。
  - evidence_json 限制 TopN 与字段长度，避免膨胀。

注意：当前「AI 审核」按钮实际只跑本地规则（ai_client 未调用），所以 model_version
默认 'local-rule'；待重启用真 Agnes 时由调用方传入真实模型版本即可。
"""
import sqlite3
import json
import uuid
import datetime
from typing import Dict, List, Optional

from core.read_status import DB_PATH


def _app_version() -> str:
    try:
        from utils.version_history import VERSION_HISTORY
        return VERSION_HISTORY[0].get("version", "unknown")
    except Exception:
        return "unknown"


DEFAULT_MODEL_VERSION = "local-rule"   # 当前审核走本地规则引擎；重启用 AI 后改为真实模型版本


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------
def ensure_audit_tables() -> None:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS audit_report ("
        " audit_id TEXT PRIMARY KEY,"
        " data_id TEXT NOT NULL,"
        " verdict TEXT NOT NULL,"
        " confidence TEXT NOT NULL DEFAULT '中',"   # 高 | 中 | 低
        " needs_human INTEGER NOT NULL DEFAULT 0,"
        " suggestion TEXT DEFAULT '',"
        " report_version INTEGER NOT NULL DEFAULT 1,"
        " rule_version TEXT DEFAULT '',"
        " model_version TEXT DEFAULT '',"
        " created_at TEXT NOT NULL"
        ")")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS audit_evidence ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " audit_id TEXT NOT NULL,"
        " data_id TEXT NOT NULL,"
        " evidence_type TEXT NOT NULL,"
        " evidence_json TEXT NOT NULL,"
        " rule_version TEXT DEFAULT '',"
        " model_version TEXT DEFAULT '',"
        " created_at TEXT NOT NULL"
        ")")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_report_data ON audit_report(data_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_report_time ON audit_report(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evid_audit ON audit_evidence(audit_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evid_data ON audit_evidence(data_id)")
    conn.commit()
    conn.close()


def _connect() -> sqlite3.Connection:
    ensure_audit_tables()
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# ---------------------------------------------------------------------------
# 证据类型常量
# ---------------------------------------------------------------------------
EV_RULE_HIT = "rule_hit"                 # 命中本地规则/分支
EV_DEV_RATE = "dev_rate"                 # 偏差率（本期值）
EV_REMARK = "remark_coverage"           # 备注覆盖情况
EV_UNFINISHED = "unfinished_status"     # 未完结状态（分批入库场景）
EV_ALT_CHAIN = "alt_chain"              # 替代料长链
EV_HISTORY = "history_similar"          # 历史相似案例 TopN


# ---------------------------------------------------------------------------
# 写入
# ---------------------------------------------------------------------------
def write_audit(data_id: str, verdict: str, confidence: str,
                needs_human: bool, suggestion: str, evidence_list: List[Dict],
                rule_version: Optional[str] = None,
                model_version: Optional[str] = None,
                created_at: Optional[str] = None) -> str:
    """写入一次审核的完整证据。返回新生成的 audit_id。

    evidence_list: [{"evidence_type": str, "content": <json-serializable>,
                     "rule_version": str, "model_version": str}, ...]
    同一次审核的 rule_version / model_version 以首条证据或参数优先。
    """
    ensure_audit_tables()
    audit_id = uuid.uuid4().hex
    now = created_at or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rv = rule_version or _app_version()
    mv = model_version or DEFAULT_MODEL_VERSION

    # report_version：同一 data_id 自增
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        cur = conn.execute(
            "SELECT COALESCE(MAX(report_version), 0) FROM audit_report WHERE data_id=?",
            (str(data_id),))
        max_v = cur.fetchone()[0]
        report_version = max_v + 1

        conn.execute(
            "INSERT INTO audit_report "
            "(audit_id, data_id, verdict, confidence, needs_human, suggestion, "
            " report_version, rule_version, model_version, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (audit_id, str(data_id), verdict, confidence,
             1 if needs_human else 0, suggestion or "",
             report_version, rv, mv, now))

        for ev in evidence_list:
            ej = json.dumps(ev.get("content", {}), ensure_ascii=False)
            ev_rv = ev.get("rule_version") or rv
            ev_mv = ev.get("model_version") or mv
            conn.execute(
                "INSERT INTO audit_evidence "
                "(audit_id, data_id, evidence_type, evidence_json, rule_version, model_version, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (audit_id, str(data_id), ev.get("evidence_type", ""), ej,
                 ev_rv, ev_mv, now))
        conn.commit()
    finally:
        conn.close()
    return audit_id


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------
def get_latest_report(data_id: str) -> Optional[Dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT audit_id, data_id, verdict, confidence, needs_human, suggestion, "
        "report_version, rule_version, model_version, created_at "
        "FROM audit_report WHERE data_id=? ORDER BY report_version DESC LIMIT 1",
        (str(data_id),)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_report(row)


def get_report(audit_id: str) -> Optional[Dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT audit_id, data_id, verdict, confidence, needs_human, suggestion, "
        "report_version, rule_version, model_version, created_at "
        "FROM audit_report WHERE audit_id=?", (audit_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_report(row)


def get_evidence(audit_id: str) -> List[Dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT evidence_type, evidence_json, rule_version, model_version, created_at "
        "FROM audit_evidence WHERE audit_id=? ORDER BY id",
        (audit_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        try:
            content = json.loads(r[1])
        except Exception:
            content = {}
        out.append({
            "evidence_type": r[0],
            "content": content,
            "rule_version": r[2],
            "model_version": r[3],
            "created_at": r[4],
        })
    return out


def _row_to_report(r) -> Dict:
    return {
        "audit_id": r[0], "data_id": r[1], "verdict": r[2], "confidence": r[3],
        "needs_human": bool(r[4]), "suggestion": r[5], "report_version": r[6],
        "rule_version": r[7], "model_version": r[8], "created_at": r[9],
    }


def get_all_reports(limit: int = 500) -> List[Dict]:
    """期间汇总用：返回最近 N 条报告（含 data_id）。"""
    conn = _connect()
    rows = conn.execute(
        "SELECT audit_id, data_id, verdict, confidence, needs_human, suggestion, "
        "report_version, rule_version, model_version, created_at "
        "FROM audit_report ORDER BY created_at DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [_row_to_report(r) for r in rows]


def summary_stats(reports: Optional[List[Dict]] = None) -> Dict:
    """聚合期间汇总所需的分布。reports 不传则内部拉取最近 500 条。

    返回：verdict_dist / confidence_dist / needs_human_count / rule_version_dist /
         model_version_dist / top_reason_types（needs_human 下 evidence_type 频率）。
    """
    if reports is None:
        reports = get_all_reports(500)

    verdict_dist: Dict[str, int] = {}
    confidence_dist: Dict[str, int] = {}
    rule_version_dist: Dict[str, int] = {}
    model_version_dist: Dict[str, int] = {}
    needs_human_count = 0
    reason_types: Dict[str, int] = {}

    for r in reports:
        verdict_dist[r["verdict"]] = verdict_dist.get(r["verdict"], 0) + 1
        confidence_dist[r["confidence"]] = confidence_dist.get(r["confidence"], 0) + 1
        rule_version_dist[r["rule_version"]] = rule_version_dist.get(r["rule_version"], 0) + 1
        model_version_dist[r["model_version"]] = model_version_dist.get(r["model_version"], 0) + 1
        if r["needs_human"]:
            needs_human_count += 1
            # 该 data_id 最新报告的关联证据类型（Top 误判原因代理）
            rep = get_report(r["audit_id"])
            if rep:
                for ev in get_evidence(r["audit_id"]):
                    reason_types[ev["evidence_type"]] = reason_types.get(ev["evidence_type"], 0) + 1

    top_reason_types = sorted(reason_types.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "total": len(reports),
        "verdict_dist": verdict_dist,
        "confidence_dist": confidence_dist,
        "needs_human_count": needs_human_count,
        "rule_version_dist": rule_version_dist,
        "model_version_dist": model_version_dist,
        "top_reason_types": top_reason_types,
    }
