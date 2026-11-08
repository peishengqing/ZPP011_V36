# -*- coding: utf-8 -*-
"""
flip_check_dashboard_dialog.py — 翻箱净含量守恒审核看板

看板职责
------------------------------------
把当前分析里的翻箱（ZPFX）订单逐单做「净含量守恒」校验，标出产出>投入的
疑似漏记单，供审核员直接在界面里看+筛+判断，不用去翻导出 Excel。

口径与 analysis_extra_flip.py（导出的「翻箱守恒预警」sheet）**完全同源**：
直接复用它的 parse_net_kg / _check_order，不重复实现，避免两套逻辑打架。

数据来源：主表 dev_df（_get_master_df()），筛 订单类型含 ZPFX 的行，
按流程订单分组，构造与 _scan_flip_source 同结构的 rows 喂给 _check_order。
"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

# 复用导出表的守恒逻辑（单一口径来源）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from analysis.excel_builder.analysis_extra_flip import _check_order, parse_net_kg

# 看板统一美化（v43.299 方案C）
try:
    from gui_pyside6.widgets.board_visual import apply_board_visual
except Exception:
    apply_board_visual = None

# 疑似漏记行底色（浅红）
_RED = QColor(255, 205, 210)
# 守恒/正常行底色（浅绿）
_GREEN = QColor(220, 245, 225)

# 表头（与导出「翻箱守恒预警」sheet 对齐）
_HEADERS = ['订单日期', '流程订单', '工厂', '车间', '产品物料描述',
            '产量(件)', '单件净含量(KG)', '产出总净含量(KG)',
            '投入成品件折KG', '投入散货食物KG', '投入食物合计KG',
            '差额KG(产出-投入)', '偏差率', '结论', '备注']


class FlipCheckDashboardDialog(QDialog):
    """翻箱净含量守恒审核看板：产出>投入的漏记嫌疑单，只读视图。"""

    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("翻箱守恒预警看板 - ZPFX 净含量守恒")
        self.resize(1400, 620)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.main_window = main_window
        self._verdict_filter = "全部"   # 全部 / 疑似漏记 / 守恒/正常（与 _apply_filter 比较值一致）
        self._factory_filter = "全部"  # 🔴 必须用中文「全部」，与 _apply_filter 的 != "全部" 对齐；
        self._workshop_filter = "全部"  #    若初始化成英文 'all'，首屏 _apply_filter 会把全部行滤空（真事故）
        self._rows = []                # 算好的守恒结果（订单维度）
        self._filtered = []
        self._build_ui()
        self._load(df)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ---- 顶部说明 + 筛选栏 ----
        tip = QLabel("翻箱(ZPFX)净含量守恒：产出KG 应≈投入食物KG。"
                     "<b>产出&gt;投入=凭空多出食物=拆包投入漏记</b>（标红）。"
                     "件数因拆大装小不可比，只有重量可比。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#555; font-size:12px;")
        layout.addWidget(tip)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        top.addWidget(QLabel("结论:"))
        self.cmb_verdict = QComboBox()
        self.cmb_verdict.addItems(["全部", "疑似漏记", "守恒/正常"])
        self.cmb_verdict.currentTextChanged.connect(self._on_filter_changed)
        top.addWidget(self.cmb_verdict)

        top.addWidget(QLabel("工厂:"))
        self.cmb_factory = QComboBox()
        self.cmb_factory.currentTextChanged.connect(self._on_filter_changed)
        top.addWidget(self.cmb_factory)

        top.addWidget(QLabel("车间:"))
        self.cmb_workshop = QComboBox()
        self.cmb_workshop.currentTextChanged.connect(self._on_filter_changed)
        top.addWidget(self.cmb_workshop)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color:#333; font-weight:bold;")
        top.addSpacing(12)
        top.addWidget(self.lbl_count)
        top.addStretch(1)

        self.btn_export = QPushButton("导出当前视图")
        self.btn_export.clicked.connect(self._on_export)
        top.addWidget(self.btn_export)

        layout.addLayout(top)

        # ---- 主表格 ----
        self.table = QTableWidget()
        self.table.setColumnCount(len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        # 列宽
        widths = [90, 100, 90, 70, 240, 70, 110, 120, 110, 110, 110, 130, 80, 90, 140]
        for j, w in enumerate(widths):
            self.table.setColumnWidth(j, w)
        layout.addWidget(self.table, 1)

    # ------------------------------------------------------------------ 数据
    def _load(self, df):
        """从主表 dev_df 筛 ZPFX 单、按订单分组算守恒。"""
        if df is None or df.empty:
            QMessageBox.information(self, "提示", "暂无数据，请先分析")
            self._rows = []
            self._refresh_table()
            return
        need = ['订单类型', '流程订单', '产品物料描述', '产量',
                '组件物料类型', '物料名称', '单位', '实际']
        miss = [c for c in need if c not in df.columns]
        if miss:
            QMessageBox.warning(self, "列缺失", "主表缺少翻箱守恒必要列: %s" % ", ".join(miss))
            self._rows = []
            self._refresh_table()
            return

        fx = df[df['订单类型'].astype(str).str.upper().str.contains('ZPFX', na=False)].copy()
        if fx.empty:
            QMessageBox.information(self, "提示", "本期无翻箱(ZPFX)订单")
            self._rows = []
            self._refresh_table()
            return

        def g(row, key, default=''):
            v = row.get(key, default)
            if v is None:
                return default
            s = str(v).strip()
            if s.lower() in ('', 'nan', 'none'):
                return default
            return s

        def gnum(row, key):
            v = row.get(key)
            try:
                f = float(v)
                return 0.0 if f != f else f  # NaN→0
            except (TypeError, ValueError):
                return 0.0

        # 按流程订单分组，构造与 _scan_flip_source 同结构 rows
        groups = {}
        order_keys = []
        for _, row in fx.iterrows():
            oid = g(row, '流程订单')
            if not oid:
                continue
            if oid not in groups:
                groups[oid] = []
                order_keys.append(oid)
            groups[oid].append({
                'ord': oid,
                'date': g(row, '订单日期'),
                'fac': g(row, '工厂名称') or g(row, '工厂'),
                'ws': g(row, '车间'),
                'pdesc': g(row, '产品物料描述'),
                'yield': gnum(row, '产量'),
                'mtype': g(row, '组件物料类型').upper(),
                'mname': g(row, '物料名称'),
                'unit': g(row, '单位').upper(),
                'actual': gnum(row, '实际'),
                'note': g(row, '备注'),
            })

        rows = []
        for k in order_keys:
            res = _check_order(groups[k])
            first = groups[k][0]
            net_each = parse_net_kg(first['pdesc'])
            rows.append({
                'date': first['date'], 'ord': k, 'fac': first['fac'],
                'ws': first['ws'], 'pdesc': first['pdesc'],
                'yield': first['yield'],
                'net_each': net_each,
                'out_kg': res['out_kg'], 'in_fin': res['in_fin'],
                'in_loose': res['in_loose'], 'in_food': res['in_food'],
                'diff': res['diff'], 'rate': res['rate'],
                'verdict': res['verdict'], 'note': first['note'],
            })
        self._rows = rows
        # 先建 rows 再初始化筛选下拉：combo.addItem 会触发 currentTextChanged→_apply_filter，
        # 若在 rows 就绪前触发会按空 rows 渲染出「首屏 0 行」。
        self._init_factory_combo()
        self._init_workshop_combo()
        # 末尾显式刷一次，确保首屏（未触碰筛选时）按完整 rows 渲染
        self._apply_filter()

    def _init_factory_combo(self):
        facs = sorted({r['fac'] for r in self._rows if r['fac']})
        self.cmb_factory.blockSignals(True)
        self.cmb_factory.clear()
        self.cmb_factory.addItem("全部")
        for f in facs:
            self.cmb_factory.addItem(f)
        self.cmb_factory.blockSignals(False)

    def _init_workshop_combo(self):
        wss = sorted({r['ws'] for r in self._rows if r['ws']})
        self.cmb_workshop.blockSignals(True)
        self.cmb_workshop.clear()
        self.cmb_workshop.addItem("全部")
        for w in wss:
            self.cmb_workshop.addItem(w)
        self.cmb_workshop.blockSignals(False)

    # ------------------------------------------------------------------ 筛选
    def _on_filter_changed(self, *_):
        self._verdict_filter = self.cmb_verdict.currentText()
        self._factory_filter = self.cmb_factory.currentText()
        self._workshop_filter = self.cmb_workshop.currentText()
        self._apply_filter()

    def _apply_filter(self):
        rows = self._rows
        if self._verdict_filter == "疑似漏记":
            rows = [r for r in rows if r['verdict'] == '疑似漏记']
        elif self._verdict_filter == "守恒/正常":
            rows = [r for r in rows if r['verdict'] == '守恒/正常']
        if self._factory_filter != "全部":
            rows = [r for r in rows if r['fac'] == self._factory_filter]
        if self._workshop_filter != "全部":
            rows = [r for r in rows if r['ws'] == self._workshop_filter]
        self._filtered = rows
        self._refresh_table()

    def _refresh_table(self):
        rows = self._filtered
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        n_alert = sum(1 for r in rows if r['verdict'] == '疑似漏记')
        self.lbl_count.setText("共 %d 单，疑似漏记 %d 单" % (len(rows), n_alert))
        for i, r in enumerate(rows):
            net_each_txt = ('%.4g' % r['net_each']) if r['net_each'] is not None else '解析失败'
            out_txt = ('%.3f' % r['out_kg']) if r['out_kg'] is not None else '待解析'
            diff_txt = ('%.3f' % r['diff']) if r['diff'] is not None else '—'
            rate_txt = ('%.1f%%' % (r['rate'] * 100)) if r['rate'] is not None else '—'
            vals = [r['date'], r['ord'], r['fac'], r['ws'], r['pdesc'],
                    '%g' % r['yield'], net_each_txt, out_txt,
                    '%.3f' % r['in_fin'], '%.3f' % r['in_loose'], '%.3f' % r['in_food'],
                    diff_txt, rate_txt, r['verdict'], r['note']]
            is_alert = (r['verdict'] == '疑似漏记')
            bg = _RED if is_alert else _GREEN
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setBackground(bg)
                # 数值列右对齐
                if j in (5, 6, 7, 8, 9, 10, 11, 12):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                # 结论列加粗
                if j == 13:
                    f = it.font()
                    f.setBold(is_alert)
                    it.setFont(f)
                self.table.setItem(i, j, it)
        self.table.setSortingEnabled(True)

    # ------------------------------------------------------------------ 导出
    def _on_export(self):
        """导出当前视图为 xlsx。"""
        if not self._filtered:
            QMessageBox.information(self, "提示", "当前视图无数据")
            return
        try:
            import pandas as pd
            from PySide6.QtWidgets import QFileDialog
            default = os.path.join(
                os.path.expanduser("~"), "Desktop", "翻箱守恒预警_看板导出.xlsx")
            path, _ = QFileDialog.getSaveFileName(
                self, "导出当前视图", default, "Excel (*.xlsx)")
            if not path:
                return
            out = []
            for r in self._filtered:
                out.append({
                    '订单日期': r['date'], '流程订单': r['ord'], '工厂': r['fac'],
                    '车间': r['ws'], '产品物料描述': r['pdesc'], '产量(件)': r['yield'],
                    '单件净含量(KG)': r['net_each'], '产出总净含量(KG)': r['out_kg'],
                    '投入成品件折KG': r['in_fin'], '投入散货食物KG': r['in_loose'],
                    '投入食物合计KG': r['in_food'], '差额KG(产出-投入)': r['diff'],
                    '偏差率': r['rate'], '结论': r['verdict'], '备注': r['note'],
                })
            pd.DataFrame(out, columns=_HEADERS).to_excel(path, index=False)
            QMessageBox.information(self, "已导出", "已导出 %d 行到:\n%s" % (len(out), path))
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "导出失败", str(e))
