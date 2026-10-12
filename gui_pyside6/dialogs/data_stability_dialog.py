# -*- coding: utf-8 -*-
"""数据稳定性看板（v43.181）。

只读 `audit.db` 的 `deviation_history` 表（偏差数据修改流水），帮助审核员发现
「哪些物料的数据在反复摇摆」「归因口径是否在漂移」「哪天做了大批量改动」。
与偏差分析主表完全解耦，不触碰 analyzer 红线区。
"""
import os
import sqlite3

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QTabWidget, QSpinBox, QMessageBox,
)
from PySide6.QtCore import Qt

from gui_pyside6.dialogs.material_profile_dialog import normalize_text

_DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "audit.db")


def _split_data_id(did):
    """data_id 格式：云南达利-食品厂|2026-09-07|100327825|20000389。"""
    p = did.split("|")
    fac = p[0].replace("云南达利-", "") if len(p) > 0 else ""
    od = p[1] if len(p) > 1 else ""
    fo = p[2] if len(p) > 2 else ""
    mat = p[3] if len(p) > 3 else ""
    return fac, od, fo, mat


class DataStabilityDialog(QDialog):
    def __init__(self, parent=None, code_name_map=None):
        super().__init__(parent)
        # v43.185：物料名称不在 audit.db，由主表当前数据带一份「编码→名称」映射进来。
        self._name_map = dict(code_name_map) if code_name_map else {}
        self.setWindowTitle("📈 数据稳定性看板")
        self.resize(1000, 640)
        self._build_ui()
        self._load()

    def _name_of(self, code):
        """按物料编码取名称；查不到返回空串（不猜测）。"""
        if not code:
            return ''
        return self._name_map.get(normalize_text(code), '')

    def _build_ui(self):
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("反复修改阈值 N（次）:"))
        self._spin = QSpinBox()
        self._spin.setRange(2, 200)
        self._spin.setValue(10)
        self._spin.valueChanged.connect(self._load)
        top.addWidget(self._spin)
        self._info = QLabel()
        self._info.setWordWrap(True)
        top.addWidget(self._info, 1)
        lay.addLayout(top)

        self._tabs = QTabWidget()
        # Tab1：反复修改榜
        self._tbl_freq = QTableWidget()
        self._tbl_freq.setColumnCount(6)
        self._tbl_freq.setHorizontalHeaderLabels(
            ["工厂", "订单日期", "流程订单", "物料编码", "物料名称", "修改次数"])
        self._tabs.addTab(self._tbl_freq, "反复修改榜")
        # Tab2：归因漂移榜（备注原因被改）
        self._tbl_note = QTableWidget()
        self._tbl_note.setColumnCount(6)
        self._tbl_note.setHorizontalHeaderLabels(
            ["工厂", "订单日期", "流程订单", "物料编码", "物料名称", "备注原因改动次数"])
        self._tabs.addTab(self._tbl_note, "归因漂移榜")
        # Tab3：按天趋势
        self._tbl_day = QTableWidget()
        self._tbl_day.setColumnCount(2)
        self._tbl_day.setHorizontalHeaderLabels(["日期", "改动次数"])
        self._tabs.addTab(self._tbl_day, "按天趋势")
        lay.addWidget(self._tabs, 1)

    def _load(self):
        if not os.path.exists(_DB_PATH):
            QMessageBox.information(self, "提示", "未找到审计库: %s" % _DB_PATH)
            return
        n = self._spin.value()
        try:
            c = sqlite3.connect(_DB_PATH)
            rows = c.execute(
                "select data_id, count(*) cnt from deviation_history "
                "where data_id<>'X' and data_id is not null "
                "group by data_id having cnt>=? order by cnt desc limit 300",
                (n,)).fetchall()
            self._fill(self._tbl_freq, rows)
            rows2 = c.execute(
                "select data_id, count(*) cnt from deviation_history "
                "where data_id<>'X' and data_id is not null and field='备注原因' "
                "group by data_id order by cnt desc limit 300").fetchall()
            self._fill(self._tbl_note, rows2, col_name="备注原因改动次数")
            rows3 = c.execute(
                "select substr(change_time,1,10) d, count(*) from deviation_history "
                "group by d order by d").fetchall()
            self._fill_day(rows3)
            tot = c.execute("select count(*) from deviation_history").fetchone()[0]
            c.close()
            self._info.setText(
                "deviation_history 共 %d 条；阈值≥%d 的反复改物料 %d 个" % (tot, n, len(rows)))
        except Exception as e:
            QMessageBox.critical(self, "错误", "读取失败: %s" % e)

    def _fill(self, tbl, rows, col_name="修改次数"):
        tbl.setRowCount(len(rows))
        for i, (did, cnt) in enumerate(rows):
            fac, od, fo, mat = _split_data_id(did)
            vals = [fac, od, fo, mat, self._name_of(mat), str(cnt)]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 5:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tbl.setItem(i, j, it)
        tbl.resizeColumnsToContents()

    def _fill_day(self, rows):
        self._tbl_day.setRowCount(len(rows))
        for i, (d, cnt) in enumerate(rows):
            self._tbl_day.setItem(i, 0, QTableWidgetItem(str(d)))
            it = QTableWidgetItem(str(cnt))
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tbl_day.setItem(i, 1, it)
        self._tbl_day.resizeColumnsToContents()
