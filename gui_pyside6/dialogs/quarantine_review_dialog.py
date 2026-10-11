# -*- coding: utf-8 -*-
"""隔离区闭环复盘看板（v43.181）。

只读 `audit.db` 的 `quarantine_records` 表（隔离进出流水，含 restored_at），
帮助审核员发现「哪些物料反复进隔离」「隔离后多久被放回」「哪些悬挂未放回」。
与偏差分析主表解耦，不触碰 analyzer 红线区。
"""
import os
import sqlite3
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem, QLabel,
    QMessageBox,
)
from PySide6.QtCore import Qt

_DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "audit.db")


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        try:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


class QuarantineReviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔁 隔离区闭环复盘")
        self.resize(900, 620)
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        self._info = QLabel()
        self._info.setWordWrap(True)
        lay.addWidget(self._info)
        self._tabs = QTabWidget()
        self._t_repeat = QTableWidget()
        self._t_repeat.setColumnCount(4)
        self._t_repeat.setHorizontalHeaderLabels(
            ["data_id(uid)", "进隔离次数", "最近进隔离", "最近原因"])
        self._tabs.addTab(self._t_repeat, "反复进隔离榜")
        self._t_hang = QTableWidget()
        self._t_hang.setColumnCount(3)
        self._t_hang.setHorizontalHeaderLabels(["data_id(uid)", "进隔离时间", "原因"])
        self._tabs.addTab(self._t_hang, "悬挂未放回")
        self._t_dur = QTableWidget()
        self._t_dur.setColumnCount(3)
        self._t_dur.setHorizontalHeaderLabels(["data_id(uid)", "隔离时长(小时)", "原因"])
        self._tabs.addTab(self._t_dur, "放回时长TOP")
        lay.addWidget(self._tabs, 1)

    def _load(self):
        if not os.path.exists(_DB_PATH):
            QMessageBox.information(self, "提示", "未找到审计库: %s" % _DB_PATH)
            return
        try:
            c = sqlite3.connect(_DB_PATH)
            tot = c.execute("select count(*) from quarantine_records").fetchone()[0]
            rep = c.execute(
                "select uid, count(*) cnt, max(quarantined_at), max(reason) "
                "from quarantine_records group by uid having cnt>=2 "
                "order by cnt desc limit 300").fetchall()
            hang = c.execute(
                "select uid, quarantined_at, reason from quarantine_records "
                "where restored_at is null or restored_at='' "
                "order by quarantined_at desc limit 300").fetchall()
            all_rows = c.execute(
                "select uid, quarantined_at, restored_at, reason from quarantine_records "
                "where restored_at is not null and restored_at<>''").fetchall()
            c.close()

            self._fill_repeat(rep)
            self._fill_hang(hang)

            durs = []
            for uid, qa, ra, reason in all_rows:
                d1, d2 = _parse(qa), _parse(ra)
                if d1 and d2:
                    hrs = (d2 - d1).total_seconds() / 3600.0
                    durs.append((uid, hrs, reason))
            durs.sort(key=lambda x: -x[1])
            self._fill_dur(durs[:200])

            self._info.setText(
                "quarantine_records 共 %d 条；反复进隔离 %d 个；悬挂未放回 %d 条"
                % (tot, len(rep), len(hang)))
        except Exception as e:
            QMessageBox.critical(self, "错误", "读取失败: %s" % e)

    def _fill_repeat(self, rows):
        self._t_repeat.setRowCount(len(rows))
        for i, (uid, cnt, qa, reason) in enumerate(rows):
            for j, v in enumerate([uid, str(cnt), str(qa), str(reason)]):
                it = QTableWidgetItem(v)
                if j == 1:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._t_repeat.setItem(i, j, it)
        self._t_repeat.resizeColumnsToContents()

    def _fill_hang(self, rows):
        self._t_hang.setRowCount(len(rows))
        for i, (uid, qa, reason) in enumerate(rows):
            for j, v in enumerate([uid, str(qa), str(reason)]):
                self._t_hang.setItem(i, j, QTableWidgetItem(v))
        self._t_hang.resizeColumnsToContents()

    def _fill_dur(self, rows):
        self._t_dur.setRowCount(len(rows))
        for i, (uid, hrs, reason) in enumerate(rows):
            for j, v in enumerate([uid, "%.1f" % hrs, str(reason)]):
                it = QTableWidgetItem(v)
                if j == 1:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._t_dur.setItem(i, j, it)
        self._t_dur.resizeColumnsToContents()
