# -*- coding: utf-8 -*-
"""
表格单元格复制工具函数（v1）
合并重复的 copy_selected_cells 实现，供主窗口和所有对话框重用。
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def copy_table_cells(table_view, title="") -> str:
    """
    复制表格选中的单元格到剪贴板。

    Args:
        table_view: QTableView 实例
        title: 可选标题，用于状态反馈

    Returns:
        复制的文本内容，如果失败返回空字符串
    """
    if not table_view or not table_view.selectionModel():
        return ""
    
    selection = table_view.selectionModel()
    if not selection.hasSelection():
        return ""
    
    indexes = selection.selectedIndexes()
    if not indexes:
        return ""
    
    cells = {}
    min_row, max_row = float('inf'), -1
    min_col, max_col = float('inf'), -1
    
    for idx in indexes:
        r, c = idx.row(), idx.column()
        # 单元格值，替换换行为空格
        val = idx.data(Qt.DisplayRole) or ""
        cells[(r, c)] = str(val).replace("\n", " ").replace("\r", "")
        
        min_row = min(min_row, r)
        max_row = max(max_row, r)
        min_col = min(min_col, c)
        max_col = max(max_col, c)
    
    if max_row < 0:
        return ""
    
    # 按表格矩形区域输出，空洞填空
    lines = []
    for r in range(min_row, max_row + 1):
        row_vals = []
        for c in range(min_col, max_col + 1):
            row_vals.append(str(cells.get((r, c), "")))
        lines.append("\t".join(row_vals))
    
    content = "\n".join(lines)
    QApplication.clipboard().setText(content)
    
    # 可选状态反馈
    if title:
        QApplication.clipboard().setText(content)
    
    return content


def copy_selected_cells(table_view, status_bar=None) -> None:
    """
    简化版：复制单元格并显示状态消息（适用于对话框场景）。

    Args:
        table_view: QTableView 实例
        status_bar: 可选状态栏用于显示消息
    """
    content = copy_table_cells(table_view)
    if content and status_bar:
        rows = content.count('\n') + 1
        cols = content.split('\t')[0].count('\t') + 1 if content else 0
        status_bar.showMessage(f"已复制 {rows} 行 × {cols} 列", 2000)
