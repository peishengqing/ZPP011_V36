# -*- coding: utf-8 -*-
"""
GUI 事件与按钮回调（v39 拆分入口）
仅保留组合，所有实现移至 event_handlers/
"""

import sys as _sys
import os
import tkinter as tk
from tkinter import ttk
import json

from gui.event_handlers import (
    AuditCoreEvents,
    AuditBatchEvents,
    TableEvents,
    ExportEvents,
    AnalysisEvents,
    MenuEvents,
    UtilsEvents,
    UIHelpers,
)


class EventsMixIn(
    AuditCoreEvents,
    AuditBatchEvents,
    TableEvents,
    ExportEvents,
    AnalysisEvents,
    MenuEvents,
    UtilsEvents,
):
    """
    包含所有 GUI 事件处理方法，供 ZPP011Beautiful 继承
    实际实现分布在 event_handlers 子模块中
    """

    def __init__(self, *args, **kwargs):
        # 初始化 UI 辅助工具
        self.ui_helper = UIHelpers(self)
        super().__init__(*args, **kwargs)


def run_app():
    try:
        # 确定基础目录（打包模式下用_MEIPASS，开发模式下用脚本目录）
        if getattr(_sys, 'frozen', False):
            _base_dir = _sys._MEIPASS
        else:
            _base_dir = os.path.dirname(os.path.abspath(_sys.argv[0]))

        # 设置 tcl/tk 库路径（打包后Python DLL所在目录）
        python_dir = os.path.dirname(_sys.executable) if getattr(_sys, 'frozen', False) else _base_dir
        tcl_path = os.path.join(python_dir, 'tcl', 'tcl8.6')
        tk_path = os.path.join(python_dir, 'tcl', 'tk8.6')
        if os.path.isdir(tcl_path):
            os.environ['TCL_LIBRARY'] = tcl_path
        if os.path.isdir(tk_path):
            os.environ['TK_LIBRARY'] = tk_path

        root = tk.Tk()

        # 设置 Windows 任务栏图标（必须在 Tk() 创建后立即设置）
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "YunnanDali.ZPP011.AuditTool.32"
            )
        except Exception:
            pass

        # 设置窗口图标（兼容开发模式和打包模式）
        try:
            if getattr(_sys, 'frozen', False):
                _base_dir = _sys._MEIPASS
            else:
                _base_dir = os.path.dirname(os.path.abspath(_sys.argv[0]))
            # 先用 ICO 设置任务栏图标（Windows）
            _ico_path = os.path.join(_base_dir, 'ZPP011偏差分析器.ico')
            if os.path.exists(_ico_path):
                try:
                    root.iconbitmap(_ico_path)
                except Exception:
                    pass
            # 再用 PNG 设置窗口标题栏图标
            _png_path = os.path.join(_base_dir, 'ZPP011偏差分析器.icon.png')
            if os.path.exists(_png_path):
                try:
                    from PIL import ImageTk
                    _icon_img = ImageTk.PhotoImage(file=_png_path)
                    root.iconphoto(False, _icon_img)
                    root._icon_img = _icon_img  # 保留引用，防止 GC
                except Exception:
                    pass
        except Exception:
            pass

        # ── 启动模式选择 ──
        from gui.app import _get_mode_config_dir
        config_dir = _get_mode_config_dir()
        config_path = os.path.join(config_dir, 'mode.json')
        default_mode = None
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    default_mode = data.get("default_mode", None)
            except Exception:
                pass  # 配置读取失败时选择窗口照常弹出

        selected_mode = None
        if default_mode:
            selected_mode = default_mode
        else:
            from gui.app import ModeSelector
            selector = ModeSelector(root)  # 传入已有的 root，使用 Toplevel 而非新建 tk.Tk()
            selected_mode = selector.selected_mode
            if selected_mode is None:
                # 用户关闭了选择窗口，退出程序
                root.destroy()
                return

        if selected_mode != "analysis":
            # 库存流水模式，创建库存界面
            from gui.inventory_view import InventoryView
            inv_view = InventoryView(root)
            inv_view.pack(fill='both', expand=True)
            root.deiconify()
            root.mainloop()
            return

        from gui.app import ZPP011Beautiful
        app = ZPP011Beautiful(root)

        style = ttk.Style()
        style.theme_use('clam')

        from widgets import C as _C
        style.configure("Custom.Treeview",
                        background='#fafbfc',
                        foreground='#24292e',
                        fieldbackground='#ffffff',
                        rowheight=27,
                        font=("Microsoft YaHei", 9),
                        borderwidth=0,
                        relief="flat")
        style.map("Custom.Treeview",
                  background=[('selected', _C['accent'])],
                  foreground=[('selected', 'white')])
        style.configure("Treeview.Heading", font=("Microsoft YaHei", 9, "bold"))
        style.configure("TProgressbar", background=_C['accent'],
                        troughcolor=_C['surface2'], borderwidth=0, thickness=6)

        # 启动任务管理器轮询
        app.task_manager.poll(app.root)

        root.mainloop()

    except Exception:
        import traceback
        err_file = os.path.join(os.path.expanduser("~"), "Desktop", "app_crash.log")
        with open(err_file, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
