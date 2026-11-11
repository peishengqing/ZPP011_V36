# -*- coding: utf-8 -*-
"""F1 单笔审核证据卡弹窗（PySide6）。

由主表行右键「📋 证据卡」打开，按 data_id 展示最新一次审核的：
  结论 / 置信度（低显「建议人工复核」） / 是否需人工 / 建议动作 /
  规则版本 / 模型版本 / 时间 + 证据链列表 + 可追溯入口（复制 data_id）。
"""
import json

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser,
                               QPushButton, QHBoxLayout)

import core.audit_evidence as ae
from gui_pyside6.components.dialog_chrome import StepChain, VerdictBanner


_EV_LABEL = {
    ae.EV_RULE_HIT: "命中规则 / 分支",
    ae.EV_DEV_RATE: "偏差率（本期）",
    ae.EV_REMARK: "备注覆盖",
    ae.EV_UNFINISHED: "未完结状态",
    ae.EV_ALT_CHAIN: "替代料长链",
    ae.EV_HISTORY: "历史相似案例",
}


from gui_pyside6.components import dialog_chrome

class EvidenceCardDialog(QDialog):
    def __init__(self, data_id: str, parent=None):
        super().__init__(parent)
        self.data_id = data_id or ""
        dialog_chrome.apply(self, dialog_chrome.TIER_LARGE, "审核证据卡", self.data_id)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # 结论条：设计稿 EvidenceShell 要求第一屏先给一句人话结论，再给依据
        self._verdict = VerdictBanner("正在读取审核证据…", "", "info")
        layout.addWidget(self._verdict)

        # 证据链正文
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(False)
        layout.addWidget(self._body, 1)

        # 溯源链：规则/模型/报告版本 + 生成时间，审核员要复核的是「哪套口径算出来的」
        self._trace = StepChain()
        layout.addWidget(self._trace)

        # 底部可追溯入口
        btn_row = QHBoxLayout()
        copy_btn = QPushButton("复制 data_id")
        copy_btn.clicked.connect(self._copy_data_id)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._render()

    def _copy_data_id(self):
        from PySide6.QtWidgets import QApplication
        if self.data_id:
            QApplication.clipboard().setText(self.data_id)

    def _render(self):
        rep = ae.get_latest_report(self.data_id) if self.data_id else None
        if rep is None:
            self._verdict.set_verdict(
                "暂无审核证据", "该 data_id 尚未运行审核，或不在本期数据里。", "info")
            self._body.setPlainText("运行一次「AI 审核」后，此处会显示结论、置信度与证据链。")
            return

        evidences = ae.get_evidence(rep["audit_id"])
        suggestions = ae.get_suggestions(self.data_id)

        # 结论条：低置信度 / 需人工 → danger 档（颜色取自 TOKENS，不写死 hex）
        warn = (rep["confidence"] == "低") or rep["needs_human"]
        self._verdict.set_verdict(
            "结论：%s" % rep["verdict"],
            "置信度：%s%s　|　建议动作：%s"
            % (rep["confidence"], "（建议人工复核）" if warn else "",
               rep["suggestion"] or "—"),
            "danger" if warn else "ok")

        self._trace.add_step("是否需人工：%s" % ("是" if rep["needs_human"] else "否"))
        self._trace.add_step(
            "规则版本 %s　·　模型版本 %s" % (rep["rule_version"], rep["model_version"]))
        self._trace.add_step(
            "报告版本 v%s　·　生成时间 %s" % (rep["report_version"], rep["created_at"]))

        lines = []

        # F2 归因建议段
        if suggestions:
            latest = suggestions[0]
            lines.append("### 归因建议（F2）")
            if latest.get("root_cause"):
                lines.append(f"- **归因**：{latest['root_cause']}")
            if latest.get("action"):
                lines.append(f"- **建议动作**：{latest['action']}")
            if latest.get("precedent"):
                prec = "；".join(latest["precedent"][:3])
                lines.append(f"- **历史参考**：{prec}")
            if latest.get("candidates"):
                cand = " / ".join(c.get("text", "") for c in latest["candidates"] if c.get("text"))
                if cand:
                    lines.append(f"- **候选建议**：{cand}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("### 证据链")
        for i, ev in enumerate(evidences, 1):
            label = _EV_LABEL.get(ev["evidence_type"], ev["evidence_type"])
            content = ev["content"]
            if isinstance(content, (dict, list)):
                ct = json.dumps(content, ensure_ascii=False, indent=2)
            else:
                ct = str(content)
            lines.append(f"**{i}. {label}**  _(rule={ev['rule_version']}, model={ev['model_version']})_")
            lines.append("```")
            lines.append(ct)
            lines.append("```")
            lines.append("")

        self._body.setMarkdown("\n".join(lines))
