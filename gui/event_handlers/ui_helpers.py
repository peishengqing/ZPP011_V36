# -*- coding: utf-8 -*-
"""
UI 辅助方法（供各 handler 复用）
"""

import tkinter as tk
from tkinter import ttk


class UIHelpers:
    """UI 辅助工具类，通过多重继承混入或直接持有"""

    def __init__(self, parent):
        self._parent = parent  # 持有主窗口/EventsMixIn 实例引用

    def update_progress_bar(self, percent: int, message: str = ""):
        """更新进度条值和文本"""
        if hasattr(self._parent, 'progress_bar') and self._parent.progress_bar:
            self._parent.progress_bar['value'] = percent
            self._parent.progress_bar.update_idletasks()
        if message and hasattr(self._parent, 'set_status'):
            self._parent.set_status(message)

    def set_status_text(self, text: str, color: str = None):
        """设置状态栏文字和颜色"""
        if hasattr(self._parent, 'status_lbl'):
            self._parent.status_lbl.configure(text=text)
            if color:
                self._parent.status_lbl.configure(fg=color)

    def log_message(self, msg: str, level: str = 'info'):
        """统一日志输出"""
        if hasattr(self._parent, 'log'):
            self._parent.log(msg, level)

    def enable_buttons(self, buttons: list):
        """批量启用按钮"""
        for btn_name in buttons:
            btn = getattr(self._parent, btn_name, None)
            if btn and hasattr(btn, 'configure'):
                try:
                    btn.configure(state='normal')
                except:
                    pass

    def disable_buttons(self, buttons: list):
        """批量禁用按钮"""
        for btn_name in buttons:
            btn = getattr(self._parent, btn_name, None)
            if btn and hasattr(btn, 'configure'):
                try:
                    btn.configure(state='disabled')
                except:
                    pass
