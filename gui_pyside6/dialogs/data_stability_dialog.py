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
    QTabWidget, QSpinBox, QMessageBox, QWidget, QPushButton,
)
from PySide6.QtCore import Qt

from gui_pyside6.utils.table_autofit import install_adaptive, get_adaptive

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
        # 调用方（dashboard_manager/dashboard_controller）传入 MainWindow 作为 parent，
        # 故 parent 即 MainWindow 实例；用于取主表 DataFrame 计算备注覆盖率。
        self._mw = parent
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
        install_adaptive(self._tbl_freq, mode='content', key='stab_freq')
        # Tab2：归因漂移榜（备注原因被改）
        self._tbl_note = QTableWidget()
        self._tbl_note.setColumnCount(6)
        self._tbl_note.setHorizontalHeaderLabels(
            ["工厂", "订单日期", "流程订单", "物料编码", "物料名称", "备注原因改动次数"])
        self._tabs.addTab(self._tbl_note, "归因漂移榜")
        install_adaptive(self._tbl_note, mode='content', key='stab_note')
        # Tab3：按天趋势
        self._tbl_day = QTableWidget()
        self._tbl_day.setColumnCount(2)
        self._tbl_day.setHorizontalHeaderLabels(["日期", "改动次数"])
        self._tabs.addTab(self._tbl_day, "按天趋势")
        install_adaptive(self._tbl_day, mode='content', key='stab_day')
        # Tab4：数据质量评分卡
        self._score_widget = QWidget()
        s_lay = QVBoxLayout(self._score_widget)
        self._tbl_score = QTableWidget()
        self._tbl_score.setColumnCount(3)
        self._tbl_score.setHorizontalHeaderLabels(["指标", "数值", "说明"])
        install_adaptive(self._tbl_score, mode='content', key='stab_score')
        s_lay.addWidget(self._tbl_score, 1)
        self._score_concl = QLabel()
        self._score_concl.setWordWrap(True)
        s_lay.addWidget(self._score_concl)
        # v43.310 扣分证据入口：把三维度笼统结论落到 Top-N 具体证据
        self._btn_explain = QPushButton("🔍 查看扣分证据")
        self._btn_explain.clicked.connect(self._show_score_explain)
        s_lay.addWidget(self._btn_explain)
        self._tabs.addTab(self._score_widget, "数据质量评分卡")
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
            self._fill_score(c)
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
        ctrl = get_adaptive(tbl)
        if ctrl is not None:
            ctrl.request_refit(0)
        else:
            tbl.resizeColumnsToContents()

    def _fill_day(self, rows):
        self._tbl_day.setRowCount(len(rows))
        for i, (d, cnt) in enumerate(rows):
            self._tbl_day.setItem(i, 0, QTableWidgetItem(str(d)))
            it = QTableWidgetItem(str(cnt))
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tbl_day.setItem(i, 1, it)
        ctrl = get_adaptive(self._tbl_day)
        if ctrl is not None:
            ctrl.request_refit(0)
        else:
            self._tbl_day.resizeColumnsToContents()

    @staticmethod
    def _count_alt_chains():
        """统计替代料长链数（出现于 >1 个组的物料编码数）。

        读 %APPDATA%\\ZPP011\\config\\alt_pairs.json（外层 list 是「组」，
        每组是 2+ 个 [工厂, 编码, 名称] 三元组）。复用 alt_chain_dialog 的算法，
        在本文件内联复制，不改 alt_chain_dialog.py。

        返回 (chains_count, total_materials)；文件不存在/解析失败/格式异常
        → 返回 (0, 0) 且不抛未捕获异常。
        """
        import json
        from collections import defaultdict
        cfg = os.path.join(
            os.environ.get("APPDATA", ""), "ZPP011", "config", "alt_pairs.json")
        try:
            if not os.path.exists(cfg):
                return (0, 0)
            with open(cfg, encoding="utf-8") as f:
                d = json.load(f)
            cnt = defaultdict(int)
            for grp in d:
                if not isinstance(grp, list):
                    continue
                for s in grp:
                    if not isinstance(s, (list, tuple)) or len(s) < 3:
                        continue
                    code = str(s[1])
                    cnt[code] += 1
            chains = [(code, c) for code, c in cnt.items() if c > 1]
            return (len(chains), len(cnt))
        except Exception:
            return (0, 0)

    def _fill_score(self, c):
        """数据质量评分卡：聚合三个既有指标 → 0–100 总评分并填充 Tab4。

        权重：备注覆盖率 50% / 归因漂移率 30% / 替代料长链数 20%。
        """
        # 1) 归因漂移率（audit.db：deviation_history 中 field='备注原因' 占比）
        cnt_note = c.execute(
            "select count(*) from deviation_history "
            "where data_id<>'X' and data_id is not null and field='备注原因'"
        ).fetchone()[0]
        tot_dev = c.execute(
            "select count(*) from deviation_history "
            "where data_id<>'X' and data_id is not null"
        ).fetchone()[0]
        drift_rate = (cnt_note / tot_dev) if tot_dev else 0.0

        # 2) 替代料长链数
        chains_count, total_materials = self._count_alt_chains()

        # 3) 备注覆盖率（主表当前 DataFrame）
        coverage = None
        try:
            if self._mw is not None and hasattr(self._mw, "source_model"):
                _mdf = self._mw.source_model.getDataFrame()
                if _mdf is not None and "备注原因" in _mdf.columns and len(_mdf) > 0:
                    _has = _mdf["备注原因"].notna() & (
                        _mdf["备注原因"].astype(str).str.strip() != "")
                    coverage = float(_has.sum()) / len(_mdf)
        except Exception:
            coverage = None

        # 三项子分（0–100）
        coverage_sub = coverage * 100.0 if coverage is not None else None
        drift_sub = 100.0 * (1.0 - min(drift_rate, 1.0))
        if total_materials > 0:
            chain_ratio = chains_count / total_materials
        else:
            chain_ratio = 0.0
        chain_sub = 100.0 * (1.0 - min(chain_ratio, 1.0))

        # 总评分（加权综合）
        if coverage_sub is not None:
            final = 0.5 * coverage_sub + 0.3 * drift_sub + 0.2 * chain_sub
        else:
            # 备注覆盖率缺失，按其余两项加权归一（0.3+0.2=0.5）
            final = (0.3 * drift_sub + 0.2 * chain_sub) / 0.5

        # 填充评分表
        self._tbl_score.setRowCount(4)
        rows_data = [
            ("备注覆盖率", ("%.1f%%" % (coverage * 100)) if coverage is not None else "主表未加载", "权重 50%"),
            ("归因漂移率", "%.1f%%" % (drift_rate * 100), "权重 30%（越低越好）"),
            ("替代料长链数", "%d 个（共 %d 物料）" % (chains_count, total_materials), "权重 20%（越少越好）"),
            ("总评分", "%.1f / 100" % final, "加权综合"),
        ]
        for i, (k, v, note) in enumerate(rows_data):
            self._tbl_score.setItem(i, 0, QTableWidgetItem(k))
            self._tbl_score.setItem(i, 1, QTableWidgetItem(v))
            self._tbl_score.setItem(i, 2, QTableWidgetItem(note))
        ctrl = get_adaptive(self._tbl_score)
        if ctrl is not None:
            ctrl.request_refit(0)
        else:
            self._tbl_score.resizeColumnsToContents()

        # 一句话结论（按最差子项给建议）
        concl = []
        if coverage is not None and coverage < 0.5:
            concl.append("备注覆盖率偏低，建议补全偏差备注原因")
        if drift_rate > 0.3:
            concl.append("归因漂移偏高，建议复核 TOP 反复修改物料")
        if chains_count > 10:
            concl.append("替代料长链较多，建议复核替代料配对")
        if not concl:
            concl.append("数据质量良好")
        note_suffix = "" if coverage_sub is not None else "；备注覆盖率缺失，按其余两项加权"
        self._score_concl.setText("；".join(concl) + note_suffix)

    def _show_score_explain(self):
        """v43.310 打开「为什么分低」扣分证据弹窗（方案 A：不改 compute_scorecard）。"""
        mdf = None
        try:
            if self._mw is not None and hasattr(self._mw, "source_model"):
                mdf = self._mw.source_model.getDataFrame()
        except Exception:
            mdf = None
        from gui_pyside6.dialogs.scorecard_explain_dialog import ScorecardExplainDialog
        dlg = ScorecardExplainDialog(mdf, parent=self)
        dlg.exec()
