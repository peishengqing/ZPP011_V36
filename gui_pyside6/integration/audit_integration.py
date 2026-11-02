# -*- coding: utf-8 -*-
"""
审计系统集成 - 添加到主窗口
"""

from PySide6.QtWidgets import QMenu, QMessageBox, QInputDialog
from PySide6.QtGui import QAction
from gui_pyside6.services.audit_service import audit_service
from gui_pyside6.dialogs.audit_dialog import AuditDialog


def integrate_audit_into_window(mw):
    """将简化审核系统集成到主窗口"""
    
    # 1. 在工具栏添加审核按钮
    audit_action = QAction("🔍 审核", mw)
    audit_action.setStatusTip("对选中行进行快速审核")
    audit_action.triggered.connect(lambda: _handle_audit_selection(mw))
    # 添加到主窗口的 action_bar 中（如果存在）
    action_bar = getattr(mw, 'action_bar', getattr(mw, '_action_bar', None))
    if action_bar:
        # 使用快速插入模式：Action 直接添加到工具栏
        action_bar.addAction(audit_action)
    
    # 2. 添加快捷操作到右键菜单
    right_click_menu = mw.menu_bar
    
    # 如果还没有审核菜单，则创建
    audit_menu = None
    for menu in right_click_menu.children(QMenu):
        if menu.title() == "审核":
            audit_menu = menu
            break
    
    if not audit_menu:
        audit_menu = right_click_menu.addMenu("审核")
    
    # 添加标记为待审核
    mark_needed_action = QAction("⏳ 标记待审核", mw)
    mark_needed_action.triggered.connect(lambda: _mark_as_needed(mw))
    audit_menu.addAction(mark_needed_action)
    
    # 添加快速审核
    quick_audit_action = QAction("✅ 快速审核", mw)
    quick_audit_action.triggered.connect(lambda: _quick_audit(mw))
    audit_menu.addAction(quick_audit_action)
    
    # 添加查看审核记录
    view_history_action = QAction("📋 查看审核历史", mw)
    view_history_action.triggered.connect(lambda: _view_audit_history(mw))
    audit_menu.addAction(view_history_action)
    
    # 3. 连接审核服务状态变化事件
    service = audit_service
    if hasattr(service, 'status_changed'):
        service.status_changed.connect(mw.refresh_audit_status)
    
    return True


def _get_selected_row_data(mw):
    """获取主表格选中行的数据"""
    # 获取主表格中选中的行
    selection = mw.table_view.selectionModel().selectedRows()
    if selection:
        return mw.source_model.getDataFrame().iloc[selection[0].row()]
    return None


def _mark_as_needed(mw):
    """将选中行标记为待审核"""
    row_data = _get_selected_row_data(mw)
    if not row_data or 'data_id' not in row_data.index:
        from gui_pyside6.widgets.toast import toast
        toast("请选择数据行", level="warning", parent=mw)
        return
    
    data_id = row_data['data_id']
    reason, ok = QInputDialog.getText(mw, "标记待审核", f"请输入 {data_id[:20]} 待审核原因:")
    
    if ok and reason:
        # TODO: 实现标记逻辑
        from gui_pyside6.widgets.toast import toast
        toast(f"已标记 {data_id[:20]} 为待审核", level="info", parent=mw)
