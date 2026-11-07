# -*- coding: utf-8 -*-
"""B/C/D/F 链路联动回归测试（integration）。

目的：证明 B 钻取 / C 评分卡 / D 变更摘要·快照 / F 审核证据·归因·时间线 不是各自孤立，
而是能按同一 data_id、在同一个隔离 audit.db 上串成一条端到端数据链。

联动命门（本测试同时钉死，防止回归）：
  - read_status._get_conn() 是进程级单例缓存连接，patch rs.DB_PATH 后必须同时把
    rs._CONN 置 None，否则旧连接仍指向真实库（最容易踩的坑）。
  - scorecard / closing / audit_evidence / deviation_timeline 都是
    `from core.read_status import DB_PATH` 顶层按值拷贝，必须逐一 patch 各自模块的
    DB_PATH，漏一个就会打到真实 ~/.zpp011_audit/audit.db。

只读断言：本测试只往隔离临时库写测试数据，不碰任何真实表；测完即弃（tmp_path）。
"""
import pytest

pytestmark = pytest.mark.integration

from core import read_status as rs
from core import audit_evidence as ae
from core import closing
from core import deviation_timeline as dt
from core import scorecard
from core import change_summary
from core import snapshot

DID = "1101|2026-10-15|0000123456|20005693"
MONTH = "2026-10"


@pytest.fixture
def linked_env(tmp_path, monkeypatch):
    """把全链路模块指向同一个隔离临时 audit.db，返回 main_df（含单一 data_id）。"""
    dbpath = str(tmp_path / "audit.db")
    # 1) 单例连接源：先重置 _CONN 再改 DB_PATH（顺序无关，但两者都必须做）
    monkeypatch.setattr(rs, "_CONN", None, raising=False)
    monkeypatch.setattr(rs, "DB_PATH", dbpath)
    # 2) 顶层按值拷贝 DB_PATH 的模块，逐一 patch
    monkeypatch.setattr(scorecard, "DB_PATH", dbpath)
    monkeypatch.setattr(ae, "DB_PATH", dbpath)
    monkeypatch.setattr(closing, "DB_PATH", dbpath)
    # deviation_timeline 自身不持有 DB_PATH，其 DB 访问经 rs(_get_conn) 与 ae(_connect)，
    # 已被上面 rs.DB_PATH / ae.DB_PATH 覆盖，无需也无法单独 patch。
    # change_summary 的 _deviation_changes_since 是函数体内 `from core.read_status import DB_PATH`
    # → 运行时取 rs.DB_PATH，已被上面 patch 覆盖，无需额外处理。

    rs.init_db()
    ae.ensure_audit_tables()
    closing._ensure_table()

    import pandas as pd
    main_df = pd.DataFrame([{
        "工厂": "1101", "订单日期": "2026-10-15", "流程订单": "0000123456",
        "物料编码": "20005693", "物料名称": "测试物料", "data_id": DID,
        "偏差金额(含税)": -1000.0, "备注原因": "",
    }])
    return main_df


def test_b_drill_data_id_wiring(linked_env):
    """B 钻取：main_df 的 data_id 能被时间线/已读状态按同键定位。"""
    df = linked_env
    assert DID in set(df["data_id"])
    # 未标已读时，read_status 应查不到该键（返回空映射或无该键）
    rmap = rs.load_read_status([DID])
    assert DID not in rmap or not rmap[DID][0]


def test_f_audit_evidence_attribution_timeline(linked_env):
    """F 链路：审核 → 证据 → 归因 → 时间线 全部按同一 data_id 串起。"""
    # 写变更历史（两笔）
    rs.record_deviation_change(DID, "偏差金额", "100", "150", "审核后数据被修改")
    rs.record_deviation_change(DID, "偏差率", "5.0", "8.2", "重新分析")
    # 写审核 + 证据链 + 归因建议
    aid = ae.write_audit(DID, verdict="需关注", confidence="中", needs_human=False,
                         suggestion="补充备注说明偏差原因",
                         evidence_list=[{"evidence_type": "rule_hit",
                                         "content": {"branch": "dev_mid"},
                                         "rule_version": "t", "model_version": "local"}])
    ae.write_suggestion(aid, DID, branch="dev_mid", root_cause="偏差居中需关注",
                        action="补充备注", precedent=["案例A"],
                        candidates=[{"text": "候选1"}])

    # 审核报告按 data_id 可查
    rep = ae.get_latest_report(DID)
    assert rep is not None and rep["data_id"] == DID
    assert rep["verdict"] == "需关注"
    # 证据挂到该审核
    evs = ae.get_evidence(rep["audit_id"])
    assert any(e["evidence_type"] == "rule_hit" for e in evs)
    # 归因建议按 data_id 可查
    suggs = ae.get_suggestions(DID)
    assert len(suggs) == 1 and suggs[0]["branch"] == "dev_mid"

    # 时间线把以上全部串成一个事件流（2 变更 + 1 审核 + 1 归因）
    tl = dt.build_timeline(DID)
    kinds = [e["kind"] for e in tl["events"]]
    assert kinds.count("change") == 2
    assert kinds.count("audit") == 1
    assert kinds.count("suggestion") == 1
    # 审核节点挂上证据链
    audit_ev = [e for e in tl["events"] if e["kind"] == "audit"][0]
    assert "rule_hit" in audit_ev["detail"]
    assert tl["feedback_available"] is False  # F3 未落地占位


