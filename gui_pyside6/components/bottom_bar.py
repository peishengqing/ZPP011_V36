# -*- coding: utf-8 -*-
"""底部栏组件（运行日志已移除，保留占位以免其他模块引用报错）"""


class BottomBarComponent:
    """底部栏组件：运行日志面板已移除，self.log_group / self.mw.log_text 不再创建。
    MainWindow.log() 保留为空操作，确保各处 self.log(...) 调用不崩溃。"""

    def __init__(self, main_window):
        self.mw = main_window
        # 不再创建任何 widget；日志功能已确认不再需要
