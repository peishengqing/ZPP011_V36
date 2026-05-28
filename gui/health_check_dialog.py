# -*- coding: utf-8 -*-
"""
健康检查对话框 — 依赖、配置、磁盘、数据库状态
完全避开冷冻区，不修改 analyzer.py / storage.py
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
import json
from pathlib import Path

from core.backup_manager import BackupManager
from core.audit_logger import AuditLogger
from core.dry_run_analyzer import DryRunAnalyzer


class HealthCheckDialog:
    """
    健康检查面板：
    - 检查依赖（openpyxl, pandas, pandas, ...）
    - 检查配置完整性
    - 检查磁盘空间
    - 检查数据库状态
    - 提供 dry-run 模拟分析
    - 一键修复（配置修复弹窗预览）
    """

    def __init__(self, parent):
        self.parent = parent
        self.selected_file = None
        self.result_text = None
        self.status_labels = {}

        win = tk.Toplevel(parent)
        self.win = win
        win.title("健康检查")
        win.geometry("620x540")
        win.resizable(True, True)
        win.transient(parent)
        win.grab_set()

        self._build_ui()
        self._run_check()

    # ── UI 构建 ──────────────────────────────────────────────────

    def _build_ui(self):
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill="both", expand=True)

        # 1. 检查项结果表格
        ttk.Label(frm, text="系统检查结果", font=("微软雅黑", 10, "bold")).pack(anchor="w")

        cols = ("check_item", "status", "detail")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=8)
        for col, txt, w in [
            ("check_item", "检查项", 160),
            ("status",      "状态", 80),
            ("detail",      "详情", 320),
        ]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="w" if col != "status" else "center")
        self.tree.pack(fill="x", pady=(4, 8))

        # 2. Dry-run 区域
        sep = ttk.Separator(frm, orient="horizontal")
        sep.pack(fill="x", pady=6)

        ttk.Label(frm, text="模拟分析（dry-run）", font=("微软雅黑", 10, "bold")).pack(anchor="w")

        file_frm = ttk.Frame(frm)
        file_frm.pack(fill="x", pady=(4, 2))
        ttk.Button(file_frm, text="选择 Excel 文件", command=self._select_file).pack(side="left")
        self.file_lbl = ttk.Label(file_frm, text="未选择文件", foreground="#888")
        self.file_lbl.pack(side="left", padx=8)

        opt_frm = ttk.Frame(frm)
        opt_frm.pack(fill="x", pady=2)
        ttk.Label(opt_frm, text="开始日期：").pack(side="left")
        self.start_var = tk.StringVar()
        ttk.Entry(opt_frm, textvariable=self.start_var, width=12).pack(side="left", padx=2)
        ttk.Label(opt_frm, text="结束日期：").pack(side="left", padx=(8, 0))
        self.end_var = tk.StringVar()
        ttk.Entry(opt_frm, textvariable=self.end_var, width=12).pack(side="left", padx=2)

        ttk.Button(frm, text="▶ 执行 Dry-Run", command=self._run_dry_run).pack(anchor="w", pady=4)

        # 3. 结果展示
        result_frm = ttk.LabelFrame(frm, text="Dry-Run 结果", padding=6)
        result_frm.pack(fill="both", expand=True, pady=(4, 4))

        self.result_text = tk.Text(result_frm, height=7, font=("Consolas", 9), wrap="word")
        sb = ttk.Scrollbar(result_frm, command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.result_text.pack(fill="both", expand=True)

        # 4. 底部按钮
        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_frm, text="一键修复", command=self._fix_issues).pack(side="left")
        ttk.Button(btn_frm, text="关闭", command=self.win.destroy).pack(side="right")

    # ── 检查执行 ──────────────────────────────────────────────────

    def _run_check(self):
        """执行所有检查项，刷新表格。"""
        results = []

        # ① 依赖检查
        deps = self._check_dependencies()
        for name, ok, detail in deps:
            results.append((name, "✅ 正常" if ok else "❌ 缺失", detail))

        # ② 配置检查
        cfg_ok, cfg_detail = self._check_config()
        results.append(("配置文件", "✅ 正常" if cfg_ok else "⚠ 异常", cfg_detail))

        # ③ 磁盘空间
        disk_ok, disk_detail = self._check_disk()
        results.append(("磁盘空间", "✅ 充足" if disk_ok else "⚠ 不足", disk_detail))

        # ④ 数据库
        db_ok, db_detail = self._check_database()
        results.append(("审核数据库", "✅ 正常" if db_ok else "⚠ 异常", db_detail))

        # ⑤ 备份恢复状态
        bm = BackupManager()
        pending = bm.get_pending_recovery()
        if pending:
            results.append(("备份恢复", "⚠ 待恢复", f"备份时间：{pending.get('timestamp', '未知')}"))
        else:
            results.append(("备份恢复", "✅ 正常", "无待恢复备份"))

        # 刷新表格
        self.tree.delete(*self.tree.get_children())
        for item in results:
            tag = "ok" if "✅" in item[1] else "warn"
            self.tree.insert("", "end", values=item, tags=(tag,))
        self.tree.tag_configure("ok", foreground="#1b8a34")
        self.tree.tag_configure("warn", foreground="#cc7722")

    # ── 单项检查实现 ──────────────────────────────────────────────

    def _check_dependencies(self):
        """检查关键第三方库。"""
        checks = [
            ("openpyxl",  "openpyxl"),
            ("pandas",    "pandas"),
            ("sqlite3",    "sqlite3"),
        ]
        results = []
        for label, mod in checks:
            try:
                __import__(mod)
                results.append((label, True, "已安装"))
            except ImportError:
                results.append((label, False, "未安装，请运行 pip install"))
        return results

    def _check_config(self):
        """检查 config/defaults.json 是否存在且合法。"""
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "defaults.json")
        cfg_path = os.path.normpath(cfg_path)
        if not os.path.exists(cfg_path):
            return False, f"文件不存在：{cfg_path}"
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                json.load(f)
            return True, f"OK：{os.path.basename(cfg_path)}"
        except Exception as e:
            return False, f"JSON 解析失败：{e}"

    def _check_disk(self):
        """检查磁盘剩余空间（~/.zpp011_audit 所在盘）。"""
        app_dir = os.path.join(os.path.expanduser("~"), ".zpp011_audit")
        try:
            free = shutil.disk_usage(app_dir).free
            free_mb = free // (1024 * 1024)
            if free_mb < 100:
                return False, f"剩余 {free_mb} MB（低于 100 MB 建议）"
            return True, f"剩余 {free_mb} MB"
        except Exception as e:
            return False, str(e)

    def _check_database(self):
        """检查审核数据库是否存在、是否可读写。"""
        from storage.storage import get_audit_db_path
        db_path = get_audit_db_path()
        if not os.path.exists(db_path):
            return False, "数据库文件不存在（将自动创建）"
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            size_kb = os.path.getsize(db_path) // 1024
            return True, f"OK（{size_kb} KB）"
        except Exception as e:
            return False, f"无法访问：{e}"

    # ── Dry-Run ─────────────────────────────────────────────────────

    def _select_file(self):
        path = filedialog.askopenfilename(
            parent=self.win,
            title="选择输入 Excel",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")],
        )
        if path:
            self.selected_file = path
            self.file_lbl.configure(text=os.path.basename(path))

    def _run_dry_run(self):
        if not self.selected_file:
            messagebox.showwarning("提示", "请先选择 Excel 文件", parent=self.win)
            return

        self.result_text.delete("1.0", "end")
        self.result_text.insert("end", "⏳ 正在执行 dry-run，请稍候...\n")

        def worker():
            try:
                result = DryRunAnalyzer.analyze(
                    input_excel_path=self.selected_file,
                    start_date=self.start_var.get().strip() or None,
                    end_date=self.end_var.get().strip() or None,
                )
                # 切回主线程更新 UI
                self.win.after(0, lambda r=result: self._show_dry_run_result(r))
            except Exception as e:
                self.win.after(0, lambda e=e: self.result_text.insert("end", f"❌ 错误：{e}\n"))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _show_dry_run_result(self, result: dict):
        self.result_text.delete("1.0", "end")
        if "error" in result:
            self.result_text.insert("end", f"❌ {result['error']}\n")
            return

        lines = []
        lines.append(f"📊 原始总行数：    {result.get('total_rows', '?')}")
        lines.append(f"📊 筛选后行数：  {result.get('filtered_rows', '?')}")
        lines.append(f"⚠ 偏差率≥10%：  {result.get('high_dev_count', '?')} 行")
        lines.append(f"📝 需补备注：      {result.get('need_note_count', '?')} 行")
        est = result.get('estimated_time_sec', 0)
        lines.append(f"⏱ 预计耗时：       约 {est} 秒（按 5000 行/秒估算）")
        lines.append("")
        lines.append("✅ dry-run 未产生任何临时文件，未修改数据库。")

        self.result_text.insert("end", "\n".join(lines))

    # ── 一键修复 ─────────────────────────────────────────────────

    def _fix_issues(self):
        """
        一键修复：目前仅修复 config/defaults.json 缺失问题。
        修复前弹窗预览操作。
        """
        # 收集需要修复的项
        to_fix = []
        for item_id in self.tree.get_children():
            vals = self.tree.item(item_id, "values")
            if "⚠" in vals[1] or "❌" in vals[1]:
                to_fix.append(vals[0])

        if not to_fix:
            messagebox.showinfo("提示", "没有需要修复的问题。", parent=self.win)
            return

        # 弹窗预览
        preview = "计划执行以下修复：\n\n" + "\n".join(f"  • {item}" for item in to_fix)
        preview += "\n\n是否立即执行？"
        if not messagebox.askyesno("确认修复", preview, parent=self.win):
            return

        # 执行修复
        if "配置文件" in to_fix:
            self._fix_config()
        # 可扩展其他修复...

        # 重新检查
        self._run_check()

    def _fix_config(self):
        """修复配置文件：写入默认 defaults.json。"""
        defaults = {
            "version": "v39.4.1",
            "features": {"enable_s01": False, "enable_alt_pair": True},
            "ui": {"window_geometry": "1200x700"},
        }
        cfg_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        cfg_dir = os.path.normpath(cfg_dir)
        os.makedirs(cfg_dir, exist_ok=True)
        cfg_path = os.path.join(cfg_dir, "defaults.json")
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(defaults, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("修复成功", f"已写入默认配置：\n{cfg_path}", parent=self.win)
        except Exception as e:
            messagebox.showerror("修复失败", str(e), parent=self.win)
