# -*- coding: utf-8 -*-
"""跨月偏差趋势看板 —— 选物料看它逐月偏差走势（峰值/期末双口径）。

裴哥 2026-11-14 · 跨月趋势对比功能

数据源：monthly_archive.db（由 core/monthly_archive_builder.backfill 从源 Excel 回填）。
看板只读表 + 画图，不碰分析逻辑、不改状态。

交互：
  - 左侧物料列表（按历史峰值降序，反复出问题的排最前）+ 搜索框（名称/编码模糊）；
  - 顶部工厂切换（归档表里出现过的工厂）+ 峰值/期末线开关 + 回填归档按钮；
  - 右侧 QWebEngineView 渲染趋势图（后台 QThread 用 Agg 画，避免卡 GUI）。

WebEngine 延迟 import + try/except 降级 QTextBrowser（同 dashboard_dialog，
避免模块级初始化 Chromium 导致启动 hang）。
"""
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QUrl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QCheckBox, QComboBox,
    QSplitter, QProgressDialog, QTextBrowser,
)
from PySide6.QtCore import Qt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import monthly_archive_store as store  # noqa: E402
from analysis.trend_html import build_trend_html  # noqa: E402
from gui_pyside6.components import dialog_chrome  # noqa: E402


class _TrendRenderWorker(QThread):
    """后台线程：取某物料跨月趋势 + 画图出 HTML（Agg 后端，不占 GUI 线程）。"""

    html_ready = Signal(str)
    build_failed = Signal(str)

    def __init__(self, factory, material_code, material_name, dark, show_period, parent=None):
        super().__init__(parent)
        self.factory = factory
        self.material_code = material_code
        self.material_name = material_name
        self.dark = dark
        self.show_period = show_period

    def run(self):
        try:
            rows = store.load_archive(factory=self.factory,
                                      material_keyword=self.material_code)
            # load_archive 已按工厂+编码过滤，再精确锁编码（防同名编码模糊误中）
            rows = [r for r in rows if r["material_code"] == self.material_code]
            trend = [{"biz_month": r["biz_month"], "period_dev": r["period_dev"],
                      "peak_dev": r["peak_dev"], "corrected": r["corrected"]}
                     for r in rows]
            trend.sort(key=lambda r: r["biz_month"])
            meta = {"material_code": self.material_code,
                    "material_name": self.material_name,
                    "factory": self.factory}
            self.html_ready.emit(build_trend_html(trend, meta, dark=self.dark,
                                                  show_period=self.show_period))
        except Exception as e:  # noqa: BLE001
            self.build_failed.emit(f"生成趋势图失败：{e}")


class _BackfillWorker(QThread):
    """后台线程：扫源 Excel 全量回填归档表（200+ 文件约 1~2 分钟）。"""

    progress = Signal(int, int, str)   # done, total, 当前文件名
    done = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            from config.paths import get_data_dir
            from core.monthly_archive_builder import backfill
            stat = backfill(get_data_dir(),
                            progress=lambda i, t, n: self.progress.emit(i, t, n))
            self.done.emit(stat)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"回填归档失败：{e}")


