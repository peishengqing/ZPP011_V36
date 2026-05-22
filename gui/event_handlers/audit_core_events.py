# -*- coding: utf-8 -*-
"""AI审核 + 自动结案核心事件"""

import threading
import tkinter as tk
from tkinter import messagebox
from copy import deepcopy
from core.decorators import with_feedback
from core.auto_closer import AutoCloser


class AuditCoreEvents:
    """AI审核 + 自动结案核心事件"""
    def _run_ai_audit(self):





        """AI审核：委托给 AuditPresenter"""





        if self.is_auditing:





            messagebox.showwarning("提示", "AI审核正在运行，请等待完成或点击取消")





            return





        if self.audit_data is None or self.audit_data.empty:





            messagebox.showwarning("警告", "没有审核数据，请先加载审核数据")





            return











        # 委托 Presenter 准备审核数据





        audit_indices = self.audit_presenter.run_ai_audit()





        if not audit_indices:





            messagebox.showinfo("提示", "没有需要AI审核的行")





            return











        # 设置状态





        self.progress_bar.configure(mode='determinate', maximum=100)





        self.progress_bar['value'] = 0





        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)





        self.set_status("AI审核中...")





        self.audit_presenter._ai_cancel_flag = threading.Event()





        self.audit_presenter.is_auditing = True





        self.is_auditing = True











        df_to_audit = self.audit_data.loc[audit_indices].copy()





        _presenter = self.audit_presenter











        def _worker(progress_callback):





            return _presenter.ai_audit_worker(





                audit_indices, df_to_audit, self.ai_client,





                progress_callback=progress_callback





            )











        def _on_progress(pct):





            self.root.after(0, lambda p=pct: (





                self.progress_bar.configure(value=p),





                self.set_status(f"AI审核中... {p}%")





            ))











        self.task_manager.run(





            _worker,





            callback=self._on_ai_audit_done,





            error_callback=self._on_ai_audit_error,





            progress_callback=_on_progress,





        )











    def _cancel_ai_audit(self):





        """取消当前 AI 审核（直接设置 cancel_flag）"""





        if hasattr(self, '_ai_cancel_flag') and self._ai_cancel_flag is not None:





            self._ai_cancel_flag.set()





        self.set_status("正在取消AI审核...")











    def _on_ai_audit_done(self, popup_rows):





        """AI审核完成回调"""





        self.is_auditing = False





        self.unsaved_ai_results = True





        self.progress_bar.configure(value=100)





        # 修正：Lambda 不能返回元组，拆成两条语句





        self.root.after(400, lambda: self.progress_bar.pack_forget())





        self.root.after(400, lambda: self.progress_bar.configure(mode='indeterminate', value=0))











        # 写回审核结果





        for row_data in popup_rows:





            idx = row_data['idx']





            if idx in self.audit_data.index:





                self.audit_data.at[idx, 'audit_result'] = row_data['_audit_result']





                self.audit_data.at[idx, 'AI建议'] = row_data['_ai_suggestion']





                self.audit_data.at[idx, '备注来源'] = 'AI审核'





                self.audit_data.at[idx, '审核来源'] = 'AI'











        # 刷新表格





        self._refresh_audit_tree(self.audit_data)





        self.set_status(f"AI审核完成，共 {len(popup_rows)} 条")











        # 可选：显示结果窗口





        if popup_rows:





            messagebox.showinfo("完成", f"AI审核完成，共处理 {len(popup_rows)} 条记录")











    def _on_ai_audit_error(self, exc):





        """AI审核错误回调（在主线程执行）"""





        self.is_auditing = False





        self.progress_bar.pack_forget()





        self.progress_bar.configure(mode='indeterminate', value=0)











        if isinstance(exc, InterruptedError):





            self.set_status("AI审核已取消")





            messagebox.showinfo("已取消", "AI审核已被用户取消")





        else:





            self.set_status("AI审核失败")





            import traceback





            self.log(f"❌ AI审核异常：{traceback.format_exc()}", "error")





            messagebox.showerror("AI审核失败", f"审核过程发生异常：\n{str(exc)}")











    def _auto_close(self):





        """自动结案（委托Presenter）"""





        if not hasattr(self, '_auto_close_event'):





            self._auto_close_event = threading.Event()





        if not hasattr(self, '_auto_close_cancel_flag'):





            self._auto_close_cancel_flag = None











        if self._auto_close_event.is_set():





            messagebox.showwarning("提示", "自动结案任务进行中，请勿重复操作")





            return





        if self.audit_data is None or self.audit_data.empty:





            messagebox.showwarning("警告", "没有数据可操作")





            return











        self._auto_close_event.set()





        self.progress_bar.configure(mode='determinate', maximum=100)





        self.progress_bar['value'] = 0





        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)





        self.set_status("正在执行自动结案...")











        # 双快照：防止规则漂移





        df_to_audit = self.audit_data.copy(deep=True)





        rule_snapshot = deepcopy(self.rule_engine)











        # 包装函数，保存 cancel_flag 引用





        def wrapper(cancel_flag, progress_callback):





            self._auto_close_cancel_flag = cancel_flag





            return self.audit_presenter.auto_close(





                df_to_audit, rule_snapshot, progress_callback, cancel_flag





            )











        self.task_manager.run(





            wrapper,





            callback=self._on_auto_close_done,





            error_callback=self._on_auto_close_error,





            progress_callback=self._on_auto_close_progress





        )





    def _on_auto_close_progress(self, current, total, eta):





        """进度回调"""





        percent = int(current / total * 100) if total else 0





        self.progress_bar['value'] = percent





        self.progress_bar.update_idletasks()





        eta_text = f", 剩余约{int(eta)}秒" if eta else ""





        self.set_status(f"自动结案中: {current}/{total} ({percent}%){eta_text}")





    





    def _on_auto_close_done(self, result):





        """成功回调"""





        df, success, fail, fail_rows = result





        self.audit_data = df





        self._refresh_audit_tree(self.audit_data)





        self._auto_close_event.clear()





        self._auto_close_cancel_flag = None





        self.progress_bar.pack_forget()





        self.set_status(f"自动结案完成，成功 {success} 行，失败 {fail} 行")





        msg = f"自动结案完成\n成功: {success} 行\n失败: {fail} 行"





        if fail > 0:





            msg += f"\n失败行号: {fail_rows[:10]}{'...' if len(fail_rows) > 10 else ''}\n请查看日志获取详情。"





        messagebox.showinfo("完成", msg)





    





    def _on_auto_close_error(self, error):





        """错误回调（取消时丢弃快照，不回写数据）"""





        self._auto_close_event.clear()





        self._auto_close_cancel_flag = None





        self.progress_bar.pack_forget()





        





        if isinstance(error, InterruptedError):





            self.set_status("自动结案已取消")





            messagebox.showwarning("已取消", "自动结案操作已取消，数据未变动。")





        else:





            self.set_status("自动结案失败")





            messagebox.showerror("错误", f"自动结案失败: {error}")





            from core.logger import get_logger





            get_logger("Events").error(f"自动结案异步失败: {error}")





    





    def _cancel_auto_close(self):





        """取消自动结案"""





        if self._auto_close_cancel_flag:





            self._auto_close_cancel_flag.set()

            # B005: wait for worker to finish (max 5s)
            try:
                tid = self.task_manager.current_task_id
                if tid and tid in self.task_manager._tasks:
                    self.task_manager._tasks[tid]["future"].result(timeout=5)
            except Exception:
                pass  # timeout OK, cancel flag already set

            self.set_status("正在取消自动结案...")





        else:





            messagebox.showwarning("提示", "当前没有正在运行的自动结案任务")
