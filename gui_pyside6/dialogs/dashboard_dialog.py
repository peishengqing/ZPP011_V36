# -*- coding: utf-8 -*-
"""管理看板对话框 - 偏差视角 12 图 HTML 看板（QWebEngineView 渲染）

替代旧版只用 matplotlib 画的车间排名/物料大类/月度趋势三张糙图，
改为复用 analysis.dashboard_html.build_html 生成自包含 HTML，
用 QWebEngineView 加载 —— 与「tools/gen_dashboard.py 生成的桌面 HTML 版」完全一致：
顶部「全部 / 食品厂 / 饮料厂」切换按钮、按工厂独立出 指标卡 + 12 图 + 小结。

数据来源：main_window 传来的 view_model.df（已按分析日期窗口过滤、含 工厂 列的混合 df），
本对话框只做「取数拆分 + 渲染」，不碰任何分析逻辑。

性能：build_html（为每个工厂画 12 张 matplotlib 图）是同步重活，
原先在 GUI 主线程跑会阻塞界面、导致「未响应」。现改为在后台 QThread 中
用 Agg 后端绘制（仅出图、不需要 Qt 集成），画完通过信号把 HTML 交回主线程显示。
"""
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QTextBrowser,
)
from PySide6.QtCore import QUrl, QThread, Signal

# 让项目 analysis 模块可 import
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.dashboard_html import compute_metrics  # noqa: E402

# 说明：本模块故意不在文件顶部 import PySide6.QtWebEngine*，
# 因为 main_window.py 在模块级（顶部）就 `from .dialogs.dashboard_dialog import DashboardDialog`，
# 会导致软件一启动就强制初始化 Chromium 内核（WebEngine）而长时间 hang。
# WebEngine 改为在 DashboardDialog.__init__ 内部延迟 import + try/except 降级。
# matplotlib 后端不在主线程设置：绘制改到后台线程用 Agg（见 _DashboardBuildWorker），
# 主线程只负责把生成的 HTML 交给 WebEngine 显示，不再直接画图。



def _split_by_factory(audit_df):
    """把混合 df 按 工厂 列拆成 blocks（工厂名 -> (metrics, sub_df)）。
    无 工厂 列时整体作为单一区块。"""
    blocks = {}
    if audit_df is None or audit_df.empty:
        return blocks
    if "工厂" in audit_df.columns:
        for fac in audit_df["工厂"].dropna().unique():
            sub = audit_df[audit_df["工厂"] == fac]
            if not sub.empty:
                blocks[str(fac)] = (compute_metrics(sub), sub)
    else:
        blocks["全部"] = (compute_metrics(audit_df), audit_df)
    return blocks


def _window_from_df(audit_df):
    """从 df 的 订单日期 推断分析窗口，用于看板副标题。"""
    if audit_df is None or "订单日期" not in audit_df.columns:
        return "全量", "全量"
    dates = pd.to_datetime(audit_df["订单日期"], errors="coerce").dropna()
    if dates.empty:
        return "全量", "全量"
    return dates.min().strftime("%Y-%m-%d"), dates.max().strftime("%Y-%m-%d")


class _DashboardBuildWorker(QThread):
    """后台线程：拆分数据 + 生成看板 HTML（Agg 后端，避免占用 GUI 线程）。"""

    html_ready = Signal(str)
    build_failed = Signal(str)

    def __init__(self, audit_df, parent=None):
        super().__init__(parent)
        self.audit_df = audit_df

    def run(self):
        try:
            import importlib
            import matplotlib
            # 后台线程用纯 Agg 后端出图（fig.savefig 写内存缓冲），
            # 不依赖 Qt，避免在非 GUI 线程创建 QPixmap/QImage 导致崩溃。
            matplotlib.use("Agg", force=True)
            import analysis.dashboard_html as dh
            importlib.reload(dh)  # 让模块内的 plt 重新绑定到 Agg
            blocks = _split_by_factory(self.audit_df)
            if not blocks:
                self.build_failed.emit("当前没有可展示的偏差数据。")
                return
            start, end = _window_from_df(self.audit_df)
            meta = {
                "start": start,
                "end": end,
                "src": "管理看板（实时数据）",
                "gen": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            }
            html = dh.build_html(blocks, meta)
            self.html_ready.emit(html)
        except Exception as e:  # noqa: BLE001
            self.build_failed.emit(f"生成看板失败：{e}")


