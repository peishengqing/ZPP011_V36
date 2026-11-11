# -*- coding: utf-8 -*-
"""单笔偏差全生命周期时间线弹窗（PySide6）。

由主表行右键「🕐 查看偏差时间线」打开，按 data_id 把
变更历史 → 审核结论 → 审核证据 → 归因建议 → 当前状态 串成一条竖向时间线，
服务追责与复盘（这笔偏差被改了几手、谁改的、为什么改、审核怎么判的）。
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTextBrowser,
                               QPushButton, QHBoxLayout, QFrame)
from PySide6.QtCore import Qt

from core.deviation_timeline import build_timeline
from utils.theme_manager import Thm


_KIND_LABEL = {
    "change": "数据变更",
    "audit": "审核",
    "suggestion": "归因建议",
    "feedback": "人工反馈",
}
#: 事件类型 → 语义色令牌键（实际色值按当前主题由 Thm 取，暗色下自动换亮档）
_KIND_TOKEN = {
    "change": "warn",
    "audit": "ok",
    "suggestion": "info",
    "feedback": "violet",
}


from gui_pyside6.components import dialog_chrome

class DeviationTimelineDialog(QDialog):
    def __init__(self, data_id: str, parent=None):
        super().__init__(parent)
        self.data_id = data_id or ""
        dialog_chrome.apply(self, dialog_chrome.TIER_LARGE, "偏差时间线", self.data_id)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        # 顶部当前状态条
        self._head = QLabel("")
        self._head.setFrameShape(QFrame.Box)
        self._head.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._head.setStyleSheet("QLabel{padding:8px;font-weight:bold;font-size:12px;}")
        self._head.setWordWrap(True)
        layout.addWidget(self._head)

        # 时间线正文
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(False)
        layout.addWidget(self._body, 1)

        # 底部：F3 占位 + 可追溯入口
        self._foot = QLabel("⏳ 人工采纳/驳回：F3 反馈闭环待落地，此节点暂无数据。")
        self._foot.setStyleSheet(f"QLabel{{color:{Thm.color('violet')};padding:2px;}}")
        layout.addWidget(self._foot)

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
        tl = build_timeline(self.data_id)
        self._render_head(tl)
        self._render_body(tl)

    def _render_head(self, tl):
        st = tl.get("status") or {}
        name = tl.get("material_name") or ""
        parts = [f"📄 {name}" if name else f"📄 {tl.get('data_id') or '（无 data_id）'}"]
        is_read = st.get("is_read")
        parts.append(f"已读：{'是' if is_read else '否'}")
        if st.get("snapshot_qty") is not None:
            parts.append(f"快照数量：{st['snapshot_qty']}")
        if st.get("closing_month"):
            cs = st.get("closing_status") or "未关账"
            parts.append(f"关账 {st['closing_month']}：{cs}")
        self._head.setText("　|　".join(parts))

    def _render_body(self, tl):
        events = tl.get("events") or []
        if not events:
            self._body.setHtml(
                "<p>该 data_id 暂无时间线事件（无变更历史、未审核、无归因建议）。</p>"
                "<p>运行一次「AI 审核」或发生数据变更后，这里会按时间串出完整链路。</p>")
            return

        # 纯 HTML 富文本：QTextBrowser 的 HTML 模式下 <b>/<h3>/<hr> 渲染稳定，
        # 不与 markdown 混用（避免 setMarkdown 里嵌 HTML 的转义歧义）。
        # 类型词由这里的彩色【label】承载，事件 title 只放纯标题（字段/结论/分支），不重复。
        parts = [f"<p>共 <b>{len(events)}</b> 个事件（旧 → 新）</p>"]
        for ev in events:
            kind = ev.get("kind", "")
            label = _KIND_LABEL.get(kind, kind)
            color = Thm.color(_KIND_TOKEN.get(kind, "textMuted"))
            time_s = ev.get("time") or "时间未知"
            warn = ev.get("needs_human")
            flag = "　⚠️需人工" if warn else ""
            parts.append(f"<h3>🕒 {time_s}</h3>")
            parts.append(
                f"<p><b style=\"color:{color}\">【{label}】</b> {ev.get('title')}{flag}</p>")
            if ev.get("detail"):
                detail = str(ev["detail"]).replace("\n", "<br/>")
                parts.append(f"<p>{detail}</p>")
            parts.append("<hr/>")
        self._body.setHtml("\n".join(parts))