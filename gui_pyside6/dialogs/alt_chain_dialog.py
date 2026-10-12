# -*- coding: utf-8 -*-
"""替代料长链预警看板（v43.181）。

只读 `%APPDATA%\ZPP011\config\alt_pairs.json`（替代料配对表），算出出现在多组的
物料（长链），提示「配方标准不统一」信号。与偏差分析主表解耦，不触碰 analyzer 红线区。
"""
import os
import json
from collections import defaultdict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt

_CFG_PATH = os.path.join(
    os.environ.get("APPDATA", ""), "ZPP011", "config", "alt_pairs.json")


class AltChainDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗 替代料长链预警")
        self.resize(900, 600)
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        self._info = QLabel()
        self._info.setWordWrap(True)
        lay.addWidget(self._info)
        self._tbl = QTableWidget()
        self._tbl.setColumnCount(4)
        self._tbl.setHorizontalHeaderLabels(
            ["物料编码", "物料名称", "出现组数", "关联物料"])
        lay.addWidget(self._tbl, 1)

    def _load(self):
        if not os.path.exists(_CFG_PATH):
            QMessageBox.information(self, "提示", "未找到配对表: %s" % _CFG_PATH)
            return
        try:
            d = json.load(open(_CFG_PATH, encoding="utf-8"))
            cnt = defaultdict(int)
            name = {}
            groups = defaultdict(list)   # code -> [(搭档编码, 搭档名称), ...]
            for grp in d:
                sides = [(str(s[1]), s[2]) for s in grp if len(s) >= 3]
                for code, nm in sides:
                    cnt[code] += 1
                    if code not in name:
                        name[code] = nm
                # v43.183 修 bug：关联物料取「同组内的其它成员」，而非把物料自己塞进去
                for code, _nm in sides:
                    for ocode, onm in sides:
                        if ocode != code:
                            groups[code].append((ocode, onm))
            chains = [(code, c, name[code], groups[code])
                      for code, c in cnt.items() if c > 1]
            chains.sort(key=lambda x: -x[1])
            self._tbl.setRowCount(len(chains))
            for i, (code, c, nm, grs) in enumerate(chains):
                uniq = list(dict.fromkeys(grs))
                rel = "；".join("%s %s" % (oc, onm) for oc, onm in uniq[:8])
                if len(uniq) > 8:
                    rel += " …"
                for j, v in enumerate([code, nm, str(c), rel]):
                    it = QTableWidgetItem(v)
                    if j == 2:
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self._tbl.setItem(i, j, it)
            self._tbl.resizeColumnsToContents()
            self._info.setText(
                "alt_pairs.json 共 %d 组；长链物料（出现>1组）%d 个"
                % (len(d), len(chains)))
        except Exception as e:
            QMessageBox.critical(self, "错误", "读取失败: %s" % e)
