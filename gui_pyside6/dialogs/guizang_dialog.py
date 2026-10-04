# -*- coding: utf-8 -*-
"""归藏（Guizang）网页版报告对话框 —— 全屏横滑 PPT，QWebEngineView 渲染（动态注入版）

两个风格入口，同一套数据管线（ZPP011 生产偏差分析 · 食品厂/饮料厂分厂报告）：
  · 归藏-Magazine  电子杂志风：衬线标题 + 墨水经典配色 + 流体 WebGL 背景
  · 归藏-Swiss     瑞士国际主义风：无衬线极轻字重 + 安全橙强调色 + 网格背景

数据管线（v43.158 动态注入）：
  分析结果 Excel → core.guizang_report.build_report_data（pandas 实时计算）
  → render_html（注入 resources/guizang/{style}/template.html 骨架）
  → 预览 HTML 写到 resources/guizang/{style}/_preview.html（与 assets/ 同目录，
    保证 ./assets/motion.min.js 相对路径可用）→ WebEngine file:// 加载。
  叙事骨架固定、数字全部动态；换一个月的分析 Excel 即出新报告。

交互（页面内置）：
  · ← → / ↑ ↓ / 空格 / 滚轮 翻页
  · B 切换静态模式（关动效 + 关 WebGL，适合投影/录屏）
  · ESC 查看全页总览

实现约定（与 DashboardDialog 保持一致，勿改）：
  1. QtWebEngine 一律在本文件 __init__ 内**延迟 import**（若在模块顶层 import，
     软件一启动就初始化 Chromium 内核，导致长时间 hang）。
  2. WebEngine 不可用时自动降级 QTextBrowser，不让入口点成废键。
  3. 必须开 LocalContentCanAccessFileUrls，否则 file:// 页面读不到同目录 assets 下的 js。
  4. 报告构建放后台 QThread（pandas 读 1.7 万行明细约 1~2 秒），避免 GUI「未响应」。
"""
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
)
from PySide6.QtCore import QUrl, QThread, Signal

# 项目根（gui_pyside6/dialogs/xxx.py → parents[2]）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 两种风格的元信息：键 -> (显示名, 子目录, 一句话说明)
GZ_STYLES = {
    "magazine": ("归藏 · Magazine", "magazine", "电子杂志风：衬线标题 · 墨水经典配色 · 流体背景"),
    "swiss": ("归藏 · Swiss", "swiss", "瑞士国际主义：无衬线极简 · 安全橙强调 · 网格背景"),
}


def guizang_preview_path(style: str) -> Path:
    """返回指定风格预览 HTML 落点（与 assets/ 同目录，相对路径才能解析）。"""
    meta = GZ_STYLES.get(style) or GZ_STYLES["magazine"]
    return PROJECT_ROOT / "resources" / "guizang" / meta[1] / "_preview.html"


class _GuizangBuildWorker(QThread):
    """后台线程：读分析 Excel → 算数 → 渲染归藏 HTML。"""

    html_ready = Signal(str)
    build_failed = Signal(str)
    progress = Signal(str)

    def __init__(self, style: str, excel_path: str, parent=None):
        super().__init__(parent)
        self.style = style
        self.excel_path = excel_path

    def run(self):
        try:
            root = str(PROJECT_ROOT)
            if root not in sys.path:
                sys.path.insert(0, root)
            from core.guizang_report import build_report_data, render_html

            self.progress.emit("正在读取分析结果并计算…")
            data = build_report_data(self.excel_path, log_cb=lambda m: self.progress.emit(m))
            self.progress.emit("正在渲染报告…")
            html = render_html(self.style, data)
            self.html_ready.emit(html)
        except Exception as e:  # noqa: BLE001
            self.build_failed.emit(f"生成归藏报告失败：{e}")


