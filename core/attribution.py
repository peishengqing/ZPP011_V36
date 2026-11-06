# -*- coding: utf-8 -*-
"""F2 归因建议（纯逻辑，无 PyQt，可 offscreen 单测）。

在 F1 证据链 / verdict 基础上，生成可解释的「归因 + 建议动作」，
并 best-effort 检索历史相似案例作 precedent。只建议、不自动改。

原则（裴哥 F 系列）：先证据链、后模型；先检索/规则、后训练；
所有结论带版本 + 置信度。
"""
from typing import Dict, List, Optional

from core.read_status import DB_PATH


# 分支 -> (归因句式, 动作句式)。句式用 {rate}/{remark}/{kw}/{n} 占位，由 _fmt 填充。
# 分支名须与 gui_pyside6/models/workers.py 的 _record_decision 保持一致。
_BRANCH_LOGIC = {
    "unfinished": (
        "数据未完结：该订单仍处分批入库状态，在途单据未结算，当前偏差数可能不完整",
        "暂缓判定，待入库全部完成后复核再定结论；期间勿据现有数据关账或改数",
    ),
    "keyword_hit": (
        "备注含明确原因关键词（{kw}），偏差已有合理解释",
        "维持当前判定，备注作为依据留存；如无新证据不必重审",
    ),
    "remark_short": (
        "备注过短（{n}字），原因描述不充分，无法据此认定偏差性质",
        "补充详细原因（建议≥5字），写明偏差来源/责任环节，便于后续追溯",
    ),
    "remark_ok": (
        "备注清晰，偏差原因已说明",
        "维持当前判定",
    ),
    "dev_low": (
        "偏差率 {rate}% 在可接受区间（<5%），属正常波动",
        "可接受，无需特别处理；纳入常规监控即可",
    ),
    "dev_mid": (
        "偏差率 {rate}% 居中（5%~10%），需确认是否合理",
        "确认偏差来源是否合理；如非系统/工艺变更，建议补备注说明",
    ),
    "dev_high": (
        "偏差率 {rate}% 偏高（≥10%）且无备注，风险敞口大",
        "必须补备注说明原因；若为替代料/工艺变更需附凭证，必要时人工复核",
    ),
}


def retrieve_precedent(material: str, factory: str, top: int = 3) -> List[str]:
    """best-effort：同物料+同厂的历史有效备注 TopN（deviation_history）。失败返回 []。"""
    material = str(material or "").strip()
    factory = str(factory or "").strip()
    if not material or not factory:
        return []
    try:
        import sqlite3
        from collections import Counter
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            cur = conn.execute(
                "SELECT 备注原因 FROM deviation_history "
                "WHERE 物料编码=? AND 工厂=? LIMIT 200", (material, factory))
            cnt = Counter()
            for (r,) in cur.fetchall():
                rs = str(r or "").strip()
                if rs and rs not in ("nan", "None", ""):
                    cnt[rs] += 1
            return [k for k, _ in cnt.most_common(top)]
        finally:
            conn.close()
    except Exception:
        return []


def build_attribution(branch: str, *, dev_rate: float = 0.0, remark: str = "",
                      has_alt_chain: bool = False, material: str = "",
                      factory: str = "", keywords: Optional[List[str]] = None) -> Dict:
    """返回结构化归因建议 dict。"""
    root_tmpl, action_tmpl = _BRANCH_LOGIC.get(branch, ("（未识别分支）", "建议人工复核"))
    n = len(remark) if remark else 0
    kw = "、".join(keywords) if keywords else "替代料/系统无定额/已核实"
    root_cause = root_tmpl.format(rate=round(abs(dev_rate), 2), remark=remark, kw=kw, n=n)
    action = action_tmpl.format(rate=round(abs(dev_rate), 2), remark=remark, kw=kw, n=n)

    precedent = retrieve_precedent(material, factory)
    candidates = [
        {"type": "rule", "text": action, "confidence": "规则推导"},
    ]
    if precedent:
        candidates.append({
            "type": "precedent",
            "text": "参考历史同类处理：" + "；".join(precedent[:1]),
            "confidence": "历史检索",
        })
    if has_alt_chain:
        candidates.append({
            "type": "alt_chain",
            "text": "核对替代料 BOM 映射与长链替代关系，确认净偏差抵消口径",
            "confidence": "规则推导",
        })
    return {
        "branch": branch,
        "root_cause": root_cause,
        "action": action,
        "precedent": precedent,
        "candidates": candidates,
    }


def compact_suggestion(att: Dict) -> str:
    """压成单行字符串，写 audit_report.suggestion。"""
    s = att.get("action", "")
    if att.get("precedent"):
        s += "；参考历史：" + att["precedent"][0]
    return s