class DashboardDialog(QDialog):
    """管理看板：偏差视角 12 图（分厂切换）。"""

    def __init__(self, audit_df, material_df=None, parent=None, main_window=None):
        # WebEngine：首次 import 会初始化 Chromium 内核（较重），失败时降级 QTextBrowser
        self._web_engine_ok = False
        self._web_engine_err = ""
        self._WebEngineView = None
        self._WebEngineSettings = None
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            from PySide6.QtWebEngineCore import QWebEngineSettings  # noqa: F401
            self._WebEngineView = QWebEngineView
            self._WebEngineSettings = QWebEngineSettings
            self._web_engine_ok = True
        except Exception as e:  # noqa: BLE001
            self._web_engine_err = str(e)

        super().__init__(parent)
        self.main_window = main_window
        self.audit_df = audit_df
        self.material_df = material_df
        self._tmp_html = None
        self._last_html = None
        self._worker = None
        self._alive = True
        self._init_ui()
        self._start_build()

    def _init_ui(self):
        self.setWindowTitle("管理看板 · 偏差视角 12 图")
        self.resize(1100, 760)
        layout = QVBoxLayout(self)

        # 顶部工具栏
        top = QHBoxLayout()
        hint = QLabel("偏差分析看板（顶部按钮可切换 食品厂 / 饮料厂）")
        hint.setStyleSheet("color:#656d76;font-size:13px")
        top.addWidget(hint)
        top.addStretch()
        self.export_btn = QPushButton("导出 HTML")
        self.export_btn.clicked.connect(self._export_html)
        self.export_btn.setEnabled(False)  # 看板生成完成后才允许导出
        top.addWidget(self.export_btn)
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        top.addWidget(self.close_btn)
        layout.addLayout(top)

        # WebEngine 视图（若可用），否则降级到 QTextBrowser
        if self._web_engine_ok:
            self.web = self._WebEngineView(self)
            self.web.settings().setAttribute(
                self._WebEngineSettings.LocalContentCanAccessFileUrls, True
            )
        else:
            self.web = QTextBrowser(self)
            self.web.setAcceptRichText(True)
            self.web.setOpenExternalLinks(False)
            if self._web_engine_err:
                self.web.setHtml(
                    f"<p style='color:#b00'>WebEngine 不可用，已降级为文本视图：<br>"
                    f"<small>{self._web_engine_err}</small></p>"
                )
        layout.addWidget(self.web, 1)
        # 先显示加载占位，避免空白窗
        self.web.setHtml(
            "<div style='padding:40px;text-align:center;color:#656d76;"
            "font-size:15px'>正在生成看板，请稍候…</div>"
        )

    def _start_build(self):
        """启动后台线程生成看板 HTML，避免阻塞 GUI 主线程。"""
        self._worker = _DashboardBuildWorker(self.audit_df)
        self._worker.html_ready.connect(self._on_html_ready)
        self._worker.build_failed.connect(self._on_build_failed)
        self._worker.start()

    def _on_html_ready(self, html):
        if not self._alive:
            return
        self._last_html = html
        self.export_btn.setEnabled(True)
        # WebEngine 模式：写临时文件用本地 file:// 加载（data: URI 过长易出问题）
        if self._web_engine_ok:
            tmp = tempfile.NamedTemporaryFile(
                "w", suffix=".html", delete=False, encoding="utf-8", dir=tempfile.gettempdir()
            )
            tmp.write(html)
            tmp.close()
            self._tmp_html = tmp.name
            self.web.load(QUrl.fromLocalFile(self._tmp_html))
        else:
            # 降级模式：QTextBrowser 直接渲染静态 HTML（JS 切换按钮不生效，但全部厂区默认可见）
            self._tmp_html = None
            self.web.setHtml(html)

    def _on_build_failed(self, msg):
        if not self._alive:
            return
        QMessageBox.information(self, "提示", msg)

    def _export_html(self):
        if not getattr(self, "_last_html", None):
            QMessageBox.information(self, "提示", "看板还在生成中，请稍候再导出。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出看板 HTML", "ZPP011偏差看板.html", "HTML (*.html)"
        )
        if path:
            from gui_pyside6.save_guard import safe_save, friendly_error

            def _write(p):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(self._last_html)

            try:
                saved = safe_save(self, path, _write, what="看板")
                if saved:
                    QMessageBox.information(self, "已导出", f"看板已保存到：\n{saved}")
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, "导出失败", friendly_error(path, e))

    def closeEvent(self, event):
        self._alive = False
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()       # 非事件循环线程下为 no-op，但保留以策万全
            self._worker.wait(3000)   # 等待后台绘制结束，避免 use-after-free
        if self._tmp_html and os.path.exists(self._tmp_html):
            try:
                os.remove(self._tmp_html)
            except OSError:
                pass
        super().closeEvent(event)