def test_c_scorecard_reads_same_db(linked_env):
    """C 评分卡：备注覆盖率吃 main_df，漂移率读同一 audit.db 的变更历史。"""
    df = linked_env
    rs.record_deviation_change(DID, "偏差金额", "100", "150", "审核后数据被修改")
    # 该笔变更 field 非“备注原因” → 漂移率 0.0
    sc = scorecard.compute_scorecard(df)
    assert sc["drift_rate"] == 0.0
    # main_df 备注原因为空 → 覆盖率 0.0
    assert sc["coverage_rate"] == 0.0
    assert "score_total" in sc


def test_c_drift_rate_tracks_note_field(linked_env):
    """C 联动：当变更历史出现 field='备注原因'，评分卡漂移率随之上升。"""
    df = linked_env
    rs.record_deviation_change(DID, "偏差金额", "100", "150", "x")   # 非备注
    assert scorecard.compute_scorecard(df)["drift_rate"] == 0.0
    rs.record_deviation_change(DID, "备注原因", "", "补充说明", "补备注")  # 备注原因
    # 2 条变更中 1 条为备注原因 → 漂移率 0.5
    assert scorecard.compute_scorecard(df)["drift_rate"] == pytest.approx(0.5)


def test_d_change_summary_and_snapshot(linked_env):
    """D 链路：变更摘要统计未完结订单 + 变更记录数，均基于同一 main_df + 同一 audit.db。"""
    df = linked_env
    rs.record_deviation_change(DID, "偏差金额", "100", "150", "审核后数据被修改")
    summary = change_summary.compute_change_summary(df)
    # 该 data_id 未标已读 → 计入未完结订单
    assert summary["current_total_orders"] >= 1
    assert summary["change_records"] >= 1
    # 快照未完结统计同样按 data_id 关联
    unf = snapshot.compute_unfinished(df)
    assert unf["total_orders"] >= 1


def test_closing_links_to_timeline_status(linked_env):
    """关账联动：data_id 所属月份关账后，时间线 status 应反映关账状态。"""
    closing.close_month(MONTH, by="tester", final_pdf="x.pdf")
    assert closing.get_status(MONTH)["status"] == "closed"
    tl = dt.build_timeline(DID)
    st = tl["status"]
    assert st.get("closing_month") == MONTH
    assert st.get("closing_status") == "closed"


def test_full_chain_end_to_end(linked_env):
    """端到端：一笔偏差从钻取到时间线，整条链按同一 data_id 贯通、口径一致。"""
    # 变更 → 审核(带证据) → 归因 → 关账
    rs.record_deviation_change(DID, "偏差金额", "100", "150", "审核后数据被修改")
    aid = ae.write_audit(DID, verdict="需关注", confidence="低", needs_human=True,
                         suggestion="补充备注",
                         evidence_list=[{"evidence_type": "alt_long_chain",
                                         "content": {"n": 2},
                                         "rule_version": "t", "model_version": "local"}])
    ae.write_suggestion(aid, DID, branch="alt_chain", root_cause="替代料长链",
                        action="复核配对", precedent=[], candidates=[])
    closing.close_month(MONTH, by="tester", final_pdf="f.pdf")

    tl = dt.build_timeline(DID)
    # 事件流齐全
    kinds = sorted({e["kind"] for e in tl["events"]})
    assert set(["change", "audit", "suggestion"]).issubset(set(kinds))
    # 低置信度 → 审核节点标需人工
    audit_ev = [e for e in tl["events"] if e["kind"] == "audit"][0]
    assert audit_ev["needs_human"] is True
    # 关账状态进时间线
    assert tl["status"]["closing_status"] == "closed"
    # 证据卡与时间线口径一致：证据均挂在同一 audit_id 下
    rep = ae.get_latest_report(DID)
    assert rep["audit_id"] == aid
