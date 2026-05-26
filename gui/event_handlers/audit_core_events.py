# -*- coding: utf-8 -*-
"""AI瀹℃牳 + 鑷姩缁撴鏍稿績浜嬩欢"""

import threading
import tkinter as tk
from tkinter import messagebox
from copy import deepcopy
from core.rule_engine import RuleEngine
from widgets import C
from core.auto_closer import AutoCloser


class AuditCoreEvents:
    """AI瀹℃牳 + 鑷姩缁撴鏍稿績浜嬩欢"""
    def _run_ai_audit(self):





        """AI瀹℃牳锛氬鎵樼粰 AuditPresenter"""





        if self.is_auditing:





            messagebox.showwarning("鎻愮ず", "AI瀹℃牳姝ｅ湪杩愯锛岃绛夊緟瀹屾垚鎴栫偣鍑诲彇娑?)





            return





        if self.audit_data is None or self.audit_data.empty:





            messagebox.showwarning("璀﹀憡", "娌℃湁瀹℃牳鏁版嵁锛岃鍏堝姞杞藉鏍告暟鎹?)





            return











        # 濮旀墭 Presenter 鍑嗗瀹℃牳鏁版嵁





        audit_indices = self.audit_presenter.run_ai_audit()





        if not audit_indices:





            messagebox.showinfo("鎻愮ず", "娌℃湁闇€瑕丄I瀹℃牳鐨勮")





            return











        # 璁剧疆鐘舵€?





        self.progress_bar.configure(mode='determinate', maximum=100)





        self.progress_bar['value'] = 0





        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)





        self.set_status("AI瀹℃牳涓?..")





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





                self.set_status(f"AI瀹℃牳涓?.. {p}%")





            ))











        self.task_manager.run(





            _worker,





            callback=self._on_ai_audit_done,





            error_callback=self._on_ai_audit_error,





            progress_callback=_on_progress,





        )











    def _cancel_ai_audit(self):





        """鍙栨秷褰撳墠 AI 瀹℃牳锛堢洿鎺ヨ缃?cancel_flag锛?""





        if hasattr(self, '_ai_cancel_flag') and self._ai_cancel_flag is not None:





            self._ai_cancel_flag.set()





        self.set_status("姝ｅ湪鍙栨秷AI瀹℃牳...")











    def _on_ai_audit_done(self, popup_rows):





        """AI瀹℃牳瀹屾垚鍥炶皟"""





        self.is_auditing = False





        self.unsaved_ai_results = True





        self.progress_bar.configure(value=100)





        # 淇锛歀ambda 涓嶈兘杩斿洖鍏冪粍锛屾媶鎴愪袱鏉¤鍙?





        self.root.after(400, lambda: self.progress_bar.pack_forget())





        self.root.after(400, lambda: self.progress_bar.configure(mode='indeterminate', value=0))











        # 鍐欏洖瀹℃牳缁撴灉





        for row_data in popup_rows:





            idx = row_data['idx']





            if idx in self.audit_data.index:





                self.audit_data.at[idx, 'audit_result'] = row_data['_audit_result']





                self.audit_data.at[idx, 'AI寤鸿'] = row_data['_ai_suggestion']





                self.audit_data.at[idx, '澶囨敞鏉ユ簮'] = 'AI瀹℃牳'





                self.audit_data.at[idx, '瀹℃牳鏉ユ簮'] = 'AI'











        # 鍒锋柊琛ㄦ牸





        self._refresh_audit_tree(self.audit_data)





        self.set_status(f"AI瀹℃牳瀹屾垚锛屽叡 {len(popup_rows)} 鏉?)











        # 鍙€夛細鏄剧ず缁撴灉绐楀彛





        if popup_rows:





            messagebox.showinfo("瀹屾垚", f"AI瀹℃牳瀹屾垚锛屽叡澶勭悊 {len(popup_rows)} 鏉¤褰?)











    def _on_ai_audit_error(self, exc):





        """AI瀹℃牳閿欒鍥炶皟锛堝湪涓荤嚎绋嬫墽琛岋級"""





        self.is_auditing = False





        self.progress_bar.pack_forget()





        self.progress_bar.configure(mode='indeterminate', value=0)











        if isinstance(exc, InterruptedError):





            self.set_status("AI瀹℃牳宸插彇娑?)





            messagebox.showinfo("宸插彇娑?, "AI瀹℃牳宸茶鐢ㄦ埛鍙栨秷")





        else:





            self.set_status("AI瀹℃牳澶辫触")





            import traceback





            self.log(f"鉂?AI瀹℃牳寮傚父锛歿traceback.format_exc()}", "error")





            messagebox.showerror("AI瀹℃牳澶辫触", f"瀹℃牳杩囩▼鍙戠敓寮傚父锛歕n{str(exc)}")











    def _auto_close(self):





        """鑷姩缁撴锛堝鎵楶resenter锛?""





        if not hasattr(self, '_auto_close_event'):





            self._auto_close_event = threading.Event()





        if not hasattr(self, '_auto_close_cancel_flag'):





            self._auto_close_cancel_flag = None











        if self._auto_close_event.is_set():





            messagebox.showwarning("鎻愮ず", "鑷姩缁撴浠诲姟杩涜涓紝璇峰嬁閲嶅鎿嶄綔")





            return





        if self.audit_data is None or self.audit_data.empty:





            messagebox.showwarning("璀﹀憡", "娌℃湁鏁版嵁鍙搷浣?)





            return











        self._auto_close_event.set()





        self.progress_bar.configure(mode='determinate', maximum=100)





        self.progress_bar['value'] = 0





        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)





        self.set_status("姝ｅ湪鎵ц鑷姩缁撴...")











        # 鍙屽揩鐓э細闃叉瑙勫垯婕傜Щ





        df_to_audit = self.audit_data.copy(deep=True)





        rule_snapshot = deepcopy(self.rule_engine)











        # 鍖呰鍑芥暟锛屼繚瀛?cancel_flag 寮曠敤





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





        """杩涘害鍥炶皟"""





        percent = int(current / total * 100) if total else 0





        self.progress_bar['value'] = percent





        self.progress_bar.update_idletasks()





        eta_text = f", 鍓╀綑绾int(eta)}绉? if eta else ""





        self.set_status(f"鑷姩缁撴涓? {current}/{total} ({percent}%){eta_text}")





    





    def _on_auto_close_done(self, result):





        """鎴愬姛鍥炶皟"""





        df, success, fail, fail_rows = result





        self.audit_data = df





        self._refresh_audit_tree(self.audit_data)





        self._auto_close_event.clear()





        self._auto_close_cancel_flag = None





        self.progress_bar.pack_forget()





        self.set_status(f"鑷姩缁撴瀹屾垚锛屾垚鍔?{success} 琛岋紝澶辫触 {fail} 琛?)





        msg = f"鑷姩缁撴瀹屾垚\n鎴愬姛: {success} 琛孿n澶辫触: {fail} 琛?





        if fail > 0:





            msg += f"\n澶辫触琛屽彿: {fail_rows[:10]}{'...' if len(fail_rows) > 10 else ''}\n璇锋煡鐪嬫棩蹇楄幏鍙栬鎯呫€?





        messagebox.showinfo("瀹屾垚", msg)





    





    def _on_auto_close_error(self, error):





        """閿欒鍥炶皟锛堝彇娑堟椂涓㈠純蹇収锛屼笉鍥炲啓鏁版嵁锛?""





        self._auto_close_event.clear()





        self._auto_close_cancel_flag = None





        self.progress_bar.pack_forget()





        





        if isinstance(error, InterruptedError):





            self.set_status("鑷姩缁撴宸插彇娑?)





            messagebox.showwarning("宸插彇娑?, "鑷姩缁撴鎿嶄綔宸插彇娑堬紝鏁版嵁鏈彉鍔ㄣ€?)





        else:





            self.set_status("鑷姩缁撴澶辫触")





            messagebox.showerror("閿欒", f"鑷姩缁撴澶辫触: {error}")





            from core.logger import get_logger





            get_logger("Events").error(f"鑷姩缁撴寮傛澶辫触: {error}")





    





    def _cancel_auto_close(self):





        """鍙栨秷鑷姩缁撴"""





        if self._auto_close_cancel_flag:





            self._auto_close_cancel_flag.set()

            # B005: wait for worker to finish (max 5s)
            try:
                tid = self.task_manager.current_task_id
                if tid and tid in self.task_manager._tasks:
                    self.task_manager._tasks[tid]["future"].result(timeout=5)
            except Exception:
                pass  # timeout OK, cancel flag already set

            self.set_status("姝ｅ湪鍙栨秷鑷姩缁撴...")





        else:





            messagebox.showwarning("鎻愮ず", "褰撳墠娌℃湁姝ｅ湪杩愯鐨勮嚜鍔ㄧ粨妗堜换鍔?)
