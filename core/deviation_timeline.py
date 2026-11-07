# -*- coding: utf-8 -*-
"""单笔偏差全生命周期时间线（纯逻辑，无 PyQt，可 offscreen 单测）。

以 data_id 为轴，把分散在各表的事件按时间串成一条时间线：

  变更历史(deviation_history) → 审核结论(audit_report) → 审核证据(audit_evidence)
  → 归因建议(audit_suggestion) → 当前状态(read_status 快照 + closing 关账)

设计原则（承接 B 钻取 / C 评分卡 / D 变更摘要 / F1 证据链 / F2 归因建议 的整合收口）：
  - 只读不改：时间线纯查询，不写任何表。
  - 每个事件带时间 + 类型 + 标题 + 明细，按时间升序（旧→新）排列。
  - 全部查询走 data_id 索引（deviation_history/audit_report/audit_evidence/
    audit_suggestion 四表均有 data_id 索引），单笔拉取不会全表扫描。
  - 人工采纳/驳回节点依赖 F3 audit_feedback（本期未落地），先返回
    feedback_available=False 占位，F3 落地后在事件流里追加 feedback 事件即可。
"""
from typing import Dict, List, Optional

from core import read_status as rs
from core import audit_evidence as ae


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _norm_time(t) -> str:
    """把 'YYYY-MM-DDTHH:MM:SS' / 'YYYY-MM-DD HH:MM:SS' 统一成可排序可显示字符串。"""
    if not t:
        return ""
    return str(t).strip().replace("T", " ")


def _month_of_data_id(data_id: str) -> Optional[str]:
    """data_id = 工厂|订单日期|流程订单|物料编码，取订单日期前 7 位作月份（best-effort）。"""
    try:
        seg = str(data_id).split("|")
        if len(seg) >= 2:
            d = seg[1].strip()
            if len(d) >= 7 and d[4] == "-":
                return d[:7]
    except Exception:
        pass
    return None


def _material_name(data_id: str) -> str:
    """从 material_names 持久缓存取物料名（编码 = data_id 末段），取不到返回空。"""
    try:
        seg = str(data_id).split("|")
        code = seg[-1] if seg else ""
        if not code:
            return ""
        return rs.get_material_names().get(code, "")
    except Exception:
        return ""


def _reports_by_data(data_id: str) -> List[Dict]:
    """某 data_id 的全部审核报告（按 report_version 升序），复用 F1 的 row 映射。"""
    conn = ae._connect()
    try:
        rows = conn.execute(
            "SELECT audit_id, data_id, verdict, confidence, needs_human, suggestion, "
            "report_version, rule_version, model_version, created_at "
            "FROM audit_report WHERE data_id=? ORDER BY report_version ASC",
            (str(data_id),)).fetchall()
    finally:
        conn.close()
    return [ae._row_to_report(r) for r in rows]


# ---------------------------------------------------------------------------
# 事件采集
# ---------------------------------------------------------------------------
def _collect_changes(data_id: str, events: List[Dict]) -> None:
    """变更历史：被改了几手 · 旧值→新值 · 原因。"""
    try:
        hist = rs.get_deviation_history(data_id) or []
    except Exception:
        hist = []
    for h in hist:
        field = h.get("field") or "字段"
        old_v = h.get("old_value")
        new_v = h.get("new_value")
        events.append({
            "time": _norm_time(h.get("change_time")),
            "kind": "change",
            "title": f"{field}",
            "detail": f"{old_v} → {new_v}　|　原因：{h.get('change_reason') or '—'}",
        })


def _collect_audits(data_id: str, events: List[Dict]) -> None:
    """审核结论 + 证据链：每次审核一个节点，证据挂在节点下。"""
    for rep in _reports_by_data(data_id):
        try:
            evids = ae.get_evidence(rep["audit_id"]) or []
        except Exception:
            evids = []
        ev_lines = [
            f"- {ev['evidence_type']}（rule={ev['rule_version']}, model={ev['model_version']}）"
            for ev in evids
        ]
        warn = (rep["confidence"] == "低") or rep["needs_human"]
        detail = f"建议动作：{rep.get('suggestion') or '—'}"
        if ev_lines:
            detail += "\n证据链：\n" + "\n".join(ev_lines)
        events.append({
            "time": _norm_time(rep["created_at"]),
            "kind": "audit",
            "title": (f"{rep['verdict']}（置信度 {rep['confidence']}"
                      f"{' · 需人工' if rep['needs_human'] else ''}）"),
            "detail": detail,
            "needs_human": warn,
            "report_version": rep["report_version"],
        })


def _collect_suggestions(data_id: str, events: List[Dict]) -> None:
    """归因建议（F2）：候选原因 + 建议动作 + 历史参考。"""
    try:
        suggs = ae.get_suggestions(data_id) or []
    except Exception:
        suggs = []
    for s in suggs:
        detail = f"归因：{s.get('root_cause') or '—'}\n建议动作：{s.get('action') or '—'}"
        if s.get("precedent"):
            detail += "\n历史参考：" + "；".join(s["precedent"][:3])
        cand = " / ".join(
            c.get("text", "") for c in (s.get("candidates") or []) if c.get("text"))
        if cand:
            detail += f"\n候选：{cand}"
        events.append({
            "time": _norm_time(s.get("created_at")),
            "kind": "suggestion",
            "title": f"{s.get('branch') or '分支'}",
            "detail": detail,
        })


# ---------------------------------------------------------------------------
# 当前状态（快照 + 关账）
# ---------------------------------------------------------------------------
def _current_status(data_id: str) -> Dict:
    out = {
        "is_read": None, "snapshot_qty": None, "snapshot_note": None,
        "snapshot_yield": None, "closing_month": None, "closing_status": None,
    }
    try:
        tup = rs.load_read_status([data_id]).get(str(data_id))
        if tup:
            out["is_read"] = tup[0]
            out["snapshot_qty"] = tup[2]
            out["snapshot_note"] = tup[3]
            out["snapshot_yield"] = tup[4]
    except Exception:
        pass
    month = _month_of_data_id(data_id)
    if month:
        try:
            from core import closing  # 懒加载：closing 顶层依赖 pandas
            out["closing_month"] = month
            out["closing_status"] = closing.get_status(month).get("status")
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# 对外主函数
# ---------------------------------------------------------------------------
def build_timeline(data_id: str) -> Dict:
    """以 data_id 为轴，组装单笔偏差全生命周期时间线。

    返回：{data_id, material_name, events, status, feedback_available}
      events: [{time, kind, title, detail, ...}] 按时间升序（旧→新），时间空者排最后。
      kind ∈ {change, audit, suggestion}（F3 落地后追加 feedback）。
      status: 当前快照 + 关账状态（pinned 到弹窗顶部，不进事件流）。
      feedback_available: False=人工反馈节点待 F3 落地（弹窗底部显占位说明）。
    """
    data_id = str(data_id or "")
    events: List[Dict] = []
    _collect_changes(data_id, events)
    _collect_audits(data_id, events)
    _collect_suggestions(data_id, events)

    # 时间升序（旧→新），时间空者排最后；同时间按 kind 稳定
    events.sort(key=lambda e: (_norm_time(e.get("time")) == "", _norm_time(e.get("time"))))

    return {
        "data_id": data_id,
        "material_name": _material_name(data_id),
        "events": events,
        "status": _current_status(data_id),
        "feedback_available": False,   # F3 audit_feedback 落地后改 True
    }