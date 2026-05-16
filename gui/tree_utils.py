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


def apply_multi_sort(tree, sort_state):
    """
    对 Treeview 应用多列排序。
    依次按 sort_state 中存储的列顺序进行稳定排序。

    参数:
        tree: Treeview 控件
        sort_state: dict，格式为 {column_id: bool}
                    True = 降序, False = 升序
                    只对 is_active=True 的列进行排序
    """
    if not sort_state:
        return

    # 收集所有行数据
    rows = [(item, [tree.set(item, col) for col in sort_state.keys()])
            for item in tree.get_children('')]

    # 从后往前依次排序（保持稳定性）
    cols = list(sort_state.keys())
    for col in reversed(cols):
        reverse = sort_state[col]
        # 转换函数（与 sort_treeview_column 一致）
        def convert(val, _reverse=reverse):
            try:
                clean = str(val).replace('%', '').replace(',', '').strip()
                return float(clean)
            except (ValueError, AttributeError):
                return str(val).lower() if isinstance(val, str) else val

        rows.sort(key=lambda x: convert(tree.set(x[0], col)), reverse=reverse)

    # 重新排列
    for index, (item, _) in enumerate(rows):
        tree.move(item, '', index)


def bind_multi_sort(tree, sort_state_ref, cols=None):
    """
    为 Treeview 的列头绑定多列排序事件。
    普通点击：替换排序条件
    Ctrl+点击：追加/移除排序条件

    参数:
        tree: Treeview 控件
        sort_state_ref: callable，返回当前 sort_state dict 的引用
                        例如: lambda: self._sort_states["audit"]
        cols: list，可选，指定要绑定的列。默认取 tree['columns']
    """
    if cols is None:
        cols = list(tree['columns'])

    def on_tree_click(event):
        """处理整棵树的点击事件，区分行点击和列头点击"""
        sort_state = sort_state_ref()

        # 获取点击位置的 region
        region = tree.identify_region(event.x, event.y)
        if region != 'heading':
            return  # 非列头点击，不处理

        # 获取列名
        col = tree.identify_column(event.x)
        # 列名格式为 #1, #2 等，转为实际列名
        col_index = int(col.replace('#', '')) - 1
        if col_index < 0 or col_index >= len(cols):
            return
        col = cols[col_index]

        # Ctrl+点击：追加/移除该列
        ctrl = (event.state & 0x4) != 0
        if ctrl:
            if col in sort_state:
                del sort_state[col]
            else:
                sort_state[col] = False
        else:
            # 普通点击：切换该列排序方向，或设置升序
            if col in sort_state:
                sort_state[col] = not sort_state[col]
            else:
                sort_state[col] = False

        apply_multi_sort(tree, sort_state)

    tree.bind('<Button-1>', on_tree_click)
