# -*- coding: utf-8 -*-
"""阈值与提醒 —— 规则中心第三页（设计稿 v43.333 rules.html 第三 Tab，第四期E）。

改造前的现状不是「第四个独立窗口」那么轻：压根没有窗口。这五个数散落在代码里：
偏差率预警阈值写死在 5 处（主表橙色高亮、颜色筛选、偏差率预警看板、KPI 偏差预警、
未读汇总），真异常阈值写死在 2 处（KPI 与状态条），AI 通过率下限只在设计稿里存在过，
两个排除开关（SAP 除零钳位、未投料）是每处各自抄的一段注释。想改一个数得改七行代码，
而 ``core/config_loader.py`` 里那个 ``alert.threshold_percent`` 没有任何调用者 ——
配置文件里写着、代码里没人读，比没写更容易骗人。

现在：判据收在 ``core.threshold_config``，本页是它唯一的编辑入口。

四条硬约束：
1. **默认值 = 改造前的字面量**（10 / 30 / 80 / 两个开关都开），不改就不变行为；
   金矿快照用例把改造前五处共同的表达式逐字钉住（test_threshold_config_phase4e.py）。
2. **预览就是生产判据**：本页数字来自 ``thr.dev_alert_mask``，与主表橙色、颜色筛选、
   看板、KPI 调的是同一个函数，不存在「预览一套、真跑另一套」。
3. **保存当场生效**：写完配置立刻推到 AlertMonitor / 代理模型 / 主表 / KPI / 未读汇总，
   不要求重启；``AuditProxyModel.set_alert_threshold`` 这个从前零调用者的 setter
   终于有了调用者。
4. **红线不越**：本页只管「亮不亮橙色」，不管「谁被自动已读」。实际=0（未投料）的行
   无论这里怎么选，都留在隔离区等人工审计 —— 界面上必须把这句说出来。
"""
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import threshold_config as thr
from gui_pyside6.components import message_box
from gui_pyside6.dialogs.rule_editor_kit import (
    BODY_MIN_H,
    CARD_GAP,
    card,
    fcheck,
    fhint,
    flabel,
    fspin,
    style_tab,
)

_EXTRA_QSS = """
QLabel#pvRed { color: $warn; }
QLabel#thrNote { color: $textMuted; font-size: 11px; }
"""


def _hrow(spacing=6):
    lay = QHBoxLayout()
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    return lay


