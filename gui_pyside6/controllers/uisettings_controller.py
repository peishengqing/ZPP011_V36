# -*- coding: utf-8 -*-
"""
UI 设置控制器
负责：统计卡片更新、进度/状态标签管理、视图可见性控制
"""

import time
from PySide6.QtCore import QObject

from utils.version_history import VERSION_HISTORY, APP_NAME, AUTHOR
from utils.theme_manager import Thm
from gui_pyside6.themes.tokens import FONT_UI


class UISettingsController(QObject):
    """UI 状态更新控制器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

    # ------------------- 统计卡片更新 -------------------
    def update_summary(self):
        """底部合计标签（配额/实际/偏差率/偏差量/净偏差率）已于 v43.281 按用户
        要求整体移除，本方法保留为空壳：main_window 仍有 ~10 处信号/调用点
        （dataChanged/layoutChanged/工厂切换/筛选回调等）连向 _update_summary，
        拆信号面大且易漏，留空壳最稳。选中合计仍走状态栏（interaction_controller）。
        """
        return

    def update_mark_stats(self):
        """更新主表上方『标记统计』标签"""
        lbl = getattr(self.main_window.main_table, "mark_stats_label", None)
        if lbl is None:
            return

        sm = getattr(self.main_window, 'source_model', None)
        pm = getattr(self.main_window, 'proxy_model', None)
        if sm is None or pm is None:
            lbl.setText("标记统计：—")
            return

        alert = getattr(sm, "_alert_rows", set())
        sub = getattr(sm, "_substitute_rows", set())
        unused = getattr(sm, "_unused_rows", set())
        n_alert = n_sub = n_unused = 0

        rows = pm.rowCount()
        if rows:
            for r in range(rows):
                sr = pm.mapToSource(pm.index(r, 0)).row()
                if sr in alert:
                    n_alert += 1
                if sr in sub:
                    n_sub += 1
                if sr in unused:
                    n_unused += 1

        lbl.setText(
            "🔴 偏差预警 %d 条    🔵 替代料 %d 条    ⚪ 未投料 %d 条"
            % (n_alert, n_sub, n_unused)
        )

    def update_read_counter(self):
        """刷新状态栏常驻的「已读计数」标签（自动 N / 手动 M）。

        口径变更（v43.281）：从「会话增量累加」改为「当前主表实时统计」。
        旧实现只在本次会话新标记已读时 +=，从数据库恢复的历史已读（如日志
        「从数据库恢复了 36 条审核结果」）永远不计入，且自动已读命中 0 条时
        连刷新都不触发——用户看到常驻 0/0，以为功能坏了（2026-10-27 反馈）。
        现改为直接对 view_model.df 统计 _read==1 并按 _read_source 分桶：
        'auto' 归自动，其余（'manual'/''，含老数据无来源）归手动。
        会话累加值（_auto_read_count/_manual_read_count）仅作 df 不可用时的兜底。
        """
        try:
            n_auto = n_manual = 0
            df = None
            vm = getattr(self.main_window, 'view_model', None)
            if vm is not None:
                df = getattr(vm, 'df', None)
            if df is not None and not df.empty and '_read' in df.columns:
                read_rows = df[df['_read'] == 1]
                if '_read_source' in read_rows.columns:
                    src = read_rows['_read_source'].fillna('').astype(str)
                    n_auto = int((src == 'auto').sum())
                    n_manual = int(len(read_rows) - n_auto)
                else:
                    n_manual = int(len(read_rows))
            else:
                n_auto = int(getattr(self.main_window, '_auto_read_count', 0))
                n_manual = int(getattr(self.main_window, '_manual_read_count', 0))
            self.main_window._read_counter_label.setText(
                f"📖 已读：自动 {n_auto} / 手动 {n_manual}"
            )
        except RuntimeError:
            pass  # 标签已被 deleteLater 回收（关窗时序），忽略

    def update_analysis_time_label(self, mode):
        """刷新状态栏常驻的「分析时间」标签。mode 为 '自动' 或 '手动'"""
        try:
            ts = time.strftime("%m-%d %H:%M:%S")
            self.main_window._analysis_time_label.setText(f"分析：{mode} {ts}")
        except RuntimeError:
            pass

    def toggle_stats_from_toolbar(self, visible):
        """从工具栏切换统计面板可见性"""
        if hasattr(self.main_window, 'stats_cards'):
            if visible:
                self.main_window.stats_cards.show_panel()
            else:
                self.main_window.stats_cards._toggle_cards(False)

    def toggle_progress_from_toolbar(self, visible):
        """从工具栏切换进度条可见性"""
        if hasattr(self.main_window, 'main_table'):
            self.main_window.main_table.set_progress_visible(visible)

    def auto_collapse_progress_after_analysis(self):
        """分析完成 6s 后自动收起进度面板；若新一轮分析已开始（_heavy_busy）则放弃"""
        if getattr(self.main_window, '_heavy_busy', False):
            return
        if hasattr(self.main_window, 'main_table'):
            self.main_window.main_table.set_progress_visible(False)

    def on_stats_visibility_changed(self, visible):
        """概览面板显隐变化时同步工具栏按钮文字和顶部容器可见性"""
        # v43.264：图标化后按钮文字去 emoji 前缀（图标常驻，文字只表状态）
        self.main_window.action_btn_toggle_stats.setText("概览" if visible else "显示概览")
        self.main_window.action_btn_toggle_stats.setToolTip("隐藏本次分析概览" if visible else "显示本次分析概览")
        self.main_window._update_top_panel_visibility()

    def on_progress_visibility_changed(self, visible):
        """进度面板显隐变化时同步工具栏按钮文字和顶部容器可见性"""
        self.main_window.action_btn_toggle_progress.setText("进度" if visible else "显示进度")
        self.main_window.action_btn_toggle_progress.setToolTip("隐藏分析进度" if visible else "显示分析进度")

    def update_top_panel_visibility(self):
        """两个面板都隐藏时，把顶部容器也隐藏，释放空间给表格"""
        stats_visible = not self.main_window.stats_cards._user_hidden
        progress_visible = not self.main_window.main_table._progress_hidden
        self.main_window.top_panel.setVisible(stats_visible or progress_visible)

    # ------------------- 倒计时与计时 -------------------
    def update_countdown(self):
        """用真实时间戳差值，比每秒累加更准，也不受 UI 阻塞影响"""
        elapsed = int(time.perf_counter() - getattr(self.main_window, "_analysis_start_ts", 0))
        if elapsed != self.main_window._countdown_seconds:
            self.main_window._countdown_seconds = elapsed
        m, s = divmod(self.main_window._countdown_seconds, 60)
        self.main_window.timer_lbl.setText(f"{m:02d}:{s:02d}")

    def stop_countdown(self):
        """停止倒计时计时器"""
        if hasattr(self.main_window, "_countdown_timer") and self.main_window._countdown_timer is not None:
            try:
                self.main_window._countdown_timer.stop()
            except Exception:
                pass

    def format_elapsed(self):
        """格式化经过的时间，显示为 mm:ss"""
        elapsed = int(time.perf_counter() - getattr(self.main_window, "_analysis_start_ts", 0))
        m, s = divmod(elapsed, 60)
        return f"{m:02d}:{s:02d}"

    # ------------------- 主题切换 -------------------
    def toggle_theme(self):
        """切换亮暗主题"""
        current = self.main_window.styleSheet()
        if current:
            self.load_dark_theme()
        else:
            self.load_dark_theme()

    def load_dark_theme(self):
        """加载暗色主题"""
        from PySide6.QtWidgets import QApplication
        with open('gui_pyside6/dark_theme.qss', 'r', encoding='utf-8') as f:
            QApplication.setStyleOverride(f.read())

    def _on_stats_card_clicked(self, index):
        """统计卡片点击事件（未完全实现，仅占位）"""
        pass

    def _show_about(self):
        """「关于」弹窗（v43.317 真身自 MainWindow 迁入）。"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QTextBrowser
        from PySide6.QtCore import Qt
        dialog = QDialog(self.main_window)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
        dialog.setWindowTitle(f"关于 - ZPP011 {VERSION_HISTORY[0]['version']}")
        dialog.setMinimumSize(680, 560)
        dialog.setObjectName("aboutDialog")
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部信息区
        info_frame = QFrame()
        info_frame.setObjectName("aboutInfoFrame")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(28, 24, 28, 16)
        title_row = QHBoxLayout()
        icon_label = QLabel("\U0001F3ED")
        title_label = QLabel(f"{APP_NAME} {VERSION_HISTORY[0]['version']}")
        title_label.setObjectName("aboutTitle")
        title_row.addWidget(icon_label)
        title_row.addWidget(title_label)
        info_layout.addLayout(title_row)
        desc_label = QLabel("功能：偏差分析 · AI审核 · 批量操作")
        desc_label.setObjectName("aboutDesc")
        info_layout.addWidget(desc_label)
        author_label = QLabel(f"制作人：{AUTHOR} | 云南达利食品")
        author_label.setObjectName("aboutAuthor")
        info_layout.addWidget(author_label)
        main_layout.addWidget(info_frame)

        # 版本日志区
        log_label = QLabel("版本日志")
        log_label.setObjectName("aboutSectionLabel")
        main_layout.addWidget(log_label)

        log_browser = QTextBrowser()
        log_browser.setObjectName("versionLogBrowser")
        log_browser.setOpenExternalLinks(False)
        html = self._build_version_log_html()
        log_browser.setHtml(html)
        main_layout.addWidget(log_browser, 1)

        # 底部按钮
        btn_frame = QFrame()
        btn_frame.setObjectName("aboutBtnFrame")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(88, 34)
        close_btn.setObjectName("aboutCloseBtn")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        main_layout.addWidget(btn_frame)
        dialog.exec()

    def _build_version_log_html(self):
        """生成版本日志 HTML"""
        _c_text = Thm.color("text")
        html_parts = ["<style>"
                      f"body {{ font-family: {FONT_UI}, sans-serif; font-size: 12px; "
                      f"color: {_c_text}; }}"
                      f".ver {{ font-weight: bold; color: {Thm.color('primary')}; "
                      f"font-size: 13px; margin-top: 12px; }}"
                      f".date {{ color: {Thm.color('textMuted')}; font-size: 11px; "
                      f"margin-left: 8px; }}"
                      f".section {{ color: {_c_text}; font-weight: 600; margin-top: 6px; }}"
                      "ul { margin: 2px 0 6px 0; padding-left: 20px; }"
                      "li { margin: 2px 0; }"
                      "</style>"]
        for i, v in enumerate(VERSION_HISTORY):
            ver = v.get("version", "")
            date = v.get("date", "")
            html_parts.append(f'<div class="ver">{ver}<span class="date">{date}</span></div>')
            for section_key, section_title in [("features", "✦ 新功能"), ("fixes", "🔧 修复"), ("optimizations", "⚡ 优化"), ("lessons", "⚠ 教训"), ("notes", "📌 说明")]:
                items = v.get(section_key, [])
                # ⚠ 兼容 str 与 list 两种写法（v43.166）。
                #   version_history 里 features/fixes 历来写成**字符串**，而下面
                #   `for item in items` 对字符串是**逐字符迭代** —— 每个汉字各包一个
                #   <li>，整段被拆成几百行单列，就是「版本日志文字竖排成一列单字」。
                #   实测 v43.165 修复前 features 生成 265 个 <li>、fixes 301 个；
                #   v43.163 的 fixes 更夸张（451 个）。短文案时不明显，长文案即暴露。
                #   归一化：str 视作单个列表项（保留其内部换行语义）。
                if isinstance(items, str):
                    items = [items]
                elif not isinstance(items, (list, tuple)):
                    items = [str(items)]
                if items:
                    html_parts.append(f'<div class="section">{section_title}</div><ul>')
                    for item in items:
                        # ⚠ 转义 < 与 >：版本日志正文里可能引用 HTML 标签名
                        #   （如 v43.166 自己的 fixes 里就写了 `<li>`），不转义会被
                        #   QTextBrowser 当成未知标签 —— 要么吞掉、要么把后面的文本吃掉。
                        #   只转这两个字符，**加粗** 等 Markdown 记号保持原样（它们本就
                        #   是给日志窗口看的字面文本，不是真Markdown）。
                        _txt = (str(item).replace('&', '&amp;')
                                .replace('<', '&lt;').replace('>', '&gt;'))
                        html_parts.append(f'<li>{_txt}</li>')
                    html_parts.append('</ul>')
        return "".join(html_parts)
