# -*- coding: utf-8 -*-
"""
Treeview 通用工具函数
包含：列排序、单元格渲染等功能
"""

def sort_treeview_column(tree, col, reverse):
    """
    对 Treeview 的指定列进行排序。
    
    参数:
        tree: Treeview 控件
        col: 列名（column identifier）
        reverse: True 为降序，False 为升序
    
    特性:
        - 自动识别数值列（偏差率、现存量、金额等），按数值排序
        - 识别带 % 的字符串并正确排序
        - 字符串按字母顺序排序
    """
    # 获取当前所有行的值
    rows = [(tree.set(item, col), item) for item in tree.get_children('')]
    
    # 尝试转换为数字排序（如偏差率、现存量、金额等）
    def convert(value):
        if value is None:
            return 0
        # 尝试去掉 % 符号和千分位逗号后转数值
        try:
            # 先去除常见的后缀和分隔符
            clean = str(value).replace('%', '').replace(',', '').strip()
            return float(clean)
        except (ValueError, AttributeError):
            # 不是数值，按字符串排序
            return str(value).lower() if isinstance(value, str) else value
    
    # 排序
    rows.sort(key=lambda x: convert(x[0]), reverse=reverse)
    
    # 重新排列
    for index, (_, item) in enumerate(rows):
        tree.move(item, '', index)
    
    return reverse  # 返回反转后的状态，供下次使用


def setup_column_sorting(tree, column_ids):
    """
    为 Treeview 的多列设置点击排序功能。
    
    参数:
        tree: Treeview 控件
        column_ids: dict，格式为 {column_id: heading_text}
                   例如: {'#1': '序号', '#5': '物料名称', 'dev_rate': '偏差率'}
    
    返回:
        dict，格式为 {column_id: reverse_flag}，用于跟踪每列的排序状态
    
    示例:
        sort_states = setup_column_sorting(audit_tree, {
            '#1': '序号',
            '#5': '物料名称',
            'dev_rate': '偏差率',
            'quota': '定额',
            'actual': '实际'
        })
    """
    sort_states = {}
    
    def on_header_click(col):
        """列头点击处理函数"""
        # 获取当前列的排序状态
        reverse = sort_states.get(col, False)
        
        # 执行排序
        sort_treeview_column(tree, col, reverse)
        
        # 反转状态
        sort_states[col] = not reverse
    
    # 为每个列绑定点击事件
    for col in column_ids:
        tree.heading(col, command=lambda c=col: on_header_click(c))
    
    return sort_states