class ThresholdConfigWidget(QWidget):
    """阈值与提醒编辑页；``saved`` 与另两页同义（True=已落盘）。"""

    saved = Signal(bool)

    def __init__(self, parent=None, df=None):
        super().__init__(parent)
        self.df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        self.cfg = thr.load_threshold_config()
        self._build_ui()
        style_tab(self, _EXTRA_QSS)
        self._fill_from_cfg(self.cfg)
        self._refresh_preview()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(10)

        note = QLabel(
            "这里定的数，主表橙色高亮 / 颜色筛选 / 偏差率预警看板 / KPI 偏差预警 / "
            "未读汇总读的是<b>同一个值</b>。改一次，五处一起变。")
        note.setObjectName("thrNote")
        note.setWordWrap(True)
        v.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(CARD_GAP)

        g1, b1 = card("gauge", "偏差率口径", logic="全局生效")
        row = _hrow()
        row.addWidget(flabel("预警阈值"))
        self.spin_alert = fspin(0.0, 100.0, 10.0, width=96)
        row.addWidget(self.spin_alert)
        row.addWidget(fhint("% ｜偏差率| ≥ 此值即计预警（含等号，与改造前一致）"))
        row.addStretch(1)
        b1.addLayout(row)
        row = _hrow()
        row.addWidget(flabel("真异常阈值"))
        self.spin_anomaly = fspin(0.0, 100.0, 30.0, width=96)
        row.addWidget(self.spin_anomaly)
        row.addWidget(fhint("% ｜偏差率| > 此值且非替代料计真异常（不含等号）"))
        row.addStretch(1)
        b1.addLayout(row)
        iv.addWidget(g1)

        g2, b2 = card("shield", "不计入预警", tone="warn", logic="开关")
        self.chk_sap = fcheck("排除 SAP 除零假值")
        b2.addWidget(self.chk_sap)
        h = fhint("|偏差率| 恰为 +100.0%（定额=0 的钳位值）。计入等于把除零假象当真偏差。")
        h.setWordWrap(True)
        b2.addWidget(h)
        self.chk_unfed = fcheck("排除未投料行")
        b2.addWidget(self.chk_unfed)
        h = fhint("实际=0 且 定额>0（恒 -100.0%）。关掉这里它们会亮橙色，"
                  "但仍留在隔离区等人工审计 —— 本页只决定亮不亮，不决定谁被自动已读。")
        h.setWordWrap(True)
        b2.addWidget(h)
        iv.addWidget(g2)

        g3, b3 = card("bell", "AI 通过率提醒", logic="下限")
        row = _hrow()
        row.addWidget(flabel("通过率下限"))
        self.spin_pass = fspin(0.0, 100.0, 80.0, width=96)
        row.addWidget(self.spin_pass)
        row.addWidget(fhint("% 低于下限时 KPI 通过率那格会在数字后标注「低于 xx%」"))
        row.addStretch(1)
        b3.addLayout(row)
        iv.addWidget(g3)

        iv.addStretch(1)
        scroll.setWidget(inner)
        scroll.setMinimumHeight(BODY_MIN_H)
        v.addWidget(scroll, 1)
        v.addWidget(self._build_preview())

    def _build_preview(self):
        bar = QFrame()
        bar.setObjectName("rulePreview")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(14)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(3)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.pv_pre = QLabel("按当前取值实测：")
        self.pv_pre.setObjectName("pvMain")
        self.pv_num = QLabel("—")
        self.pv_num.setObjectName("pvMainNum")
        self.pv_post = QLabel("条预警")
        self.pv_post.setObjectName("pvMain")
        for w in (self.pv_pre, self.pv_num, self.pv_post):
            row.addWidget(w)
        row.addStretch(1)
        lv.addLayout(row)

        self.pv_red = QLabel()
        self.pv_red.setObjectName("pvRed")
        self.pv_red.setWordWrap(True)
        self.pv_red.setVisible(False)
        lv.addWidget(self.pv_red)

        self.pv_sample = QLabel("主表无数据时不计算")
        self.pv_sample.setObjectName("pvSample")
        self.pv_sample.setWordWrap(True)
        lv.addWidget(self.pv_sample)
        hl.addWidget(left, 1)

        self.btn_save = QPushButton("保存阈值")
        self.btn_save.clicked.connect(self._on_save_clicked)
        hl.addWidget(self.btn_save, 0, Qt.AlignTop)
        return bar

    # ------------------------------------------------------------------ 取值
    def _fill_from_cfg(self, cfg):
        """回填控件：挡掉 valueChanged，免得把「打开页面」报成「用户改过」。"""
        for w in (self.spin_alert, self.spin_anomaly, self.spin_pass,
                  self.chk_sap, self.chk_unfed):
            w.blockSignals(True)
        self.spin_alert.setValue(cfg["alert_dev_rate_pct"])
        self.spin_anomaly.setValue(cfg["anomaly_dev_rate_pct"])
        self.spin_pass.setValue(cfg["ai_pass_rate_min_pct"])
        self.chk_sap.setChecked(cfg["exclude_sap_zero_div"])
        self.chk_unfed.setChecked(cfg["exclude_unfed"])
        for w in (self.spin_alert, self.spin_anomaly, self.spin_pass,
                  self.chk_sap, self.chk_unfed):
            w.blockSignals(False)

    def _draft(self):
        return {
            "alert_dev_rate_pct": float(self.spin_alert.value()),
            "anomaly_dev_rate_pct": float(self.spin_anomaly.value()),
            "ai_pass_rate_min_pct": float(self.spin_pass.value()),
            "exclude_sap_zero_div": self.chk_sap.isChecked(),
            "exclude_unfed": self.chk_unfed.isChecked(),
        }

    def wire_changed_signals(self):
        for spin in (self.spin_alert, self.spin_anomaly, self.spin_pass):
            spin.valueChanged.connect(self._on_editor_changed)
        for chk in (self.chk_sap, self.chk_unfed):
            chk.toggled.connect(self._on_editor_changed)
        return self

    def _on_editor_changed(self, *_a):
        self._refresh_preview()

    def set_df(self, df):
        self.df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        self._refresh_preview()

    # ------------------------------------------------------------------ 预览
    def _refresh_preview(self):
        """预览用**草稿值**算，并说清它还没保存。

        主行（pv_post）不换行、参与最小宽度计算，所以只放短数字；长说明一律进会
        换行的 pv_red —— 这是第四期D 量出来的教训（1078 > 960）。
        """
        draft = self._draft()
        red = []
        if draft != thr.get_thresholds():
            red.append("以上是未保存的草稿；当前生效值仍是已保存的那一套")

        mask = thr.dev_alert_mask(self.df, draft)
        if mask is None:
            self.pv_num.setText("—")
            self.pv_post.setText("条")
            if self.df is None or self.df.empty:
                self.pv_sample.setText("主表无数据：不计算命中")
            else:
                self.pv_sample.setText("主表没有偏差率列：无从判断命中几条，"
                                       "不表示「一条都没有」")
            self.pv_red.setText("　".join(red))
            self.pv_red.setVisible(bool(red))
            return

        hits = int(mask.sum())
        total = len(self.df)
        amask = thr.anomaly_mask(self.df, draft)
        anomaly = 0 if amask is None else int(amask.sum())
        self.pv_num.setText(str(hits))
        self.pv_post.setText("条预警 · 占全表 %.1f%% · 真异常 %d 条"
                             % (100.0 * hits / total if total else 0.0, anomaly))

        unfed = thr.unfed_mask(self.df)
        if not draft["exclude_unfed"] and unfed is not None and int(unfed.sum()):
            red.append("排除未投料已关：%d 行实际=0 会一起亮橙色；它们仍留在隔离区"
                       "等人工审计，本页不改变谁被自动已读" % int(unfed.sum()))
        if not draft["exclude_sap_zero_div"]:
            red.append("排除 SAP 除零假值已关：定额=0 的 +100.0% 也会被计进预警")

        rate = thr.ai_pass_rate(self.df)
        if rate is None:
            self.pv_sample.setText("AI 通过率：主表没有审核结果列，说不准")
        elif rate < draft["ai_pass_rate_min_pct"]:
            self.pv_sample.setText("AI 通过率 %.0f%%，低于下限 %.0f%%"
                                   % (rate, draft["ai_pass_rate_min_pct"]))
        else:
            self.pv_sample.setText("AI 通过率 %.0f%%（下限 %.0f%%）"
                                   % (rate, draft["ai_pass_rate_min_pct"]))

        ids = [str(x) for x in self.df.loc[mask, "data_id"].head(5)] \
            if "data_id" in self.df.columns else []
        if ids:
            self.pv_sample.setText(self.pv_sample.text() + "　样例：" + "、".join(ids))
        self.pv_red.setText("　".join(red))
        self.pv_red.setVisible(bool(red))
        self.pv_post.setToolTip(
            "预警条数用的就是主表橙色、颜色筛选、预警看板、KPI 那一条判据："
            "core.threshold_config.dev_alert_mask")

    # ------------------------------------------------------------------ 保存
    def save(self):
        try:
            self.cfg = thr.save_threshold_config(self._draft())
        except Exception as e:
            message_box.error(self, "保存失败", "写入阈值配置失败。", exc=e)
            return False
        self._refresh_preview()
        return True

    def _on_save_clicked(self):
        ok = self.save()
        if ok:
            self.saved.emit(True)
