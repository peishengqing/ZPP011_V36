# -*- coding: utf-8 -*-
# core/decorators.py
import tkinter as tk
from tkinter import ttk, messagebox
import traceback
from functools import wraps
from core.logger import get_logger

logger = get_logger("Decorators")

def with_feedback(success_msg="操作成功", error_msg_prefix="操作失败", disable_controls=True, show_progress=False):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 获取根窗口
            root = getattr(self, 'root', None) or getattr(self, 'master', None)
            if not root:
                return func(self, *args, **kwargs)

            # 禁用所有按钮（可选）
            if disable_controls:
                for child in root.winfo_children():
                    if isinstance(child, (tk.Button, ttk.Button)):
                        child.config(state='disabled')
                root.update()

            # 显示状态栏消息
            if hasattr(self, 'set_status'):
                self.set_status("处理中...")

            try:
                result = func(self, *args, **kwargs)
                if success_msg:
                    messagebox.showinfo("完成", success_msg)
                return result
            except Exception as e:
                err_msg = f"{error_msg_prefix}: {str(e)}"
                logger.error(f"{err_msg}\n{traceback.format_exc()}")
                messagebox.showerror("错误", err_msg)
                raise
            finally:
                if disable_controls:
                    for child in root.winfo_children():
                        if isinstance(child, (tk.Button, ttk.Button)):
                            child.config(state='normal')
                if hasattr(self, 'clear_status'):
                    self.clear_status()
        return wrapper
    return decorator
