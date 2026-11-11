# -*- coding: utf-8 -*-
"""F1 期间汇总报告（全量）：读 audit_report / audit_evidence 聚合分布。

展示：结论分布、置信度分布、需人工数、规则/模型版本分布、需人工下 Top 误判原因
（evidence_type 频率）。人工采纳率依赖 F3 反馈闭环，未上线时显示占位说明。
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser,
                               QPushButton, QHBoxLayout)

import core.audit_evidence as ae

_EV_LABEL = {
    ae.EV_RULE_HIT: "命中规则/分支",
    ae.EV_DEV_RATE: "偏差率（本期）",
    ae.EV_REMARK: "备注覆盖",
    ae.EV_UNFINISHED: "未完结状态",
    ae.EV_ALT_CHAIN: "替代料长链",
    ae.EV_HISTORY: "历史相似案例",
}


from gui_pyside6.components import dialog_chrome

class AuditSummaryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        dialog_chrome.apply(self, dialog_chrome.TIER_LARGE, "期间汇总报告", "审核证据")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(False)
        layout.addWidget(self._body, 1)
        btn_row = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        self._render()

    def _render(self):
        stats = ae.summary_stats()
        lines = []
        lines.append(f"# 审核证据期间汇总（共 {stats['total']} 条报告）")
        lines.append("")
        lines.append("> 说明：本汇总基于本地审核（规则引擎）产出的可解释证据。"
                     "人工采纳率需待 F3 反馈闭环上线后提供。")
        lines.append("")

        lines.append("## 结论分布")
        if stats["verdict_dist"]:
            for k, v in sorted(stats["verdict_dist"].items(), key=lambda kv: -kv[1]):
                lines.append(f"- {k}：{v}")
        else:
            lines.append("- （暂无数据）")
        lines.append("")

        lines.append("## 置信度分布")
        for lv in ("高", "中", "低"):
            c = stats["confidence_dist"].get(lv, 0)
            lines.append(f"- {lv}：{c}")
        lines.append("")

        lines.append(f"## 需人工复核（低置信度 / 未完结暂缓）：{stats['needs_human_count']} 条")
        lines.append("")

        lines.append("## 规则版本分布")
        for k, v in sorted(stats["rule_version_dist"].items(), key=lambda kv: -kv[1]):
            lines.append(f"- {k}：{v}")
        lines.append("")

        lines.append("## 模型版本分布")
        for k, v in sorted(stats["model_version_dist"].items(), key=lambda kv: -kv[1]):
            lines.append(f"- {k}：{v}")
        lines.append("")

        lines.append("## 需人工下 Top 误判原因（证据类型频率）")
        if stats["top_reason_types"]:
            for et, cnt in stats["top_reason_types"][:8]:
                lines.append(f"- {_EV_LABEL.get(et, et)}：{cnt}")
        else:
            lines.append("- （暂无需人工记录）")
        lines.append("")

        lines.append("## 人工采纳率")
        lines.append("- **F3 反馈闭环未上线**：采纳率 / 驳回原因分布暂不可得，待 F3 落地后补充。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("可解释覆盖率目标：每条审核结果都有证据链（100%）。"
                     "低置信度标注率、误判类型分布可在此查。建议不自动改数据，反馈可追溯，版本可回滚。")

        self._body.setMarkdown("\n".join(lines))
