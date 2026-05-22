# -*- coding: utf-8 -*-
"""
GUI 事件与按钮回调（v39 拆分入口）
仅保留组合，所有实现移至 event_handlers/
"""

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
