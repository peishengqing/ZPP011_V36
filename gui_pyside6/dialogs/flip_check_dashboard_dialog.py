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
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout,
)

# 复用导出表的守恒逻辑（单一口径来源）：食品走 KG 守恒（_check_order/_food_kg_of/
# parse_net_kg），饮料走总容器数守恒（check_drink_order/_drink_container_of/
# parse_pack），路由统一走 split_by_factory 分厂 —— 与导出的四张 sheet 完全同源，
# 看板绝不自己再写一套判别，否则跟导出对不上（历史事故 v43.183 / v43.323 / v43.324）。
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from analysis.excel_builder.analysis_extra_flip import (
    _check_order, _drink_container_of, _food_kg_of, check_drink_order,
    parse_net_kg, parse_pack, split_by_factory)
from gui_pyside6.utils.board_empty_hint import NO_DATA_TEXT, set_empty_hint
from gui_pyside6.utils.row_number_gutter import enable_row_numbers
from utils.theme_manager import Thm

# 看板统一美化（v43.299 方案C）
try:
    from gui_pyside6.widgets.board_visual import apply_board_visual
except Exception:
    apply_board_visual = None

# 疑似漏记行底色（浅红）
_RED = QColor(255, 205, 210)
# 守恒/正常行底色（浅绿）
_GREEN = QColor(220, 245, 225)

# 表头（与导出四张 sheet 一一对齐）
# ⚠️ 新列一律追加在**表尾**：_fill_* 里数值列/结论列是行号索引，插在中间会让
# 这些索引整体失效（历史坑：换列必查索引）。
#
# 食品结论页（导出「翻箱守恒预警」）：按净含量 KG 守恒。
_HEADERS = ['订单日期', '流程订单', '工厂', '车间', '产品物料描述',
            '产量(件)', '单件净含量(KG)', '产出总净含量(KG)',
            '投入成品件折KG', '投入散货食物KG', '投入食物合计KG',
            '差额KG(产出-投入)', '偏差率', '结论', '备注',
            '产品物料编码', '组件物料编码', '组件物料名称']
# 饮料结论页（导出「饮料翻箱守恒」）：按总容器数守恒，指标列与食品不同（容器数而非KG）。
_DRINK_HEADERS = ['订单日期', '流程订单', '工厂', '车间', '产品物料编码',
                  '产品物料描述', '产量(件)', '容器形式', '净含量单位',
                  '单件容器数', '单容器净含量', '产出总容器数', '投入总容器数',
                  '差额容器数', '偏差率', '结论', '备注']

# 组件明细页表头：与导出「翻箱组件明细」sheet 同源（analysis_extra_flip._build_flip_detail），
# 末尾多挂一列「结论」，让明细行带着所属单的守恒结论——筛出疑似漏记单时，
# 底下这些行才是真正要核对的那批组件。
# v43.368：明细页原来只有「实际/计入KG/结论」，看不到订单级的产量/单件净含量(定额)/
# 产出总净含量/投入合计/差额，用户反映「看不出到底守不守恒」。把结论页那几个守恒
# 数值列追加到明细页尾，每行组件自带所属单的守恒数字，不用切回结论页对照。
# ⚠️ 新列只许追加在**表尾**：_fill_detail 里 11/13/12 是行号索引，插中间会整体失效。
_DETAIL_HEADERS = ['订单日期', '流程订单', '工厂', '车间',
                   '产品物料编码', '产品物料描述', '产量(件)',
                   '组件物料编码', '组件物料名称', '组件物料类型', '组件物料类型描述',
                   '单位', '实际', '是否计入食物投入', '计入KG(参考)', '备注', '结论',
                   '单件净含量(KG)', '产出总净含量(KG)',
                   '投入食物合计KG', '差额KG(产出-投入)', '偏差率']
# 饮料明细页（导出「饮料翻箱组件明细」）：一行一组件，被排除的都留「排除原因」，
# 绝不静默丢行。判别与主表共用 _drink_container_of，可逐单对账到「投入总容器数」。
_DRINK_DETAIL_HEADERS = ['订单日期', '流程订单', '工厂', '车间',
                         '产品物料编码', '产品物料描述', '产量(件)',
                         '组件物料编码', '组件物料名称', '组件物料类型',
                         '组件物料类型描述', '单位', '实际',
                         '是否计入容器数', '计入容器数(参考)', '排除原因', '备注']

# 总表页（食+饮合并·结论）：食品/饮料订单混排一屏，按「口径」列区分用哪套守恒
# （KG vs 容器数），结论/偏差率两厂同口径可比；「工厂」列看得出属哪家。
_ALL_HEADERS = ['订单日期', '流程订单', '工厂', '车间', '产品物料编码',
                '产品物料描述', '产量(件)', '口径', '结论', '偏差率']