class TrendDialog(QDialog):
    """跨月偏差趋势看板。"""

    def __init__(self, owner=None, dark=None):
        self._web_ok = False
        self._web_err = ""
        self._WebEngineView = None
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            self._WebEngineView = QWebEngineView
            self._web_ok = True
        except Exception as e:  # noqa: BLE001
            self._web_err = str(e)

        super().__init__(owner)
        self.owner = owner
        # 主题：能读到全局就跟随，读不到按亮色兜底
        self.dark = bool(dark) if dark is not None else self._guess_dark()
        self._worker = None
        self._backfill_worker = None
        self._tmp_html = None
        self._alive = True
        self._materials = []
        self._build_ui()
        self._reload_factories()
        self._reload_materials()

    @staticmethod
    def _guess_dark():
        try:
            from utils.theme_manager import Thm
            return bool(Thm.is_dark)
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        dialog_chrome.apply(self, dialog_chrome.TIER_BOARD,
                            "跨月偏差趋势", "峰值 / 期末双口径")
        root = QVBoxLayout(self)

        # 顶部工具条：工厂 + 线开关 + 回填 + 导出
        top = QHBoxLayout()
        top.addWidget(QLabel("工厂"))
        self.fac_combo = QComboBox()
        self.fac_combo.setMinimumWidth(90)
        self.fac_combo.currentTextChanged.connect(self._on_factory_changed)
        top.addWidget(self.fac_combo)

        self.period_chk = QCheckBox("显示期末线")
        self.period_chk.setChecked(True)
        self.period_chk.toggled.connect(self._on_option_changed)
        top.addWidget(self.period_chk)

        top.addStretch()
        self.backfill_btn = QPushButton("回填归档")
        self.backfill_btn.setToolTip("扫源 Excel 全量重建跨月归档表（首次约 1~2 分钟）")
        self.backfill_btn.clicked.connect(self._on_backfill)
        top.addWidget(self.backfill_btn)
        self.export_btn = QPushButton("导出 HTML")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        top.addWidget(self.export_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        top.addWidget(close_btn)
        root.addLayout(top)

        # 左物料列表 + 右图
        splitter = QSplitter(Qt.Horizontal)
        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜物料名 / 编码（如 黄原胶、10001119）")
        self.search.textChanged.connect(self._reload_materials)
        left.addWidget(self.search)
        self.mat_list = QListWidget()
        self.mat_list.currentItemChanged.connect(self._on_material_selected)
        left.addWidget(self.mat_list, 1)
        from PySide6.QtWidgets import QWidget
        left_panel = QWidget()
        left_panel.setLayout(left)
        left_panel.setMinimumWidth(260)
        splitter.addWidget(left_panel)

        self.web = self._WebEngineView(self) if self._web_ok else QTextBrowser(self)
        if self._web_ok:
            try:
                from PySide6.QtWebEngineCore import QWebEngineSettings
                self.web.settings().setAttribute(
                    QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            except Exception:  # noqa: BLE001
                pass
        else:
            self.web.setHtml(
                f"<p style='color:#b00'>WebEngine 不可用，已降级文本视图：<br>"
                f"<small>{self._web_err}</small></p>")
        splitter.addWidget(self.web)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.web.setHtml(
            "<div style='padding:40px;text-align:center;color:#656d76;"
            "font-size:15px'>选择左侧物料查看跨月趋势…</div>")

    # ------------------------------------------------------------------ 数据
    def _reload_factories(self):
        self.fac_combo.blockSignals(True)
        self.fac_combo.clear()
        facs = store.list_factories()
        self.fac_combo.addItem("")  # 全部（跨厂汇总）
        for f in facs:
            self.fac_combo.addItem(f)
        self.fac_combo.blockSignals(False)

    def _reload_materials(self):
        fac = self.fac_combo.currentText() if hasattr(self, "fac_combo") else ""
        kw = self.search.text().strip() if hasattr(self, "search") else ""
        self._materials = store.list_materials(fac)
        if kw:
            k = kw.lower()
            self._materials = [m for m in self._materials
                               if k in str(m["material_name"]).lower()
                               or k in str(m["material_code"]).lower()]
        self.mat_list.blockSignals(True)
        self.mat_list.clear()
        for m in self._materials:
            name = m["material_name"] or "(无名)"
            label = f"{name}  [{m['material_code']}] · 峰值{m['max_peak']:g} · {m['months']}月"
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, m)
            self.mat_list.addItem(it)
        self.mat_list.blockSignals(False)
        # 无选中时自动选第一个（峰值最高的），让看板一打开就有图
        if self.mat_list.count() > 0 and self.mat_list.currentRow() < 0:
            self.mat_list.setCurrentRow(0)

    def _current_material(self):
        it = self.mat_list.currentItem()
        return it.data(Qt.UserRole) if it else None

    # ------------------------------------------------------------------ 交互
    def _on_factory_changed(self, _):
        self._reload_materials()

    def _on_material_selected(self, _cur, _prev):
        self._render_current()

    def _on_option_changed(self):
        self._render_current()

    def _render_current(self):
        m = self._current_material()
        if not m:
            return
        fac = self.fac_combo.currentText()
        self._start_worker(fac, m["material_code"], m["material_name"])

    def _start_worker(self, fac, code, name):
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(1500)
        self._worker = _TrendRenderWorker(fac, code, name, self.dark,
                                          self.period_chk.isChecked(), parent=self)
        self._worker.html_ready.connect(self._on_html_ready)
        self._worker.build_failed.connect(lambda msg: QMessageBox.information(self, "提示", msg))
        self._worker.start()

    def _on_html_ready(self, html):
        if not self._alive:
            return
        self._last_html = html
        self.export_btn.setEnabled(True)
        if self._web_ok:
            tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                              encoding="utf-8",
                                              dir=tempfile.gettempdir())
            tmp.write(html)
            tmp.close()
            self._tmp_html = tmp.name
            self.web.load(QUrl.fromLocalFile(self._tmp_html))
        else:
            self._tmp_html = None
            self.web.setHtml(html)

    # ------------------------------------------------------------------ 回填
    def _on_backfill(self):
        if self._backfill_worker is not None and self._backfill_worker.isRunning():
            QMessageBox.information(self, "提示", "回填正在进行中，请稍候。")
            return
        self._prog = QProgressDialog("正在回填跨月归档…", "取消", 0, 100, self)
        self._prog.setWindowModality(Qt.WindowModal)
        self._prog.setMinimumDuration(0)
        self._prog.setValue(0)
        self._backfill_worker = _BackfillWorker(parent=self)
        self._backfill_worker.progress.connect(self._on_backfill_progress)
        self._backfill_worker.done.connect(self._on_backfill_done)
        self._backfill_worker.failed.connect(self._on_backfill_failed)
        self._backfill_worker.start()

    def _on_backfill_progress(self, i, t, name):
        if not getattr(self, "_prog", None):
            return
        self._prog.setMaximum(t)
        self._prog.setValue(i)
        self._prog.setLabelText(f"正在回填跨月归档…\n[{i}/{t}] {name}")

    def _on_backfill_done(self, stat):
        if getattr(self, "_prog", None):
            self._prog.close()
        QMessageBox.information(
            self, "回填完成",
            f"扫描 {stat['scanned']} 个文件，解析 {stat['parsed']}，"
            f"跳过 {stat['skipped_files']}，写入 {stat['rows']} 行归档。\n"
            f"耗时 {stat['seconds']} 秒。")
        self._reload_factories()
        self._reload_materials()

    def _on_backfill_failed(self, msg):
        if getattr(self, "_prog", None):
            self._prog.close()
        QMessageBox.critical(self, "回填失败", msg)

    # ------------------------------------------------------------------ 导出
    def _on_export(self):
        if not getattr(self, "_last_html", None):
            QMessageBox.information(self, "提示", "趋势图还在生成中，请稍候。")
            return
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "导出趋势 HTML",
                                              "ZPP011跨月趋势.html", "HTML (*.html)")
        if not path:
            return
        from gui_pyside6.save_guard import safe_save, friendly_error

        def _write(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(self._last_html)

        try:
            saved = safe_save(self, path, _write, what="趋势图")
            if saved:
                QMessageBox.information(self, "已导出", f"趋势图已保存到：\n{saved}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", friendly_error(path, e))

    # ------------------------------------------------------------------ 生命周期
    def closeEvent(self, event):
        self._alive = False
        for w in (self._worker, getattr(self, "_backfill_worker", None)):
            if w is not None and w.isRunning():
                w.quit()
                w.wait(3000)
        if self._tmp_html and os.path.exists(self._tmp_html):
            try:
                os.remove(self._tmp_html)
            except OSError:
                pass
        super().closeEvent(event)