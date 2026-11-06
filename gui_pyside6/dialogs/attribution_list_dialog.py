# -*- coding: utf-8 -*-
"""F2 归因建议清单弹窗（PySide6）。

聚合「需人工 / 重点 verdict」的待办建议（audit_report + audit_suggestion），
按 data_id 列出归因与建议动作，支持复制清单、导出 CSV。只建议不自动改。
"""
import csv
import io

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser,
                               QPushButton, QHBoxLayout, QFileDialog, QMessageBox)

import core.audit_evidence as ae


class AttributionListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("归因建议清单（F2）")
        self.resize(720, 560)
        self._items = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(False)
        layout.addWidget(self._body, 1)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("复制清单")
        copy_btn.clicked.connect(self._copy)
        export_btn = QPushButton("导出 CSV")
        export_btn.clicked.connect(self._export)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch(1)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(export_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._render()

    def _render(self):
        items = ae.get_pending_suggestions()
        self._items = items
        lines = []
        lines.append(f"# 归因建议清单（待办 / 需关注）　共 {len(items)} 条")
        lines.append("")
        lines.append("> 说明：本清单汇总需人工复核或重点 verdict 的审核建议。只建议、不自动改；"
                     "采纳后请在原业务系统处理。归因依据见各自证据卡。")
        lines.append("")
        if not items:
            lines.append("- （暂无待办建议，运行「AI 审核」后会在此出现）")
            self._body.setMarkdown("\n".join(lines))
            return

        for it in items:
            tag = "需人工" if it["needs_human"] else "需关注"
            lines.append(f"## {it['data_id']} · {it['verdict']}（{it['confidence']} / {tag}）")
            if it["root_cause"]:
                lines.append(f"- 归因：{it['root_cause']}")
            if it["action"]:
                lines.append(f"- 建议：{it['action']}")
            if it["precedent"]:
                lines.append(f"- 历史参考：{it['precedent'][0]}")
            lines.append("")

        self._body.setMarkdown("\n".join(lines))

    def _plain(self) -> str:
        rows = ["data_id\tverdict\tconfidence\tneeds_human\troot_cause\taction\thistory_ref"]
        for it in self._items:
            rows.append("\t".join([
                it["data_id"], it["verdict"], it["confidence"],
                "是" if it["needs_human"] else "否",
                (it["root_cause"] or "").replace("\n", " "),
                (it["action"] or "").replace("\n", " "),
                (it["precedent"][0] if it["precedent"] else ""),
            ]))
        return "\n".join(rows)

    def _copy(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._plain())

    def _export(self):
        if not self._items:
            QMessageBox.information(self, "导出 CSV", "当前没有可导出的建议。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出归因建议清单", "归因建议清单.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["data_id", "verdict", "confidence", "needs_human",
                            "root_cause", "action", "history_ref"])
                for it in self._items:
                    w.writerow([
                        it["data_id"], it["verdict"], it["confidence"],
                        "是" if it["needs_human"] else "否",
                        (it["root_cause"] or "").replace("\n", " "),
                        (it["action"] or "").replace("\n", " "),
                        (it["precedent"][0] if it["precedent"] else ""),
                    ])
            QMessageBox.information(self, "导出 CSV", f"已导出到：\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出出错：{e}")