class GuizangDialog(QDialog):
    """归藏网页版报告查看窗（动态注入：数字每次从分析结果 Excel 实时计算）。

    style: 'magazine' | 'swiss'
    excel_path: 分析结果 Excel（需含「完整偏差明细」等 5 个标准 sheet）
    """

    def __init__(self, style: str, excel_path: str, parent=None, main_window=None):
        # ---- WebEngine 延迟导入（关键：勿提到模块顶层）----
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
        self.style = style if style in GZ_STYLES else "magazine"
        self._title_text, self._subdir, self._desc = GZ_STYLES[self.style]
        self.excel_path = str(excel_path)
        self._preview_path = None
        self._worker = None
        self._alive = True
        self._init_ui()
        self._start_build()

    # ------------------------------------------------------------------ UI
    def _init_ui(self):
        self.setWindowTitle(f"{self._title_text} · ZPP011 偏差分析")
        self.resize(1280, 800)
        layout = QVBoxLayout(self)

        # 顶部工具栏：状态 + 刷新 + 系统浏览器 + 关闭
        top = QHBoxLayout()
        self._status = QLabel(f"{self._desc} · 数据源：{Path(self.excel_path).name}")
        self._status.setStyleSheet("color:#656d76;font-size:13px")
        top.addWidget(self._status)
        top.addStretch()

        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.clicked.connect(self._start_build)
        top.addWidget(self._refresh_btn)

        self._browser_btn = QPushButton("用系统浏览器打开")
        self._browser_btn.clicked.connect(self._open_in_browser)
        self._browser_btn.setEnabled(False)
        top.addWidget(self._browser_btn)

        self._close_btn = QPushButton("关闭")
        self._close_btn.clicked.connect(self.accept)
        top.addWidget(self._close_btn)
        layout.addLayout(top)

        # 视图：WebEngine 优先，否则降级 QTextBrowser
        if self._web_engine_ok:
            self.web = self._WebEngineView(self)
            # 允许 file:// 页面访问同目录资源（assets/motion.min.js）
            try:
                st = self.web.settings()
                st.setAttribute(self._WebEngineSettings.LocalContentCanAccessFileUrls, True)
                st.setAttribute(self._WebEngineSettings.LocalContentCanAccessRemoteUrls, True)
                st.setAttribute(self._WebEngineSettings.JavascriptEnabled, True)
            except Exception:  # noqa: BLE001
                pass
            self.web.setHtml(
                "<div style='padding:40px;font-family:sans-serif;color:#555'>"
                "正在根据分析结果构建报告…</div>"
            )
        else:
            self.web = QTextBrowser(self)
            self.web.setAcceptRichText(True)
            self.web.setOpenExternalLinks(False)
            msg = self._web_engine_err or "未知原因"
            self.web.setHtml(
                "<div style='padding:40px;font-family:sans-serif;color:#b00'>"
                "<b>QtWebEngine 不可用，已降级为文本视图。</b><br>"
                f"<small>{msg}</small><br><br>"
                "报告构建完成后点右上角「用系统浏览器打开」查看完整效果。"
                "</div>"
            )
        layout.addWidget(self.web, 1)

    # ----------------------------------------------------------- 构建 / 加载
    def _start_build(self):
        """后台线程生成报告 HTML，避免阻塞 GUI 主线程。"""
        if self._worker is not None and self._worker.isRunning():
            return
        self._refresh_btn.setEnabled(False)
        self._browser_btn.setEnabled(False)
        self._status.setText("正在读取分析结果并计算…")
        self._worker = _GuizangBuildWorker(self.style, self.excel_path)
        self._worker.html_ready.connect(self._on_html_ready)
        self._worker.build_failed.connect(self._on_build_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_progress(self, msg: str):
        if self._alive:
            self._status.setText(msg)

    def _on_html_ready(self, html: str):
        if not self._alive:
            return
        try:
            p = guizang_preview_path(self.style)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(html, encoding="utf-8")
            self._preview_path = p
        except OSError as e:
            self._on_build_failed(f"预览文件写入失败：{e}")
            return
        self._refresh_btn.setEnabled(True)
        self._browser_btn.setEnabled(True)
        self._status.setText(f"{self._desc} · 数据源：{Path(self.excel_path).name}")
        if self._web_engine_ok:
            # 走本地 file:// 加载，assets 相对路径才能正确解析
            self.web.setUrl(QUrl.fromLocalFile(str(self._preview_path)))
        if self.main_window is not None and hasattr(self.main_window, "log"):
            try:
                self.main_window.log(f"归藏报告已生成：{self._preview_path}", "info")
            except Exception:  # noqa: BLE001
                pass

    def _on_build_failed(self, msg: str):
        if not self._alive:
            return
        self._refresh_btn.setEnabled(True)
        self._status.setText("构建失败（可点「刷新」重试）")
        self.web.setHtml(
            "<div style='padding:40px;font-family:sans-serif;color:#b00'>"
            f"<b>{msg}</b><br><br>"
            "请确认所选文件为 ZPP011 分析结果导出的完整 Excel"
            "（需含「完整偏差明细」「汇总统计」「无备注预警」「偏差原因分析」"
            "「趋势分析（自然日分组）」工作表）。</div>"
        )
        if self.main_window is not None and hasattr(self.main_window, "log"):
            try:
                self.main_window.log(msg, "error")
            except Exception:  # noqa: BLE001
                pass

    def _open_in_browser(self):
        """用系统默认浏览器打开预览文件（WebEngine 不可用时的兜底出口）。"""
        if not self._preview_path or not self._preview_path.exists():
            return
        try:
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._preview_path)))
        except Exception:  # noqa: BLE001
            import webbrowser
            webbrowser.open(self._preview_path.as_uri())

    def closeEvent(self, event):
        self._alive = False
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()       # 非事件循环线程下为 no-op，但保留以策万全
            self._worker.wait(5000)   # 等待后台构建结束，避免 use-after-free
        self._worker = None
        super().closeEvent(event)


def open_guizang(style: str, excel_path: str, parent=None, main_window=None) -> "GuizangDialog":
    """便捷入口：构造并模态显示，返回对话框实例。"""
    dlg = GuizangDialog(style, excel_path, parent=parent or main_window, main_window=main_window)
    dlg.exec()
    return dlg


def _default_style() -> str:
    """命令行/调试用：--style=swiss。"""
    for a in sys.argv:
        if a.startswith("--style="):
            return a.split("=", 1)[1]
    return "magazine"


def _pick_excel() -> str:
    """独立调试时手选分析结果 Excel。"""
    from PySide6.QtWidgets import QFileDialog

    path, _ = QFileDialog.getOpenFileName(None, "请选择分析结果 Excel 文件", "", "Excel files (*.xlsx)")
    return path


if __name__ == "__main__":
    # 独立调试：python -m gui_pyside6.dialogs.guizang_dialog --style=swiss
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    excel = _pick_excel()
    if excel:
        open_guizang(_default_style(), excel)
    os._exit(0)
