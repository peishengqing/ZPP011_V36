# -*- coding: utf-8 -*-
"""评分卡「为什么分低」证据解释弹窗（PySide6）。

由数据稳定性弹窗 Tab4 评分卡表下方「🔍 查看扣分证据」按钮打开，
把三个维度的笼统结论落到 Top-N 具体证据（车间/物料/编码），服务追责与整改。
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser,
                               QPushButton, QHBoxLayout)

from core.scorecard_explain import build_explanation
from PySide6.QtCore import Qt


class ScorecardExplainDialog(QDialog):
    def __init__(self, main_df, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self._df = main_df
        self.setWindowTitle("评分卡扣分证据 · 为什么分低")
        self.resize(640, 560)
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
        exp = build_explanation(self._df)
        mr = exp.get("missing_remark") or {}
        drift = exp.get("drift_top") or []
        alt = exp.get("alt_chain") or {}

        parts = ["<h2>🔍 评分卡扣分证据</h2>"]

        # 维度 1：备注缺失
        parts.append("<h3>① 备注覆盖率低 — 缺备注的偏差行</h3>")
        total_missing = mr.get("total_missing", 0)
        if total_missing == 0:
            parts.append("<p>偏差行备注覆盖良好，无集中缺失。</p>")
        else:
            parts.append(f"<p>共 <b>{total_missing}</b> 条偏差行缺备注，集中如下：</p>")
            by_ws = mr.get("by_workshop") or []
            if by_ws:
                parts.append("<p><b>按车间：</b></p><ul>")
                for name, cnt in by_ws:
                    parts.append(f"<li>{name}：{cnt} 条</li>")
                parts.append("</ul>")
            by_mat = mr.get("by_material") or []
            if by_mat:
                parts.append("<p><b>按物料：</b></p><ul>")
                for code, desc, cnt in by_mat:
                    label = f"{desc}（{code}）" if desc else code
                    parts.append(f"<li>{label}：{cnt} 条</li>")
                parts.append("</ul>")

        # 维度 2：归因漂移
        parts.append("<h3>② 归因漂移高 — 反复改「备注原因」的物料</h3>")
        if not drift:
            parts.append("<p>无反复改备注的物料，归因稳定。</p>")
        else:
            parts.append("<ul>")
            for it in drift:
                parts.append(f"<li>物料 {it['material']}：被改 {it['changes']} 次</li>")
            parts.append("</ul>")

        # 维度 3：替代料长链
        parts.append("<h3>③ 替代料长链多 — 构成长链的物料编码</h3>")
        chains = alt.get("chains_count", 0)
        total_mat = alt.get("total_materials", 0)
        details = alt.get("details") or []
        if chains == 0:
            parts.append("<p>无替代料长链。</p>")
        else:
            parts.append(f"<p>共 <b>{chains}</b> 个物料出现在 &gt;1 个替代料组"
                         f"（占 {total_mat} 物料），明细：</p><ul>")
            for it in details:
                parts.append(f"<li>{it['code']}：跨 {it['groups']} 组</li>")
            parts.append("</ul>")

        self._body.setHtml("\n".join(parts))
