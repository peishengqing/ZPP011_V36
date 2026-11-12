# -*- coding: utf-8 -*-
r"""替代料长链预警看板（v43.181）。

只读 `%APPDATA%\ZPP011\config\alt_pairs.json`（替代料配对表），算出出现在多组的
物料（长链），提示「配方标准不统一」信号。与偏差分析主表解耦，不触碰 analyzer 红线区。
"""
import os
import json
from collections import defaultdict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QWidget,
)
from PySide6.QtCore import Qt

from gui_pyside6.utils.table_autofit import install_adaptive, get_adaptive
from gui_pyside6.utils.board_empty_hint import set_empty_hint
from gui_pyside6.components import dialog_shell_bridge, message_box

_CFG_PATH = os.path.join(
    os.environ.get("APPDATA", ""), "ZPP011", "config", "alt_pairs.json")


from gui_pyside6.components import dialog_chrome

class AltChainDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        dialog_chrome.apply(self, dialog_chrome.TIER_LARGE, "替代料长链预警", "三级以上替代链")
        self._status_text = ""
        self._build_ui()
        self._load()
        # v43.348：专题看板统一外壳（标题栏 + 状态条 + 亮暗主题跟随），
        # 原窗口逻辑一行没动，只是把内容搬进 host 再交给 DashboardShell。
        # 原来的顶部说明 QLabel 删掉了——同一句话现在只出现在 shell 状态条里。
        self._shell = dialog_shell_bridge.install_dialog_shell(
            self, self._host, self.windowTitle(), self._status_text)

    def _set_status(self, text):
        """状态文案交给统一状态条；shell 尚未装上时只暂存，装壳时读一次。"""
        self._status_text = text
        dialog_shell_bridge.update_shell_status(self, text)

    def _build_ui(self):
        self._host = QWidget()
        lay = QVBoxLayout(self._host)
        self._tbl = QTableWidget()
        self._tbl.setColumnCount(4)
        self._tbl.setHorizontalHeaderLabels(
            ["物料编码", "物料名称", "出现组数", "关联物料"])
        lay.addWidget(self._tbl, 1)
        # v43.300：长链物料表自适应（内容+视口余量）
        install_adaptive(self._tbl, mode='content', key='alt_chain')
        get_adaptive(self._tbl).schedule_initial()

    def _load(self):
        if not os.path.exists(_CFG_PATH):
            self._set_status("未找到配对表，无法统计")
            set_empty_hint(self._tbl, "未找到替代料配对表\n请先在「导入向导」里导入替代料表。")
            message_box.info(
                self, "还没有替代料配对表",
                "长链统计要先有一份 alt_pairs.json，可在「导入向导」里导入替代料表。",
                detail=_CFG_PATH)
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
            # 0 行时表格是一片白：说清是「真的没有长链」而不是「读不出来」
            set_empty_hint(self._tbl, "" if chains else
                           "没有长链物料\n每个物料只出现在 1 组替代配对里。")
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
            ctrl = get_adaptive(self._tbl)
            if ctrl is not None:
                ctrl.request_refit(0)
            else:
                self._tbl.resizeColumnsToContents()
            self._set_status(
                "alt_pairs.json 共 %d 组；长链物料（出现>1组）%d 个"
                % (len(d), len(chains)))
        except Exception as e:
            message_box.error(
                self, "读取配对表失败",
                "文件在，但读不出内容，可能不是有效的 JSON 或已损坏。",
                exc=e, detail=_CFG_PATH)