from gui_pyside6.components import dialog_chrome

class FlipCheckDashboardDialog(QDialog):
    """翻箱净含量守恒审核看板：产出>投入的漏记嫌疑单，只读视图。"""

    def __init__(self, df, main_window, parent=None):
        super().__init__(parent)
        dialog_chrome.apply(self, dialog_chrome.TIER_BOARD, "翻箱守恒预警看板", "ZPFX 净含量守恒")
        self.main_window = main_window
        self._verdict_filter = "全部"   # 全部 / 疑似漏记 / 守恒/正常 / 待人工确认
        self._workshop_filter = "全部"   # 🔴 必须用中文「全部」，与 _match 的 != "全部" 对齐；
                                         #    若初始化成英文 'all'，首屏 _apply_filter 会把行滤空（真事故）
        # 分厂四个数据源（工厂现在是「页签」，不再是筛选器）：食品走 KG 守恒、饮料走容器数守恒。
        self._food_orders = []          # 食品订单级（一单一行）
        self._food_detail = []          # 食品组件级（一行一组件）
        self._drink_orders = []         # 饮料订单级
        self._drink_detail = []         # 饮料组件级
        # 各自筛完的视图（_apply_filter 刷新）
        self._food_orders_f = []
        self._food_detail_f = []
        self._drink_orders_f = []
        self._drink_detail_f = []
        # 总表：食+饮订单合并一屏（各自「口径」不同，靠「口径」列区分），各自筛完视图
        self._all_orders = []
        self._all_orders_f = []
        # 未识别工厂（既非食品也非饮料）的订单，不静默丢：单独留痕提示
        self._unknown_orders = []
        self._build_ui()
        self._load(df)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ---- 顶部说明 + 筛选栏 ----
        tip = QLabel(
            "翻箱(ZPFX)守恒校验。"
            "<b>食品厂</b>按净含量 KG 守恒（产出KG≈投入食物KG），"
            "<b>饮料厂</b>按总容器数守恒（产出容器≈投入容器）；"
            "<b>产出&gt;投入=凭空多出=拆包投入漏记</b>（标红）。"
            "拆大装小件数不可比，只比同口径的 KG / 容器数。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:%s; font-size:12px;" % Thm.color("textMuted"))
        layout.addWidget(tip)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        top.addWidget(QLabel("结论:"))
        self.cmb_verdict = QComboBox()
        self.cmb_verdict.addItems(["全部", "疑似漏记", "守恒/正常", "待人工确认"])
        self.cmb_verdict.currentTextChanged.connect(self._on_filter_changed)
        top.addWidget(self.cmb_verdict)

        top.addWidget(QLabel("车间:"))
        self.cmb_workshop = QComboBox()
        self.cmb_workshop.currentTextChanged.connect(self._on_filter_changed)
        top.addWidget(self.cmb_workshop)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color:%s; font-weight:bold;" % Thm.color("text"))
        top.addSpacing(12)
        top.addWidget(self.lbl_count)
        top.addStretch(1)

        self.btn_export = QPushButton("导出当前视图")
        self.btn_export.clicked.connect(self._on_export)
        top.addWidget(self.btn_export)

        layout.addLayout(top)

        # 未识别工厂提示（食品/饮料以外的厂不猜、不静默丢，单独留痕）
        self.lbl_factory_hint = QLabel("")
        self.lbl_factory_hint.setWordWrap(True)
        self.lbl_factory_hint.setStyleSheet("color:%s; font-size:12px;" % Thm.color("warn"))
        self.lbl_factory_hint.setVisible(False)
        layout.addWidget(self.lbl_factory_hint)

        # ---- 主表格：食品/饮料各分「结论页（一单一行）+ 明细页（一行一组件）」共 4 页，
        #      同一套「结论/车间」筛选同时作用于同厂的两页。工厂=页签，不再是筛选器。----
        self.tabs = QTabWidget()
        self.food_table = self._make_table(_HEADERS, [90, 100, 90, 70, 240, 70, 110, 120,
                                                       110, 110, 110, 130, 80, 90, 140,
                                                       120, 240, 280])
        self.food_table_detail = self._make_table(
            _DETAIL_HEADERS, [90, 100, 90, 70, 120, 240, 70, 120, 280, 90, 110,
                              60, 90, 130, 110, 140, 90,
                              110, 120, 110, 130, 70])
        self.drink_table = self._make_table(_DRINK_HEADERS, [80, 100, 90, 70, 120, 240,
                                                             70, 90, 90, 90, 110,
                                                             110, 110, 110, 80, 90, 240])
        self.drink_table_detail = self._make_table(
            _DRINK_DETAIL_HEADERS, [80, 100, 90, 70, 120, 240, 70, 120, 280, 90,
                                    110, 60, 90, 120, 130, 220, 140])
        # 总表：食+饮订单合并一屏（「口径」列区分 KG / 容器数守恒）
        self.all_table = self._make_table(
            _ALL_HEADERS, [90, 100, 90, 70, 120, 240, 70, 90, 90, 70])
        self.tabs.addTab(self.all_table, "总表·食+饮")
        self.tabs.addTab(self.food_table, "食品·守恒结论")
        self.tabs.addTab(self.food_table_detail, "食品·组件明细")
        self.tabs.addTab(self.drink_table, "饮料·守恒结论")
        self.tabs.addTab(self.drink_table_detail, "饮料·组件明细")
        self.tabs.currentChanged.connect(lambda *_: self._refresh_view())
        layout.addWidget(self.tabs, 1)

    def _make_table(self, headers, widths):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        enable_row_numbers(t)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setAlternatingRowColors(True)
        t.setSortingEnabled(True)
        hh = t.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        for j, w in enumerate(widths):
            t.setColumnWidth(j, w)
        return t

    # ------------------------------------------------------------------ 数据
    def _load(self, df):
        """从主表 dev_df 筛 ZPFX 单、按订单分组算守恒。"""
        if df is None or df.empty:
            QMessageBox.information(self, "提示", "暂无数据，请先分析")
            self._clear_data()
            self._refresh_factory_hint()
            self._refresh_tables()
            self._refresh_count_label()
            return
        need = ['订单类型', '流程订单', '产品物料号码', '产品物料描述', '产量',
                '组件物料类型', '物料编码', '物料名称', '单位', '实际']
        miss = [c for c in need if c not in df.columns]
        if miss:
            QMessageBox.warning(self, "列缺失", "主表缺少翻箱守恒必要列: %s" % ", ".join(miss))
            self._clear_data()
            self._refresh_factory_hint()
            self._refresh_tables()
            self._refresh_count_label()
            return

        fx = df[df['订单类型'].astype(str).str.upper().str.contains('ZPFX', na=False)].copy()
        if fx.empty:
            QMessageBox.information(self, "提示", "本期无翻箱(ZPFX)订单")
            self._clear_data()
            self._refresh_factory_hint()
            self._refresh_tables()
            self._refresh_count_label()
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
                'pno': g(row, '产品物料号码'),
                'pdesc': g(row, '产品物料描述'),
                'yield': gnum(row, '产量'),
                'mtype': g(row, '组件物料类型').upper(),
                'mtdesc': g(row, '组件物料类型描述'),
                'mcode': g(row, '物料编码'),
                'mname': g(row, '物料名称'),
                'unit': g(row, '单位').upper(),
                'actual': gnum(row, '实际'),
                'note': g(row, '备注'),
            })

        # 分厂路由（单一来源 split_by_factory，与导出四张 sheet 同源）：
        # 摊平成分组前组件行再分流。同单所有组件行 fac 相同，分流后按 ord 重新分组。
        flat = [dict(x) for k in order_keys for x in groups[k]]
        food_rows, drink_rows, unknown_rows = split_by_factory(flat)

        def regroup(rows):
            g2, ks = {}, []
            for r in rows:
                k = r['ord']
                if k not in g2:
                    g2[k] = []
                    ks.append(k)
                g2[k].append(r)
            return g2, ks

        food_groups, food_keys = regroup(food_rows)
        drink_groups, drink_keys = regroup(drink_rows)
        _, unknown_keys = regroup(unknown_rows)

        # 未识别工厂留痕（不猜、不静默丢，单独提示）
        self._unknown_orders = [(k, groups[k][0]['fac']) for k in unknown_keys]

        self._food_orders = self._build_food_orders(food_groups, food_keys)
        self._food_detail = self._build_food_detail(food_groups, food_keys)
        self._drink_orders = self._build_drink_orders(drink_groups, drink_keys)
        self._drink_detail = self._build_drink_detail(drink_groups, drink_keys)
        # 总表：食+饮订单合并（各带「口径」），一屏看清所有翻箱单结论
        self._all_orders = self._food_orders + self._drink_orders

        # 先建数据再初始化筛选下拉：combo.addItem 会触发 currentTextChanged→_apply_filter，
        # 若在数据就绪前触发会按空列表渲染出「首屏 0 行」。
        self._init_workshop_combo()
        self._refresh_factory_hint()
        # 末尾显式刷一次，确保首屏（未触碰筛选时）按完整数据渲染
        self._apply_filter()

    # -- 食品侧（净含量 KG 守恒）：与导出「翻箱守恒预警/翻箱组件明细」同源 ----
    def _build_food_orders(self, groups, keys):
        """食品订单级：一单一行，_check_order 算 KG 守恒。"""
        out = []
        for k in keys:
            g = groups[k]
            res = _check_order(g)
            first = g[0]
            net_each = parse_net_kg(first['pdesc'])
            out.append({
                'date': first['date'], 'ord': k, 'fac': first['fac'],
                'ws': first['ws'], 'pdesc': first['pdesc'],
                'yield': first['yield'], 'net_each': net_each,
                'out_kg': res['out_kg'], 'in_fin': res['in_fin'],
                'in_loose': res['in_loose'], 'in_food': res['in_food'],
                'diff': res['diff'], 'rate': res['rate'],
                'verdict': res['verdict'], 'note': first['note'],
                'pno': first['pno'], '口径': 'KG守恒',
                # 组件编码/名称按单拼全组件（含包材），悬停换行展开，不撑爆行高
                'mcodes': '；'.join(x['mcode'] for x in g if x['mcode']),
                'mnames': '；'.join(x['mname'] for x in g if x['mname']),
            })
        return out

    def _build_food_detail(self, groups, keys):
        """食品组件级：一行一组件，判别用同一个 _food_kg_of，明细加起来能回对结论页。"""
        out = []
        for k in keys:
            g = groups[k]
            res = _check_order(g)
            first = g[0]
            net_each = parse_net_kg(first['pdesc'])
            for x in g:
                flag, kg = _food_kg_of(x)
                out.append({
                    'date': x['date'], 'ord': x['ord'], 'fac': x['fac'],
                    'ws': x['ws'], 'pno': x['pno'], 'pdesc': x['pdesc'],
                    'mcode': x['mcode'], 'mname': x['mname'],
                    'mtype': x['mtype'], 'mtdesc': x['mtdesc'],
                    'unit': x['unit'], 'actual': x['actual'],
                    'flag': flag, 'kg': kg, 'note': x['note'],
                    'verdict': res['verdict'],
                    # 订单级守恒数字（同一单所有组件行共用），明细页直接看出守不守恒
                    'yield': first['yield'], 'net_each': net_each,
                    'out_kg': res['out_kg'], 'in_food': res['in_food'],
                    'diff': res['diff'], 'rate': res['rate'],
                })
        return out

    # -- 饮料侧（总容器数守恒）：与导出「饮料翻箱守恒/饮料翻箱组件明细」同源 --
    def _build_drink_orders(self, groups, keys):
        """饮料订单级：一单一行，check_drink_order 算容器数守恒。"""
        out = []
        for k in keys:
            g = groups[k]
            res = check_drink_order(g)
            first = g[0]
            notes = [x for x in (res['reason'], first['note']) if x]
            out.append({
                'date': first['date'], 'ord': k, 'fac': first['fac'],
                'ws': first['ws'], 'pno': first['pno'], 'pdesc': first['pdesc'],
                'yield': first['yield'],
                'container': res['container'], 'unit': res['unit'],
                'n': res['n'], 'per': res['per'],
                'out_containers': res['out_containers'],
                'in_containers': res['in_containers'],
                'diff': res['diff_containers'], 'rate': res['rate'],
                'verdict': res['verdict'], 'note': '；'.join(notes),
                '口径': '容器数守恒',
                'mcodes': '；'.join(x['mcode'] for x in g if x['mcode']),
                'mnames': '；'.join(x['mname'] for x in g if x['mname']),
            })
        return out

    def _build_drink_detail(self, groups, keys):
        """饮料组件级：一行一组件，全组件都列（含 Z005/Z002/Z001/实际=0），
        被排除的在「排除原因」留痕，绝不静默丢行。判别与主表共用 _drink_container_of。"""
        # 每单先算产出 pack，供 _drink_container_of 比对容器形式/单位；顺带记下所属单结论
        out_pack_by_order, verdict_by_order = {}, {}
        for k in keys:
            out_pack_by_order[k] = parse_pack(groups[k][0]['pdesc'])
            verdict_by_order[k] = check_drink_order(groups[k])['verdict']
        out = []
        for k in keys:
            opack = out_pack_by_order[k]
            for r in groups[k]:
                flag, containers, reason = _drink_container_of(r, opack)
                out.append({
                    'date': r['date'], 'ord': r['ord'], 'fac': r['fac'],
                    'ws': r['ws'], 'pno': r['pno'], 'pdesc': r['pdesc'],
                    'mcode': r['mcode'], 'mname': r['mname'],
                    'mtype': r['mtype'], 'mtdesc': r['mtdesc'],
                    'unit': r['unit'], 'actual': r['actual'],
                    'flag': flag, 'containers': containers, 'reason': reason,
                    'note': r['note'], 'verdict': verdict_by_order[k],
                    'yield': r.get('yield', 0),
                })
        return out

    def _clear_data(self):
        for attr in ("_food_orders", "_food_detail", "_drink_orders",
                     "_drink_detail", "_food_orders_f", "_food_detail_f",
                     "_drink_orders_f", "_drink_detail_f", "_all_orders",
                     "_all_orders_f", "_unknown_orders"):
            setattr(self, attr, [])

    def _init_workshop_combo(self):
        # 车间取食品+饮料两厂并集（工厂现在是页签，车间仍作筛选器）
        wss = sorted({r['ws'] for r in self._food_orders + self._drink_orders
                      if r['ws']})
        self.cmb_workshop.blockSignals(True)
        self.cmb_workshop.clear()
        self.cmb_workshop.addItem("全部")
        for w in wss:
            self.cmb_workshop.addItem(w)
        self.cmb_workshop.blockSignals(False)

    def _refresh_factory_hint(self):
        """未识别工厂留痕：食品/饮料以外的厂不猜、不静默丢，单独提示。"""
        if self._unknown_orders:
            facs = "、".join(sorted({fac for _k, fac in self._unknown_orders}))
            self.lbl_factory_hint.setText(
                "另有 %d 单未识别工厂（%s）不属食品/饮料厂，未纳入守恒计算。"
                % (len(self._unknown_orders), facs))
            self.lbl_factory_hint.setVisible(True)
        else:
            self.lbl_factory_hint.setVisible(False)

    # ------------------------------------------------------------------ 筛选
    def _on_filter_changed(self, *_):
        self._verdict_filter = self.cmb_verdict.currentText()
        self._workshop_filter = self.cmb_workshop.currentText()
        self._apply_filter()

    def _apply_filter(self):
        # 同一套「结论/车间」筛选同时作用于同厂两页；切页只换「看单/看组件」，不换数据范围。
        self._food_orders_f = self._match(self._food_orders)
        self._food_detail_f = self._match(self._food_detail)
        self._drink_orders_f = self._match(self._drink_orders)
        self._drink_detail_f = self._match(self._drink_detail)
        self._all_orders_f = self._match(self._all_orders)
        self._refresh_tables()
        self._refresh_count_label()

    def _match(self, rows):
        if self._verdict_filter != "全部":
            rows = [r for r in rows if r['verdict'] == self._verdict_filter]
        if self._workshop_filter != "全部":
            rows = [r for r in rows if r['ws'] == self._workshop_filter]
        return rows

    def _refresh_tables(self):
        self._fill_food_orders(self._food_orders_f)
        self._fill_food_detail(self._food_detail_f)
        self._fill_drink_orders(self._drink_orders_f)
        self._fill_drink_detail(self._drink_detail_f)
        self._fill_all_orders(self._all_orders_f)
        # 空表写清为什么空（四张都管，隐藏页切回来提示别过期）：
        # 没有已读/未读，只有「筛没了」和「本来就没数据」两种。
        for idx in range(self.tabs.count()):
            table, shown, total = self._active_tables(idx)
            set_empty_hint(table, "" if shown else (
                NO_DATA_TEXT if not total
                else "没有符合条件的记录（原始 %d 条）\n"
                     "请把上方的「结论 / 车间」切回「全部」。" % len(total)))

    def _active_tables(self, idx):
        """页签 → (表, 筛完的行, 全量行)：0 总表 / 1 食品结论 / 2 食品明细 / 3 饮料结论 / 4 饮料明细。"""
        if idx == 0:
            return self.all_table, self._all_orders_f, self._all_orders
        if idx == 1:
            return self.food_table, self._food_orders_f, self._food_orders
        if idx == 2:
            return self.food_table_detail, self._food_detail_f, self._food_detail
        if idx == 3:
            return self.drink_table, self._drink_orders_f, self._drink_orders
        return self.drink_table_detail, self._drink_detail_f, self._drink_detail

    def _refresh_view(self):
        """切页只换「看单/看组件」，数据不动；只重算当前页计数（表格已填好）。"""
        self._refresh_count_label()

    def _refresh_count_label(self):
        """计数跟着当前页说人话：结论页报「几单、疑似漏记几单」，明细页报「几行组件、涉及几单」。"""
        idx = self.tabs.currentIndex()
        if idx == 0:   # 总表
            rows = self._all_orders_f
            n_alert = sum(1 for r in rows if r['verdict'] == '疑似漏记')
            n_food = sum(1 for r in rows if r['口径'] == 'KG守恒')
            self.lbl_count.setText(
                "食+饮共 %d 单（食品 %d / 饮料 %d），疑似漏记 %d"
                % (len(rows), n_food, len(rows) - n_food, n_alert))
        elif idx == 1:
            rows = self._food_orders_f
            n_alert = sum(1 for r in rows if r['verdict'] == '疑似漏记')
            self.lbl_count.setText("食品 %d 单，疑似漏记 %d" % (len(rows), n_alert))
        elif idx == 2:
            rows = self._food_detail_f
            self.lbl_count.setText("食品 %d 行组件 · 涉及 %d 单"
                                   % (len(rows), len({r['ord'] for r in rows})))
        elif idx == 3:
            rows = self._drink_orders_f
            n_alert = sum(1 for r in rows if r['verdict'] == '疑似漏记')
            self.lbl_count.setText("饮料 %d 单，疑似漏记 %d" % (len(rows), n_alert))
        else:   # idx == 4 饮料明细
            rows = self._drink_detail_f
            self.lbl_count.setText("饮料 %d 行组件 · 涉及 %d 单"
                                   % (len(rows), len({r['ord'] for r in rows})))

    # ---- 食品侧两张表 ----
    def _fill_food_orders(self, rows):
        self._fill_table(self.food_table, rows,
                         self._food_order_vals, self._food_order_cell)

    def _food_order_vals(self, r):
        net_each_txt = ('%.4g' % r['net_each']) if r['net_each'] is not None else '解析失败'
        out_txt = ('%.3f' % r['out_kg']) if r['out_kg'] is not None else '待解析'
        diff_txt = ('%.3f' % r['diff']) if r['diff'] is not None else '—'
        rate_txt = ('%.1f%%' % (r['rate'] * 100)) if r['rate'] is not None else '—'
        return [r['date'], r['ord'], r['fac'], r['ws'], r['pdesc'],
                '%g' % r['yield'], net_each_txt, out_txt,
                '%.3f' % r['in_fin'], '%.3f' % r['in_loose'], '%.3f' % r['in_food'],
                diff_txt, rate_txt, r['verdict'], r['note'],
                r['pno'], r['mcodes'], r['mnames']]

    def _food_order_cell(self, i, j, v, r):
        if j >= 15:   # 编码/名称拼接列：悬停展开全组件
            v.setToolTip(str(v).replace('；', '\n'))
        if j in (5, 6, 7, 8, 9, 10, 11, 12):   # 数值列右对齐
            v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if j == 13:   # 结论列：疑似漏记加粗
            f = v.font()
            f.setBold(r['verdict'] == '疑似漏记')
            v.setFont(f)

    def _fill_food_detail(self, rows):
        self._fill_table(self.food_table_detail, rows,
                         self._food_detail_vals, self._food_detail_cell)

    def _food_detail_vals(self, r):
        net_each_txt = ('%.4g' % r['net_each']) if r.get('net_each') is not None else '解析失败'
        out_txt = ('%.3f' % r['out_kg']) if r.get('out_kg') is not None else '待解析'
        diff_txt = ('%.3f' % r['diff']) if r.get('diff') is not None else '—'
        rate_txt = ('%.1f%%' % (r['rate'] * 100)) if r.get('rate') is not None else '—'
        return [r['date'], r['ord'], r['fac'], r['ws'], r['pno'], r['pdesc'],
                '%g' % r.get('yield', 0),
                r['mcode'], r['mname'], r['mtype'], r['mtdesc'], r['unit'],
                '%g' % r['actual'], r['flag'], '%.6g' % r['kg'],
                r['note'], r['verdict'],
                net_each_txt, out_txt,
                '%.3f' % r.get('in_food', 0), diff_txt, rate_txt]

    def _food_detail_cell(self, i, j, v, r):
        if j in (6, 12, 14, 17, 18, 19, 20, 21):  # 产量/实际/计入KG + 订单级守恒数值列
            v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if j == 13:   # 是否计入食物投入：计入的加粗
            f = v.font()
            f.setBold(r['flag'] == '是')
            v.setFont(f)

    # ---- 饮料侧两张表 ----
    def _fill_drink_orders(self, rows):
        self._fill_table(self.drink_table, rows,
                         self._drink_order_vals, self._drink_order_cell)

    def _drink_order_vals(self, r):
        out_txt = ('%.3f' % r['out_containers']) if r['out_containers'] is not None else '待解析'
        diff_txt = ('%.3f' % r['diff']) if r['diff'] is not None else '—'
        rate_txt = ('%.1f%%' % (r['rate'] * 100)) if r['rate'] is not None else '—'
        return [r['date'], r['ord'], r['fac'], r['ws'], r['pno'], r['pdesc'],
                '%g' % r['yield'],
                r['container'] if r['container'] is not None else '解析失败',
                r['unit'] if r['unit'] is not None else '—',
                r['n'] if r['n'] is not None else '—',
                ('%g' % r['per']) if r['per'] is not None else '—',
                out_txt, '%.3f' % r['in_containers'], diff_txt, rate_txt,
                r['verdict'], r['note']]

    def _drink_order_cell(self, i, j, v, r):
        if j in (6, 10, 11, 12, 13, 14):   # 数值列右对齐
            v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if j == 15:   # 结论列：疑似漏记加粗
            f = v.font()
            f.setBold(r['verdict'] == '疑似漏记')
            v.setFont(f)

    def _fill_drink_detail(self, rows):
        self._fill_table(self.drink_table_detail, rows,
                         self._drink_detail_vals, self._drink_detail_cell)

    def _drink_detail_vals(self, r):
        return [r['date'], r['ord'], r['fac'], r['ws'], r['pno'], r['pdesc'],
                '%g' % r.get('yield', 0),
                r['mcode'], r['mname'], r['mtype'], r['mtdesc'], r['unit'],
                '%g' % r['actual'], r['flag'], '%.6g' % r['containers'],
                r['reason'], r['note']]

    def _drink_detail_cell(self, i, j, v, r):
        if j in (6, 12, 14):   # 产量 / 实际 / 计入容器数
            v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if j == 13:   # 是否计入容器数：计入的加粗
            f = v.font()
            f.setBold(r['flag'] == '是')
            v.setFont(f)

    # ---- 总表（食+饮合并·结论）----
    def _fill_all_orders(self, rows):
        self._fill_table(self.all_table, rows, self._all_vals, self._all_cell)

    def _all_vals(self, r):
        rate_txt = ('%.1f%%' % (r['rate'] * 100)) if r.get('rate') is not None else '—'
        return [r['date'], r['ord'], r['fac'], r['ws'], r.get('pno', ''), r['pdesc'],
                '%g' % r.get('yield', 0), r.get('口径', ''), r['verdict'], rate_txt]

    def _all_cell(self, i, j, v, r):
        if j in (6, 9):   # 产量 / 偏差率 数值列右对齐
            v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if j == 8:   # 结论列：疑似漏记加粗
            f = v.font()
            f.setBold(r['verdict'] == '疑似漏记')
            v.setFont(f)

    # -- 通用填表器：把 vals 填进表、给每格上色/套 cell 钩子 ------------------
    @staticmethod
    def _fill_table(table, rows, vals_fn, cell_fn):
        """一单一行/一行一组件通用填表：底色按所属单结论（红=疑似漏记、绿=守恒/正常、
        待人工确认不上色），逐格套 cell_fn 做对齐/加粗/悬停。"""
        table.setRowCount(0)
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            verdict = r['verdict']
            bg = _RED if verdict == '疑似漏记' else (_GREEN if verdict == '守恒/正常' else None)
            for j, v in enumerate(vals_fn(r)):
                it = QTableWidgetItem(str(v))
                if bg is not None:
                    it.setBackground(bg)
                cell_fn(i, j, it, r)
                table.setItem(i, j, it)
        table.setSortingEnabled(True)

    # ------------------------------------------------------------------ 导出
    def _on_export(self):
        """导出当前页视图为 xlsx：食品/饮料各自页导各自的行，列头与该页一致。"""
        idx = self.tabs.currentIndex()
        table, rows, _total = self._active_tables(idx)
        if not rows:
            QMessageBox.information(self, "提示", "当前视图无数据")
            return
        rec, cols = self._record_for_tab(idx)
        try:
            import pandas as pd
            from PySide6.QtWidgets import QFileDialog
            tab = self.tabs.tabText(idx)
            default = os.path.join(
                os.path.expanduser("~"), "Desktop",
                "翻箱守恒预警_看板导出_%s.xlsx" % tab.replace("·", ""))
            path, _ = QFileDialog.getSaveFileName(
                self, "导出当前视图", default, "Excel (*.xlsx)")
            if not path:
                return
            out = [rec(r) for r in rows]
            pd.DataFrame(out, columns=cols).to_excel(path, index=False)
            QMessageBox.information(self, "已导出", "已导出 %d 行到:\n%s" % (len(out), path))
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "导出失败", str(e))

    @staticmethod
    def _record_for_tab(idx):
        """页签 → (record 构造器, 列头)：导出键必须与该页表头一一对应，否则整列空白。"""
        if idx == 0:
            return FlipCheckDashboardDialog._all_record, _ALL_HEADERS
        if idx == 1:
            return FlipCheckDashboardDialog._food_order_record, _HEADERS
        if idx == 2:
            return FlipCheckDashboardDialog._food_detail_record, _DETAIL_HEADERS
        if idx == 3:
            return FlipCheckDashboardDialog._drink_order_record, _DRINK_HEADERS
        return FlipCheckDashboardDialog._drink_detail_record, _DRINK_DETAIL_HEADERS

    @staticmethod
    def _food_order_record(r):
        return {
            '订单日期': r['date'], '流程订单': r['ord'], '工厂': r['fac'],
            '车间': r['ws'], '产品物料描述': r['pdesc'], '产量(件)': r['yield'],
            '单件净含量(KG)': r['net_each'], '产出总净含量(KG)': r['out_kg'],
            '投入成品件折KG': r['in_fin'], '投入散货食物KG': r['in_loose'],
            '投入食物合计KG': r['in_food'], '差额KG(产出-投入)': r['diff'],
            '偏差率': r['rate'], '结论': r['verdict'], '备注': r['note'],
            '产品物料编码': r['pno'], '组件物料编码': r['mcodes'],
            '组件物料名称': r['mnames'],
        }

    @staticmethod
    def _food_detail_record(r):
        return {
            '订单日期': r['date'], '流程订单': r['ord'], '工厂': r['fac'],
            '车间': r['ws'], '产品物料编码': r['pno'], '产品物料描述': r['pdesc'],
            '组件物料编码': r['mcode'], '组件物料名称': r['mname'],
            '组件物料类型': r['mtype'], '组件物料类型描述': r['mtdesc'],
            '单位': r['unit'], '实际': r['actual'],
            '是否计入食物投入': r['flag'], '计入KG(参考)': round(r['kg'], 6),
            '备注': r['note'], '结论': r['verdict'],
            '产量(件)': r.get('yield', 0), '单件净含量(KG)': r.get('net_each'),
            '产出总净含量(KG)': r.get('out_kg'), '投入食物合计KG': r.get('in_food'),
            '差额KG(产出-投入)': r.get('diff'), '偏差率': r.get('rate'),
        }

    @staticmethod
    def _drink_order_record(r):
        return {
            '订单日期': r['date'], '流程订单': r['ord'], '工厂': r['fac'],
            '车间': r['ws'], '产品物料编码': r['pno'], '产品物料描述': r['pdesc'],
            '产量(件)': r['yield'],
            '容器形式': r.get('container'), '净含量单位': r.get('unit'),
            '单件容器数': r.get('n'), '单容器净含量': r.get('per'),
            '产出总容器数': r.get('out_containers'), '投入总容器数': r.get('in_containers'),
            '差额容器数': r.get('diff'), '偏差率': r.get('rate'),
            '结论': r['verdict'], '备注': r['note'],
        }

    @staticmethod
    def _drink_detail_record(r):
        return {
            '订单日期': r['date'], '流程订单': r['ord'], '工厂': r['fac'],
            '车间': r['ws'], '产品物料编码': r['pno'], '产品物料描述': r['pdesc'],
            '组件物料编码': r['mcode'], '组件物料名称': r['mname'],
            '组件物料类型': r['mtype'], '组件物料类型描述': r['mtdesc'],
            '单位': r['unit'], '实际': r['actual'],
            '是否计入容器数': r['flag'], '计入容器数(参考)': round(r['containers'], 6),
            '排除原因': r.get('reason', ''), '备注': r['note'],
            '产量(件)': r.get('yield', 0),
        }

    @staticmethod
    def _all_record(r):
        return {
            '订单日期': r['date'], '流程订单': r['ord'], '工厂': r['fac'],
            '车间': r['ws'], '产品物料编码': r.get('pno', ''),
            '产品物料描述': r['pdesc'], '产量(件)': r.get('yield', 0),
            '口径': r.get('口径', ''), '结论': r['verdict'],
            '偏差率': ('%.1f%%' % (r['rate'] * 100))
                     if r.get('rate') is not None else '—',
        }
