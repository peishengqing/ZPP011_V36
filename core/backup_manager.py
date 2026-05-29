# -*- coding: utf-8 -*-
"""
BackupManager — 异步备份 + 版本弹窗 + 文件占用检测

不修改 storage.py（冷冻区），独立部署。
分析前调用 backup_before_analysis_async()。
"""
import os
import shutil
import threading
import json
from datetime import datetime
from pathlib import Path

from storage.storage import get_audit_db_path, _get_app_dir


class BackupManager:
    """
    异步备份管理器。
    - 分析前备份：backup_before_analysis_async()
    - 版本不匹配弹窗：check_version_compatible()
    - 文件占用检测：is_file_locked()
    """

    MAX_BACKUPS = 10
    MIN_FREE_MB = 100

    # ── 文件占用检测（Windows 可靠方式）──────────────────────

    @staticmethod
    def is_file_locked(filepath: str) -> bool:
        """
        Windows 下可靠检测文件是否被占用。
        用 os.rename 原子操作检测（比 open 方式更可靠）。
        """
        if not os.path.exists(filepath):
            return False
        try:
            # 原子重命名检测：若能重命名说明没被占用
            temp_name = filepath + ".lock_check_tmp"
            if os.path.exists(temp_name):
                os.remove(temp_name)
            os.rename(filepath, temp_name)
            os.rename(temp_name, filepath)
            return False
        except OSError:
            return True

    # ── 版本兼容性检查 ─────────────────────────────────

    @staticmethod
    def check_version_compatible(backup_meta: dict, parent_window=None) -> bool:
        """
        检查备份版本与当前版本是否兼容。
        若不兼容，弹窗让用户决定是否继续。
        返回 True = 允许继续，False = 用户取消。
        """
        from utils.version_history import get_current_version
        current_ver = get_current_version()
        backup_ver = backup_meta.get("version", "unknown")
        if backup_ver == current_ver:
            return True
        # 弹窗确认
        if parent_window:
            try:
                from tkinter import messagebox
                return messagebox.askyesno(
                    "版本不一致",
                    f"备份版本 {backup_ver} 与当前版本 {current_ver} 不一致。\n"
                    f"恢复可能导致数据异常。是否继续？",
                    parent=parent_window
                )
            except Exception:
                pass
        return True  # 非 GUI 环境默认允许

    # ── 异步备份（分析前）────────────────────────────────

    def backup_before_analysis_async(
        self,
        input_excel_path: str,
        audit_db_path: str = None,
        progress_callback=None,
        done_callback=None,
    ):
        """
        异步备份输入文件和审核数据库。
        progress_callback(current, total)
        done_callback(meta, error)
        """
        if audit_db_path is None:
            audit_db_path = get_audit_db_path()

        def task():
            error = None
            meta = {}
            try:
                # 1. 检查磁盘空间
                free_mb = shutil.disk_usage(_get_app_dir()).free // (1024 * 1024)
                if free_mb < self.MIN_FREE_MB:
                    raise Exception(f"磁盘空间不足 {self.MIN_FREE_MB}MB，无法备份")

                total_steps = 2
                if progress_callback:
                    progress_callback(0, total_steps)

                # 2. 备份输入 Excel
                if input_excel_path and os.path.exists(input_excel_path):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_dir = _get_app_dir()
                    excel_backup_name = f"input_{Path(input_excel_path).stem}_{ts}.xlsx"
                    excel_backup_path = os.path.join(backup_dir, excel_backup_name)
                    shutil.copy2(input_excel_path, excel_backup_path)
                    meta["excel_backup"] = excel_backup_path

                if progress_callback:
                    progress_callback(1, total_steps)

                # 3. 备份审核数据库
                if os.path.exists(audit_db_path):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_dir = os.path.dirname(audit_db_path)
                    if not backup_dir:
                        backup_dir = _get_app_dir()
                    db_backup_name = f"audit_log_{ts}.db"
                    db_backup_path = os.path.join(backup_dir, db_backup_name)
                    shutil.copy2(audit_db_path, db_backup_path)
                    meta["db_backup"] = db_backup_path
                    meta["version"] = self._get_current_version()

                if progress_callback:
                    progress_callback(total_steps, total_steps)

                # 4. 清理旧备份（保留最新 MAX_BACKUPS 份）
                self._rotate_backups()

                # 5. 标记需要恢复（供崩溃恢复用）
                self._mark_recovery_needed(meta)

            except Exception as e:
                error = e

            if done_callback:
                # 切回主线程（tkinter 安全）
                done_callback(meta, error)

        threading.Thread(target=task, daemon=True).start()

    # ── 同步备份（供特殊场景调用）───────────────────────

    def backup_before_analysis_sync(
        self, input_excel_path: str, audit_db_path: str = None
    ) -> dict:
        """同步备份，返回 meta 或抛异常。"""
        if audit_db_path is None:
            audit_db_path = get_audit_db_path()
        meta = {}
        free_mb = shutil.disk_usage(_get_app_dir()).free // (1024 * 1024)
        if free_mb < self.MIN_FREE_MB:
            raise Exception(f"磁盘空间不足 {self.MIN_FREE_MB}MB，无法备份")

        # 备份输入 Excel
        if input_excel_path and os.path.exists(input_excel_path):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = _get_app_dir()
            excel_backup_name = f"input_{Path(input_excel_path).stem}_{ts}.xlsx"
            excel_backup_path = os.path.join(backup_dir, excel_backup_name)
            shutil.copy2(input_excel_path, excel_backup_path)
            meta["excel_backup"] = excel_backup_path

        # 备份审核数据库
        if os.path.exists(audit_db_path):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.dirname(audit_db_path)
            if not backup_dir:
                backup_dir = _get_app_dir()
            db_backup_name = f"audit_log_{ts}.db"
            db_backup_path = os.path.join(backup_dir, db_backup_name)
            shutil.copy2(audit_db_path, db_backup_path)
            meta["db_backup"] = db_backup_path
            meta["version"] = self._get_current_version()

        self._rotate_backups()
        self._mark_recovery_needed(meta)
        return meta

    # ── 崩溃恢复 ──────────────────────────────────────────

    def try_restore_from_backup(self, parent_window=None) -> bool:
        """
        启动时检查是否需要恢复。
        如果需要恢复，弹窗询问用户，执行恢复。
        返回 True = 已恢复，False = 未恢复或用户取消。
        """
        flag_path = os.path.join(_get_app_dir(), "_recovery_needed.flag")
        if not os.path.exists(flag_path):
            return False

        try:
            with open(flag_path, "r", encoding="utf-8") as f:
                meta = json.load(f) if hasattr(json, "load") else {}
        except Exception:
            meta = {}

        # 弹窗询问
        if parent_window:
            from tkinter import messagebox
            answer = messagebox.askyesno(
                "检测到异常退出",
                "上次运行异常退出，是否从备份恢复？\n"
                f"备份时间：{meta.get('timestamp', '未知')}",
                parent=parent_window
            )
            if not answer:
                os.remove(flag_path)
                return False

        # 执行恢复
        db_backup = meta.get("db_backup", "")
        if db_backup and os.path.exists(db_backup):
            try:
                shutil.copy2(db_backup, get_audit_db_path())
            except Exception:
                pass

        os.remove(flag_path)
        return True

    # ── 内部方法 ──────────────────────────────────────────

    def _rotate_backups(self):
        """保留最新 MAX_BACKUPS 份 db 备份。"""
        app_dir = _get_app_dir()
        backups = sorted([
            os.path.join(app_dir, f)
            for f in os.listdir(app_dir)
            if f.startswith("audit_log_") and f.endswith(".db")
        ], key=os.path.getmtime)
        while len(backups) > self.MAX_BACKUPS:
            old = backups.pop(0)
            try:
                os.remove(old)
            except Exception:
                pass

    def get_pending_recovery(self):
        """检查是否有待恢复的备份。返回备份 meta 字典，若无则返回 None。"""
        flag_path = os.path.join(_get_app_dir(), "_recovery_needed.flag")
        if not os.path.exists(flag_path):
            return None
        try:
            with open(flag_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return meta
        except Exception:
            return None

    def _mark_recovery_needed(self, meta: dict):
        """写入恢复标记文件。"""
        flag_path = os.path.join(_get_app_dir(), "_recovery_needed.flag")
        meta["timestamp"] = datetime.now().isoformat()
        try:
            import json
            with open(flag_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _clear_recovery_flag(self):
        """正常退出时清除恢复标记。"""
        flag_path = os.path.join(_get_app_dir(), "_recovery_needed.flag")
        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except Exception:
                pass

    @staticmethod
    def _get_current_version() -> str:
        try:
            from utils.version_history import get_current_version
            return get_current_version()
        except Exception:
            return "unknown"
