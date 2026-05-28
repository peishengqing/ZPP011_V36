# -*- coding: utf-8 -*-
"""菜单、关于、列宽锁定等事件"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, json
from storage import storage
from widgets import C


class MenuEvents:
    """菜单、关于、列宽锁定等事件"""

    def _init_menu(self):

        try:
            menubar = tk.Menu(self.root)

            self.root.config(menu=menubar)

            help_menu = tk.Menu(menubar, tearoff=0)

            menubar.add_cascade(label="帮助", menu=help_menu)

            help_menu.add_command(
                label="查看历史源码", command=self._open_source_backup
            )

            help_menu.add_separator()

            help_menu.add_command(label="健康检查", command=self._show_health_check)

            help_menu.add_separator()

            help_menu.add_command(label="关于", command=self._show_about)

        except Exception as e:
            print(f"[WARN] 菜单栏初始化失败: {e}")

    # ==================== 历史源码查看 ====================

    def _open_source_backup(self):

        backup_dir = os.path.join(
            os.path.expanduser("~"), ".zpp011_audit", "source_backups"
        )

        if os.path.exists(backup_dir):
            os.startfile(backup_dir)

        else:
            messagebox.showinfo("提示", "还没有任何源码备份，请先执行打包操作")

    # ── 多列联动排序 ─────────────────────────────────────────────

    def _show_shortcuts_help(self):
        """显示快捷键说明对话框"""

        import tkinter as tk

        from tkinter import ttk

        win = tk.Toplevel(self.root)

        win.title("快捷键说明")

        win.geometry("420x260")

        win.resizable(False, False)

        text = tk.Text(win, font=("微软雅黑", 10), wrap=tk.WORD, padx=10, pady=10)

        text.pack(fill=tk.BOTH, expand=True)

        shortcuts = [
            ("Ctrl+S", "保存审核结果"),
            ("Ctrl+E", "导出Excel"),
            ("Ctrl+A", "AI审核备注"),
            ("F1", "显示本帮助"),
            ("Ctrl+Q", "退出程序"),
        ]

        for key, desc in shortcuts:
            text.insert(tk.END, f"{key:12} {desc}\n")

        text.config(state=tk.DISABLED)

        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)

    def _show_about(self):
        from utils.version_history import (
            get_current_version,
            APP_NAME,
            AUTHOR,
            VERSION_HISTORY,
        )

        _ver_str = get_current_version()
        _ver_date = VERSION_HISTORY[0].get("date", "") if VERSION_HISTORY else ""

        d = tk.Toplevel(self.root)
        d.title("关于本软件")
        d.geometry("700x560")
        d.resizable(True, True)
        d.transient(self.root)
        d.grab_set()

        # ── 深色顶部信息栏 ──
        header = tk.Frame(d, bg="#1a1a2e")
        header.pack(fill="x")

        tk.Label(
            header,
            text=APP_NAME,
            font=("Microsoft YaHei", 14, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
        ).pack(pady=(14, 2))

        tk.Label(
            header,
            text=f"版本：{_ver_str}   |   发布日期：{_ver_date}   |   制作人：{AUTHOR}   |   © 2026 云南达利食品有限公司",
            font=("Microsoft YaHei", 9),
            fg="#aaaacc",
            bg="#1a1a2e",
        ).pack(pady=(0, 12))

        # ── 版本日志区域标题 ──
        tk.Label(
            d,
            text="  📋 完整版本日志",
            font=("Microsoft YaHei", 10, "bold"),
            fg="#1a365d",
            bg="#e8eaf6",
            anchor="w",
            relief="flat",
        ).pack(fill="x", padx=0, pady=(8, 0))

        # ── 带滚动条的日志文本框 ──
        log_frame = tk.Frame(d)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(4, 6))

        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")

        tb = tk.Text(
            log_frame,
            font=("Consolas", 9),
            fg="#1f2328",
            bg="#fafafa",
            relief="flat",
            wrap="word",
            yscrollcommand=scrollbar.set,
            bd=1,
        )
        tb.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=tb.yview)

        # 字体标签
        tb.tag_config("ver_header", font=("Microsoft YaHei", 10, "bold"), foreground="#1a365d", spacing1=6)
        tb.tag_config("feat",  font=("Consolas", 9), foreground="#276749")
        tb.tag_config("fix",   font=("Consolas", 9), foreground="#c0392b")
        tb.tag_config("opt",   font=("Consolas", 9), foreground="#2b6cb0")
        tb.tag_config("note",  font=("Consolas", 9), foreground="#7d6608")
        tb.tag_config("sep",   font=("Consolas", 8), foreground="#999999")

        # 按 VERSION_HISTORY 逐版本填充（最新在顶）
        for v in VERSION_HISTORY:
            ver_label = f"【{v.get('version', '?')}】  {v.get('date', '')}"
            tb.insert(tk.END, ver_label + "\n", "ver_header")

            for item in v.get("features", []):
                tb.insert(tk.END, f"  ✨ {item}\n", "feat")
            for item in v.get("fixes", []):
                tb.insert(tk.END, f"  🐛 {item}\n", "fix")
            for item in v.get("optimizations", []):
                tb.insert(tk.END, f"  ⚡ {item}\n", "opt")
            for item in v.get("notes", []):
                tb.insert(tk.END, f"  📌 {item}\n", "note")
            for item in v.get("lessons", []):
                tb.insert(tk.END, f"  📌 {item}\n", "note")

            # 兼容旧格式 changes 数组
            for change in v.get("changes", []):
                if "✨" in change or "【新增】" in change or "✦" in change:
                    tb.insert(tk.END, f"  ✨ {change.lstrip('✨✦ ')}\n", "feat")
                elif "🔧" in change or "【修复】" in change:
                    tb.insert(tk.END, f"  🐛 {change.lstrip('🔧 ')}\n", "fix")
                elif "⚡" in change or "【优化】" in change or "🏗" in change:
                    tb.insert(tk.END, f"  ⚡ {change.lstrip('⚡🏗️ ')}\n", "opt")
                elif "📌" in change or "【教训】" in change:
                    tb.insert(tk.END, f"  📌 {change.lstrip('📌 ')}\n", "note")
                else:
                    tb.insert(tk.END, f"  · {change}\n", "fix")

            tb.insert(tk.END, "\n", "sep")

        tb.configure(state="disabled")
        tb.see("1.0")

        # ── 确定按钮 ──
        tk.Button(
            d,
            text="  关 闭  ",
            font=("Microsoft YaHei", 10),
            command=d.destroy,
            bg="#e94560",
            fg="white",
            relief="flat",
            padx=16,
            pady=5,
            cursor="hand2",
        ).pack(pady=(0, 12))

    def _show_health_check(self):
        """打开健康检查面板"""
        from gui.health_check_dialog import HealthCheckDialog
        HealthCheckDialog(self.root)

    # ── 界面构建 ────────────────

    def open_output(self):
        """打开输出目录，若目录不存在则打开桌面"""

        output_path = getattr(self, "output_path", None)

        if output_path and os.path.exists(output_path):
            os.startfile(os.path.dirname(output_path))

        elif self.output_dir.get() and os.path.exists(self.output_dir.get()):
            os.startfile(self.output_dir.get())

        else:
            os.startfile(os.path.expanduser("~"))

    # ── Task 008：列宽持久化 ────────────────────────────────
    def _init_column_width_tracking(self):
        """初始化列宽追踪（Task 008：根据锁定状态设置绑定）"""
        if not hasattr(self, 'audit_tree'):
            return
        # 初始化 self.column_widths
        if not hasattr(self, 'column_widths'):
            self.column_widths = {col: self.audit_tree.column(col, 'width') for col in self.audit_tree['columns']}
        if getattr(self, 'column_locked', True):
            # 锁定模式：定时恢复列宽
            self._start_column_lock_polling()
        else:
            # 解锁模式：检测拖拽调整
            self.audit_tree.bind('<ButtonRelease-1>', self._on_column_drag_release)

    def _toggle_column_lock(self):
        """切换列宽锁定状态"""

        self.column_locked = not self.column_locked

        self._save_lock_state(self.column_locked)

        # 更新列宽追踪绑定（Task 008：替代不工作的 <<TreeviewColumnResized>>）
        if hasattr(self, "audit_tree"):
            if self.column_locked:
                # 锁定：用定时器轮询恢复列宽
                self._start_column_lock_polling()
            else:
                # 解锁：用 ButtonRelease-1 检测拖拽调整
                self._stop_column_lock_polling()
                self.audit_tree.bind('<ButtonRelease-1>', self._on_column_drag_release)

        self._apply_column_lock()

        self.lock_btn.configure(
            text=self.config.get("ui.lock_button_text_locked", "🔒 已锁定")
            if self.column_locked
            else "🔓 可调整",
            bg="#f0f0f0" if self.column_locked else "#e8f5e9",
        )

        self.log(
            f"列宽{'已锁定' if self.column_locked else '已解锁，可拖动调整'}", "info"
        )

    def _on_column_drag_release(self, event):
        """解锁状态下：鼠标释放时检测列宽变化并保存（Task 008）"""
        # 检查是否在列头区域拖拽了分隔线
        try:
            region = self.audit_tree.identify_region(event.x, event.y)
            if region == 'separator' or region == 'heading':
                # 延迟 300ms 后保存（避免频繁 I/O）
                if hasattr(self, '_width_save_timer') and self._width_save_timer:
                    self.root.after_cancel(self._width_save_timer)
                self._width_save_timer = self.root.after(300, self._save_all_column_widths)
        except Exception:
            pass

    def _save_all_column_widths(self):
        """保存所有列宽到 JSON 文件和 ConfigManager（Task 008：统一双存储）"""
        try:
            if hasattr(self, 'audit_tree'):
                self.column_widths = {}
                for col in self.audit_tree['columns']:
                    self.column_widths[col] = self.audit_tree.column(col, 'width')
                self._save_column_widths()
                # 同步到 ConfigManager
                if hasattr(self, 'config'):
                    self.config.set('table.column_widths', self.column_widths)
        except Exception:
            pass

    # ── 列宽锁定轮询（替代不工作的 <<TreeviewColumnResized>> 事件）──
    _lock_poll_id = None

    def _start_column_lock_polling(self):
        """锁定状态下：每 200ms 检查并恢复列宽"""
        self._stop_column_lock_polling()
        # 解绑 ButtonRelease-1
        if hasattr(self, 'audit_tree'):
            try:
                self.audit_tree.unbind('<ButtonRelease-1>')
            except Exception:
                pass
        self._lock_poll_id = self.root.after(200, self._column_lock_poll)

    def _stop_column_lock_polling(self):
        """停止锁定轮询"""
        if hasattr(self, '_lock_poll_id') and self._lock_poll_id:
            try:
                self.root.after_cancel(self._lock_poll_id)
            except Exception:
                pass
            self._lock_poll_id = None

    def _column_lock_poll(self):
        """锁定轮询：恢复被拖拽改变的列宽"""
        if not getattr(self, 'column_locked', True) or not hasattr(self, 'audit_tree'):
            return
        if hasattr(self, 'column_widths') and self.column_widths:
            for col, w in self.column_widths.items():
                if col in self.audit_tree['columns']:
                    try:
                        current_w = self.audit_tree.column(col, 'width')
                        if current_w != w:
                            self.audit_tree.column(col, width=w, stretch=False)
                    except Exception:
                        pass
        self._lock_poll_id = self.root.after(200, self._column_lock_poll)

    def _save_column_widths(self):
        """保存列宽配置到 JSON 文件（Task 008：含所有列）"""

        import json

        try:
            from gui.ui_builder import COLUMN_WIDTHS_FILE

            # 保存所有列宽（不仅仅是 self.column_widths 中已有的）
            if hasattr(self, 'audit_tree'):
                all_widths = {}
                for col in self.audit_tree['columns']:
                    all_widths[col] = self.audit_tree.column(col, 'width')
                self.column_widths = all_widths

            os.makedirs(os.path.dirname(COLUMN_WIDTHS_FILE), exist_ok=True)

            with open(COLUMN_WIDTHS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.column_widths, f, ensure_ascii=False)

            # 同步到 ConfigManager
            if hasattr(self, 'config'):
                self.config.set('table.column_widths', self.column_widths)

        except:
            pass

    def _load_column_widths(self):
        """从文件加载列宽配置"""

        import json

        try:
            from gui.ui_builder import COLUMN_WIDTHS_FILE, DEFAULT_COL_WIDTHS

            if os.path.exists(COLUMN_WIDTHS_FILE):
                with open(COLUMN_WIDTHS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)

                    return saved

        except:
            pass

        from gui.ui_builder import DEFAULT_COL_WIDTHS

        return DEFAULT_COL_WIDTHS.copy()

    def _reset_default_widths(self):
        """重置列宽为默认值（Task 008：含所有列）"""

        from gui.ui_builder import DEFAULT_COL_WIDTHS, COLUMN_WIDTHS_FILE

        self.column_widths = DEFAULT_COL_WIDTHS.copy()

        if hasattr(self, "audit_tree"):
            for col_id, w in DEFAULT_COL_WIDTHS.items():
                try:
                    min_w = w if getattr(self, "column_locked", True) else 20
                    if col_id in self.audit_tree['columns']:
                        self.audit_tree.column(
                            col_id, width=w, minwidth=min_w, stretch=False
                        )
                except Exception:
                    pass

        # 删除保存的列宽文件

        try:
            if os.path.exists(COLUMN_WIDTHS_FILE):
                os.remove(COLUMN_WIDTHS_FILE)

        except Exception:
            pass

        # 同步清除 ConfigManager 中的列宽配置
        if hasattr(self, "config"):
            try:
                self.config.set("table.column_widths", {})
            except Exception:
                pass

        self.log("列宽已重置为默认值", "info")

    def _apply_column_lock(self):
        """将锁定状态应用到审核表格的所有列"""

        if not hasattr(self, "audit_tree"):
            return

        locked = getattr(self, "column_locked", True)

        for col in self.audit_tree["columns"]:
            try:
                current_width = self.audit_tree.column(col, "width")

                if locked:
                    self.audit_tree.column(col, stretch=False, minwidth=current_width)

                else:
                    self.audit_tree.column(col, stretch=False, minwidth=20)

            except Exception:
                pass

    def _restore_column_widths(self):
        """启动时恢复列宽配置（Task 008：优先从 JSON 文件，其次从 ConfigManager）"""

        if not hasattr(self, "audit_tree"):
            return

        # 优先从 JSON 文件加载（与 _save_column_widths 一致）
        widths = self._load_column_widths()

        # JSON 文件加载失败时，尝试从 ConfigManager 加载
        if not widths:
            if hasattr(self, "config"):
                widths = self.config.get("table.column_widths", {})

        if not widths:
            return

        for col, width in widths.items():
            if col in self.audit_tree["columns"]:
                try:
                    self.audit_tree.column(col, width=int(width))

                except Exception:
                    pass


    def _check_and_upgrade_db(self):
        """





        启动时检测旧 audit_log 表是否需要升级到新 audit_records 表。





        若检测到旧表有数据，弹窗询问用户：清空旧历史 or 保留迁移。





        """

        try:
            if not storage.needs_upgrade():
                return

            choice = messagebox.askyesno(
                "数据库需要升级",
                "检测到旧版审核数据库（v36及之前），需要进行一次性升级。\n\n"
                "「是」= 清空旧历史，重新开始（推荐）\n"
                "「否」= 迁移旧记录到新表（保留历史）\n\n"
                "此升级仅执行一次。",
            )

            storage.upgrade_audit_db(clear_old=(choice == True), log_cb=self.log)

        except Exception as e:
            self.log(f"⚠ 升级检测失败：{e}", "warn")

    # ── 保存审核结果到原 Excel + SQLite ────────────────────────────────
