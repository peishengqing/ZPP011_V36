# -*- coding: utf-8 -*-
"""F1 单笔审核证据卡弹窗（PySide6）。

由主表行右键「📋 证据卡」打开，按 data_id 展示最新一次审核的：
  结论 / 置信度（低显「建议人工复核」） / 是否需人工 / 建议动作 /
  规则版本 / 模型版本 / 时间 + 证据链列表 + 可追溯入口（复制 data_id）。
"""
import json

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTextBrowser,
                               QPushButton, QHBoxLayout, QFrame)
from PySide6.QtCore import Qt

import core.audit_evidence as ae


_EV_LABEL = {
    ae.EV_RULE_HIT: "命中规则 / 分支",
    ae.EV_DEV_RATE: "偏差率（本期）",
    ae.EV_REMARK: "备注覆盖",
    ae.EV_UNFINISHED: "未完结状态",
    ae.EV_ALT_CHAIN: "替代料长链",
    ae.EV_HISTORY: "历史相似案例",
}


class EvidenceCardDialog(QDialog):
    def __init__(self, data_id: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.data_id = data_id or ""
        self.setWindowTitle(f"审核证据卡 · {self.data_id or '（无 data_id）'}")
        self.resize(620, 520)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # 顶部结论条
        self._head = QLabel("")
        self._head.setFrameShape(QFrame.Box)
        self._head.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._head.setStyleSheet("QLabel{padding:8px;font-weight:bold;font-size:13px;}")
        layout.addWidget(self._head)

        # 证据链正文
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(False)
        layout.addWidget(self._body, 1)

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
            self._head.setText("暂无审核证据（该 data_id 尚未运行审核或不在本期）")
            self._body.setPlainText("运行一次「AI 审核」后，此处会显示结论、置信度与证据链。")
            return

        evidences = ae.get_evidence(rep["audit_id"])
        suggestions = ae.get_suggestions(self.data_id)

        # 结论条：低置信度 / needs_human 标红
        warn = (rep["confidence"] == "低") or rep["needs_human"]
        verdict = rep["verdict"]
        conf = rep["confidence"]
        conf_tag = f"置信度：{conf}" + ("（建议人工复核）" if warn else "")
        color = "#c0392b" if warn else "#1f6f43"
        self._head.setText(
            f'<span style="color:{color}">结论：{verdict}</span>　|　{conf_tag}')
        self._head.setStyleSheet(
            f"QLabel{{padding:8px;font-weight:bold;font-size:13px;border:1px solid {color};}}")

        lines = []
        lines.append(f"**建议动作**：{rep['suggestion'] or '—'}")
        lines.append(f"**是否需人工**：{'是' if rep['needs_human'] else '否'}")
        lines.append(f"**规则版本**：{rep['rule_version']}　|　**模型版本**：{rep['model_version']}")
        lines.append(f"**报告版本**：v{rep['report_version']}　|　**生成时间**：{rep['created_at']}")
        lines.append("")

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
