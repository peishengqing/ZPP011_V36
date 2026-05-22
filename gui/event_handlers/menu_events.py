# -*- coding: utf-8 -*-
"""菜单、关于、列宽锁定等事件"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, json
from widgets import C
from storage import storage


class MenuEvents:
    """菜单、关于、列宽锁定等事件"""
    def _init_menu(self):





        try:





            menubar = tk.Menu(self.root)





            self.root.config(menu=menubar)





            help_menu = tk.Menu(menubar, tearoff=0)





            menubar.add_cascade(label="帮助", menu=help_menu)





            help_menu.add_command(label="查看历史源码", command=self._open_source_backup)





            help_menu.add_separator()





            help_menu.add_command(label="关于", command=self._show_about)





        except Exception as e:





            print(f"[WARN] 菜单栏初始化失败: {e}")











    # ==================== 历史源码查看 ====================





    def _open_source_backup(self):





        backup_dir = os.path.join(os.path.expanduser('~'), '.zpp011_audit', 'source_backups')





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





            ("F1",     "显示本帮助"),





            ("Ctrl+Q", "退出程序"),





        ]





        for key, desc in shortcuts:





            text.insert(tk.END, f"{key:12} {desc}\n")





        text.config(state=tk.DISABLED)











        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)











    def _show_about(self):





        from utils.version_history import (





            get_current_version, get_version_display,





            get_version_history_text, APP_NAME, AUTHOR





        )





        _ver_str = get_current_version()





        _ver_date = ''





        # 从 VERSION_HISTORY 获取日期





        from utils.version_history import VERSION_HISTORY





        if VERSION_HISTORY:





            _ver_date = VERSION_HISTORY[0].get('date', '')





        changelog = get_version_history_text()





        info = (





            f"{APP_NAME}\n"





            f"版本：{_ver_str}\n"





            f"作者：{AUTHOR}\n"





            f"日期：{_ver_date}\n"





            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"





            "功能：SAP生产订单偏差自动分析\n"





            "特点：多条件筛选 + 批量操作 + 替代料管理\n"





            "新增：AI审核建议、审核进度条、日志导出\n"





            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"





        )





        d = tk.Toplevel(self.root)





        d.title("关于")





        d.geometry("480x580")





        d.resizable(False, False)





        d.transient(self.root)





        d.grab_set()





        container = tk.Frame(d, bg="#1a1a2e")





        container.pack(fill="both", expand=True)





        tk.Label(container, text="关于", font=("Microsoft YaHei", 14, "bold"),





                 fg="#e94560", bg="#1a1a2e").pack(pady=(15, 5))





        info_lbl = tk.Label(container, text=info, font=("Microsoft YaHei", 10),





                            fg="#eaeaea", bg="#16213e", justify="left",





                            anchor="w", padx=20, pady=12)





        info_lbl.pack(fill="x", padx=30, ipady=4)





        tk.Label(container, text="📋 版本日志", font=("Microsoft YaHei", 11, "bold"),





                 fg="#0f3460", bg="#1a1a2e", anchor="w",





                 padx=30).pack(fill="x", pady=(10, 0))





        log_frame = tk.Frame(container, bg="#f8f9fa")





        log_frame.pack(fill="both", expand=True, padx=30, pady=(5, 15))





        tb = tk.Text(log_frame, font=("Microsoft YaHei", 9),





                     fg="#1f2328", bg="#ffffff",





                     relief="flat", state="disabled", wrap="word",





                     height=18)





        tb.pack(fill="both", expand=True)





        tb.configure(state="normal")





        tb.insert("1.0", changelog.strip())





        tb.configure(state="disabled")





        tk.Button(container, text="确定", font=("Microsoft YaHei", 10),





                  command=d.destroy, bg="#e94560", fg="white",





                  relief="flat", padx=20, pady=5).pack(pady=(0, 12))











    # ── 界面构建 ────────────────











    def open_output(self):





        """打开输出目录，若目录不存在则打开桌面"""





        output_path = getattr(self, 'output_path', None)





        if output_path and os.path.exists(output_path):





            os.startfile(os.path.dirname(output_path))





        elif self.output_dir.get() and os.path.exists(self.output_dir.get()):





            os.startfile(self.output_dir.get())





        else:





            os.startfile(os.path.expanduser('~'))

















    def _toggle_column_lock(self):





        """切换列宽锁定状态"""





        self.column_locked = not self.column_locked





        self._save_lock_state(self.column_locked)





        





        # 解绑旧事件





        if hasattr(self, 'audit_tree'):





            try:





                self.audit_tree.unbind("<<TreeviewColumnResized>>")





            except:





                pass





            





            # 绑定新事件





            if self.column_locked:





                self.audit_tree.bind("<<TreeviewColumnResized>>", self._on_column_resized_lock)





            else:





                self.audit_tree.bind("<<TreeviewColumnResized>>", self._on_column_resized_save)





        





        self._apply_column_lock()





        self.lock_btn.configure(





            text=self.config.get("ui.lock_button_text_locked", "🔒 已锁定") if self.column_locked else "🔓 可调整",





            bg="#f0f0f0" if self.column_locked else "#e8f5e9"





        )





        self.log(f"列宽{'已锁定' if self.column_locked else '已解锁，可拖动调整'}", "info")











    def _on_column_resized_lock(self, event):





        """锁定状态下：阻止列宽变化，恢复为保存的宽度"""





        col = event.column





        if hasattr(self, 'column_widths') and col in self.column_widths:





            try:





                self.audit_tree.column(col, width=self.column_widths[col], stretch=False)





            except:





                pass











    def _on_column_resized_save(self, event):





        """解锁状态下：保存新的列宽"""





        col = event.column





        try:





            new_w = self.audit_tree.column(col, 'width')





            if not hasattr(self, 'column_widths'):





                self.column_widths = {}





            self.column_widths[col] = new_w





            self._save_column_widths()





        except:





            pass











    def _save_column_widths(self):





        """保存列宽配置到文件"""





        import json





        try:





            from gui.ui_builder import COLUMN_WIDTHS_FILE





            os.makedirs(os.path.dirname(COLUMN_WIDTHS_FILE), exist_ok=True)





            with open(COLUMN_WIDTHS_FILE, 'w', encoding='utf-8') as f:





                json.dump(self.column_widths, f)





        except:





            pass











    def _load_column_widths(self):





        """从文件加载列宽配置"""





        import json





        try:





            from gui.ui_builder import COLUMN_WIDTHS_FILE, DEFAULT_COL_WIDTHS





            if os.path.exists(COLUMN_WIDTHS_FILE):





                with open(COLUMN_WIDTHS_FILE, 'r', encoding='utf-8') as f:





                    saved = json.load(f)





                    return saved





        except:





            pass





        from gui.ui_builder import DEFAULT_COL_WIDTHS





        return DEFAULT_COL_WIDTHS.copy()











    def _reset_default_widths(self):





        """重置列宽为默认值"""





        from gui.ui_builder import DEFAULT_COL_WIDTHS, COLUMN_WIDTHS_FILE





        self.column_widths = DEFAULT_COL_WIDTHS.copy()





        if hasattr(self, 'audit_tree'):





            for col_id, w in DEFAULT_COL_WIDTHS.items():





                try:





                    min_w = w if getattr(self, 'column_locked', True) else 20





                    self.audit_tree.column(col_id, width=w, minwidth=min_w, stretch=False)





                except Exception:





                    pass





        # 删除保存的列宽文件





        try:





            if os.path.exists(COLUMN_WIDTHS_FILE):





                os.remove(COLUMN_WIDTHS_FILE)





        except Exception:





            pass





        self.log("列宽已重置为默认值", "info")

















    def _apply_column_lock(self):





        """将锁定状态应用到审核表格的所有列"""





        if not hasattr(self, 'audit_tree'):





            return





        locked = getattr(self, 'column_locked', True)





        for col in self.audit_tree['columns']:





            try:





                current_width = self.audit_tree.column(col, 'width')





                if locked:





                    self.audit_tree.column(col, stretch=False, minwidth=current_width)





                else:





                    self.audit_tree.column(col, stretch=False, minwidth=20)





            except Exception:





                pass

















    def _restore_column_widths(self):





        """从 ConfigManager 恢复保存的列宽"""





        if not hasattr(self, 'audit_tree') or not hasattr(self, 'config'):





            return





        widths = self.config.get('table.column_widths', {})





        if not widths:





            return





        for col, width in widths.items():





            if col in self.audit_tree['columns']:





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
