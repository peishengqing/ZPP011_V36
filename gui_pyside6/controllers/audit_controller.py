# -*- coding: utf-8 -*-
"""
审核控制器
负责：AI审核、批量改状态/备注、复制上一行备注、已读/未读标记等
"""

import pandas as pd
import traceback
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox, QApplication
from core.rule_engine import RuleEngine
from core.ai_client import AIClient
from gui_pyside6.models.workers import AIAuditWorker
from gui_pyside6.dialogs.batch_operations_dialog import (
    BatchChangeStatusDialog, BatchRemarkDialog, BatchExportDialog
)
from core.read_status import save_read_status
from gui_pyside6.services.data_service import snapshot_qty_for, snapshot_note_for


class AuditController(QObject):
    """审核相关业务逻辑"""

    # 信号
    log_message = Signal(str, str)           # (msg, level)
    progress_started = Signal()               # AI审核开始
    progress_updated = Signal(int, int)       # (current, total)
    progress_finished = Signal(object)        # 审核完成，传递更新后的DataFrame
    progress_error = Signal(str)              # 错误信息
    audit_data_changed = Signal(object)        # 数据变更后通知界面刷新

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rule_engine = RuleEngine()
        self.ai_client = AIClient()
        self.ai_worker = None
        self.audit_data = None          # 当前审核数据（DataFrame）

    def set_audit_data(self, df: pd.DataFrame):
        """设置当前数据（由主窗口调用）"""
        self.audit_data = df

    def run_ai_audit(self, df: pd.DataFrame):
        """启动AI审核线程"""
        if self.ai_worker and self.ai_worker.isRunning():
            self.log_message.emit("AI审核已在运行", "warning")
            return
        self.audit_data = df
        self.progress_started.emit()
        self.ai_worker = AIAuditWorker(df, self.rule_engine, self.ai_client)
        self.ai_worker.progress.connect(self.progress_updated)
        self.ai_worker.finished.connect(self._on_ai_finished)
        self.ai_worker.error.connect(self.progress_error)
        self.ai_worker.log.connect(self._on_ai_worker_log)
        self.ai_worker.start()

    def _on_ai_worker_log(self, msg):
        """桥接槽：将 AIAuditWorker 的单参数 log 信号转发为双参数 log_message 信号"""
        self.log_message.emit(msg, "info")

    def cancel_ai_audit(self):
        """取消AI审核"""
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.cancel()
            if not self.ai_worker.wait(3000):
                self.ai_worker.terminate()
                self.ai_worker.wait()
            self.ai_worker = None
            self.log_message.emit("AI审核已取消", "info")

    def _on_ai_finished(self, updated_df):
        self.ai_worker = None
        self.audit_data = updated_df
        self.progress_finished.emit(updated_df)

    # ------------------- 批量操作 -------------------
    def batch_change_status(self, rows: list, parent_widget):
        """批量修改审核状态（弹出对话框）"""
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(parent_widget, "提示", "无数据")
            return
        dialog = BatchChangeStatusDialog(parent_widget, rows, self.audit_data, self._on_batch_change_callback)
        dialog.exec()

    def _on_batch_change_callback(self, updated_df):
        """批量修改状态后的回调"""
        self.audit_data = updated_df
        self.audit_data_changed.emit(updated_df)

    def batch_remark(self, rows: list, parent_widget):
        """批量填写备注"""
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(parent_widget, "提示", "无数据")
            return
        dialog = BatchRemarkDialog(parent_widget, rows, self.audit_data, self._on_batch_remark_callback)
        dialog.exec()

    def _on_batch_remark_callback(self, updated_df):
        self.audit_data = updated_df
        self.audit_data_changed.emit(updated_df)

    def batch_export(self, rows: list, df_subset: pd.DataFrame, parent_widget):
        """批量导出选中行"""
        dialog = BatchExportDialog(parent_widget, df_subset)
        dialog.exec()

    # ------------------- 右键菜单相关 -------------------
    def copy_material_code(self, row_data, status_bar_callback):
        """复制物料编码到剪贴板"""
        code = row_data.get('物料编码', '')
        if code:
            QApplication.clipboard().setText(str(code))
            if status_bar_callback:
                status_bar_callback(f"已复制物料编码: {code}", 2000)

    def copy_previous_remark(self, current_row, source_model, status_bar_callback):
        """复制上一行的备注到当前行"""
        if current_row <= 0:
            status_bar_callback("第一行没有上一行可复制", 2000)
            return False

        df = source_model.getDataFrame()
        # 获取上一行的备注
        prev_remark = ''
        for col in ['备注', '备注原因']:
            if col in df.columns:
                val = df.iloc[current_row - 1][col]
                if pd.notna(val) and str(val).strip() != '':
                    prev_remark = str(val)
                    break

        if not prev_remark:
            status_bar_callback("上一行没有备注可复制", 2000)
            return False

        # 更新当前行的备注列
        try:
            for col in ['备注', '备注原因']:
                if col in df.columns:
                    df.at[df.index[current_row], col] = prev_remark
            source_model.setDataFrame(df)
            self.audit_data = df
            self.audit_data_changed.emit(df)
            status_bar_callback(f"已复制上一行备注：{prev_remark[:30]}", 3000)
            return True
        except Exception as e:
            traceback.print_exc()
            status_bar_callback(f"复制失败: {e}", 3000)
            return False

    def batch_mark_read(self, rows, source_model, is_read, status_bar_callback):
        """批量标记已读/未读"""
        try:
            df = source_model.getDataFrame()

            # 确保 _read 列存在
            if '_read' not in df.columns:
                df['_read'] = 0

            # 如果没有 data_id，尝试用关键列生成（格式匹配 data_service）
            if 'data_id' not in df.columns:
                if '工厂' in df.columns:
                    df['data_id'] = (
                        df['工厂'].astype(str) + '|' +
                        df['订单日期'].astype(str) + '|' +
                        df['流程订单'].astype(str) + '|' +
                        df['物料编码'].astype(str)
                    )
                elif all(c in df.columns for c in ['订单日期', '流程订单', '物料编码']):
                    df['data_id'] = (
                        df['订单日期'].astype(str) + "|" +
                        df['流程订单'].astype(str) + "|" +
                        df['物料编码'].astype(str)
                    )

            for row in rows:
                if row < len(df):
                    df.at[df.index[row], '_read'] = is_read
                    # 安全取 data_id
                    data_id = df.iloc[row].get('data_id')
                    if not data_id:
                        if '工厂' in df.columns:
                            data_id = f"{df.iloc[row].get('工厂')}|{df.iloc[row].get('订单日期')}|{df.iloc[row].get('流程订单')}|{df.iloc[row].get('物料编码')}"
                        elif all(c in df.columns for c in ['订单日期', '流程订单', '物料编码']):
                            data_id = f"{df.iloc[row].get('订单日期')}|{df.iloc[row].get('流程订单')}|{df.iloc[row].get('物料编码')}"
                    fingerprint = df.iloc[row].get('fingerprint', '')
                    if data_id:
                        # 方案A：审核时建立实际数量 + 备注原因基线，供后续变更检测
                        qty = snapshot_qty_for(df, data_id)
                        note = snapshot_note_for(df, data_id)
                        save_read_status(data_id, is_read, fingerprint, snapshot_qty=qty, snapshot_note=note)

            source_model.setDataFrame(df)
            self.audit_data = df
            self.audit_data_changed.emit(df)
            status_bar_callback(f"已批量标记为{'已读' if is_read else '未读'}", 2000)
        except Exception as e:
            traceback.print_exc()
            status_bar_callback(f"批量标记失败: {e}", 3000)

    # ------------------- 其他 -------------------
    def is_record_audited(self, row):
        """判断单条记录是否已审核"""
        try:
            if '审核状态' in row and row['审核状态'] == '已审核':
                return True
            if '备注来源' in row and row['备注来源'] not in ('', 'AI审核', None):
                return True
        except Exception:
            pass
        return False
