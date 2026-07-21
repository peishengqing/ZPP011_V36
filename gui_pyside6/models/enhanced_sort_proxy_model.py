# -*- coding: utf-8 -*-
"""
增强版排序代理模型 - 支持每列独立三态循环

交互逻辑：
1. 点击列头：该列在【未排序 → 升序 → 降序 → 未排序】间循环
2. 排序规则栈：只包含状态为ASCENDING或DESCENDING的列
3. 规则优先级：最后被激活的排序列拥有最高优先级
"""

from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from PySide6.QtGui import QColor
from enum import Enum
from typing import List, Tuple, Dict, Optional
from gui_pyside6.models.data_frame_model import ALT_GROUP_ROLE


class ColumnSortState(Enum):
    """列排序状态枚举"""
    UNSORTED = 0
    ASCENDING = 1
    DESCENDING = 2

    def next_state(self) -> 'ColumnSortState':
        """获取循环中的下一个状态"""
        return ColumnSortState((self.value + 1) % 3)

    def to_qt_order(self) -> Optional[Qt.SortOrder]:
        """转换为Qt的排序方向（仅当已排序时）"""
        if self == ColumnSortState.ASCENDING:
            return Qt.AscendingOrder
        elif self == ColumnSortState.DESCENDING:
            return Qt.DescendingOrder
        return None  # 未排序状态无Qt对应值


class EnhancedSortProxyModel(QSortFilterProxyModel):
    """
    增强版排序代理模型 - 支持每列独立三态循环
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 存储所有列的当前状态
        self._column_states: Dict[int, ColumnSortState] = {}
        # 排序规则栈：只包含已排序的列，按激活时间倒序排列（最后激活的优先级最高）
        self._sort_stack: List[int] = []
        # 预警行缓存：偏差率列索引 + 每行是否为预警行的布尔数组（避免逐格 O(列数) 扫描）
        self._rate_col = None
        self._alert_cache = None
        self._alert_cache_n = -1

    def setSourceModel(self, model):
        """切换源模型时同步缓存失效绑定，保证数据变更后预警标记自动重建。"""
        old = self.sourceModel()
        if old is not None:
            try:
                old.modelReset.disconnect(self._invalidate_alert_cache)
                old.layoutChanged.disconnect(self._invalidate_alert_cache)
                old.dataChanged.disconnect(self._invalidate_alert_cache)
            except Exception:
                pass
        super().setSourceModel(model)
        self._invalidate_alert_cache()
        if model is not None:
            model.modelReset.connect(self._invalidate_alert_cache)
            model.layoutChanged.connect(self._invalidate_alert_cache)
            model.dataChanged.connect(self._invalidate_alert_cache)

    def _invalidate_alert_cache(self, *args):
        """源数据变化时失效预警缓存（行数/内容变化后下次访问自动重建）。"""
        self._rate_col = None
        self._alert_cache = None
        self._alert_cache_n = -1

    def _ensure_alert_cache(self):
        """必要时一次性构建预警行缓存：定位偏差率列 + 计算每行是否超阈值。O(行) 仅重建一次。"""
        src = self.sourceModel()
        if src is None:
            return
        n = src.rowCount()
        if self._alert_cache is not None and self._alert_cache_n == n and self._rate_col is not None:
            return
        # 忽略换行/空白后匹配偏差率列（与 headerData 实际显示一致）
        self._rate_col = None
        for col in range(src.columnCount()):
            cn = ''.join(str(src.headerData(col, Qt.Horizontal, Qt.DisplayRole)).split())
            if cn in ('偏差率(%)', '偏差率'):
                self._rate_col = col
                break
        self._alert_cache = [False] * n
        if self._rate_col is not None:
            for r in range(n):
                val = src.data(src.index(r, self._rate_col), Qt.DisplayRole)
                try:
                    rate = float(str(val).replace('%', '').strip())
                    self._alert_cache[r] = abs(rate) > 10
                except Exception:
                    pass
        self._alert_cache_n = n

    def get_column_state(self, column: int) -> ColumnSortState:
        """获取指定列的当前排序状态"""
        return self._column_states.get(column, ColumnSortState.UNSORTED)

    def set_column_state(self, column: int, state: ColumnSortState) -> None:
        """
        设置指定列的排序状态，并更新排序栈

        核心逻辑：
        1. 更新该列的状态
        2. 如果新状态是UNSORTED，从排序栈中移除该列
        3. 如果新状态是已排序，将该列推到栈顶（使其成为第一优先级）
        4. 触发重新排序
        """
        old_state = self.get_column_state(column)
        self._column_states[column] = state

        # 从排序栈中移除该列（无论新旧状态如何）
        if column in self._sort_stack:
            self._sort_stack.remove(column)

        # 如果新状态是已排序，添加到栈顶
        if state != ColumnSortState.UNSORTED:
            self._sort_stack.append(column)

        # 如果状态从未排序变为已排序，或从已排序变为未排序，需要更新栈
        if (old_state == ColumnSortState.UNSORTED) != (state == ColumnSortState.UNSORTED):
            self._cleanup_sort_stack()

        self.invalidate()

    def _cleanup_sort_stack(self):
        """清理排序栈，移除所有未排序的列"""
        self._sort_stack = [
            col for col in self._sort_stack
            if self.get_column_state(col) != ColumnSortState.UNSORTED
        ]

    def toggle_column_sort(self, column: int) -> ColumnSortState:
        """
        切换指定列的排序状态（用户点击列头时调用）

        返回：
            ColumnSortState: 切换后的新状态
        """
        current_state = self.get_column_state(column)
        new_state = current_state.next_state()
        self.set_column_state(column, new_state)
        return new_state

    def clear_column_sort(self, column: int) -> None:
        """单独清除某一列的排序（设为未排序）"""
        self.set_column_state(column, ColumnSortState.UNSORTED)

    def clear_all_sorting(self) -> None:
        """清空所有排序"""
        self._column_states.clear()
        self._sort_stack.clear()
        self.invalidate()

    def get_active_sort_rules(self) -> List[Tuple[int, Qt.SortOrder]]:
        """获取当前活跃的排序规则（用于lessThan方法）"""
        rules = []
        for column in reversed(self._sort_stack):  # 反转，使栈顶（最后添加）的列优先级最高
            state = self.get_column_state(column)
            if state != ColumnSortState.UNSORTED:
                order = state.to_qt_order()
                if order is not None:
                    rules.append((column, order))
        return rules

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """应用多级排序规则（核心比较逻辑）"""
        source_model = self.sourceModel()
        if source_model is None:
            return super().lessThan(left, right)

        # 获取当前所有活跃的排序规则
        sort_rules = self.get_active_sort_rules()

        # 如果没有排序规则，使用默认行为
        if not sort_rules:
            return left.row() < right.row()

        # 应用所有排序规则
        for column, order in sort_rules:
            left_data = source_model.data(left.sibling(left.row(), column), Qt.DisplayRole)
            right_data = source_model.data(right.sibling(right.row(), column), Qt.DisplayRole)

            # 智能比较逻辑（处理空值、数字、字符串）
            left_is_empty = left_data is None or str(left_data).strip() == ""
            right_is_empty = right_data is None or str(right_data).strip() == ""

            # 空值处理：空值排在最后
            if left_is_empty and right_is_empty:
                continue  # 两个都空，比较下一列
            if left_is_empty:
                return order == Qt.DescendingOrder  # 空值排后面
            if right_is_empty:
                return order == Qt.AscendingOrder  # 非空排前面

            # 尝试数字比较
            try:
                left_str = str(left_data).replace(',', '').replace('￥', '').replace('%', '').strip()
                right_str = str(right_data).replace(',', '').replace('￥', '').replace('%', '').strip()
                left_num = float(left_str)
                right_num = float(right_str)

                if left_num != right_num:
                    if order == Qt.AscendingOrder:
                        return left_num < right_num
                    else:
                        return left_num > right_num
            except (ValueError, TypeError, AttributeError):
                # 字符串比较
                left_str = str(left_data)
                right_str = str(right_data)

                if left_str != right_str:
                    if order == Qt.AscendingOrder:
                        return left_str < right_str
                    else:
                        return left_str > right_str

        # 所有排序列都相等：保持稳定排序
        return left.row() < right.row()

    def _is_alert_row(self, source_row: int) -> bool:
        """检查某行是否为预警行（偏差率 > 10%），结果来自缓存，O(1)。"""
        self._ensure_alert_cache()
        if self._alert_cache is None or source_row < 0 or source_row >= len(self._alert_cache):
            return False
        return self._alert_cache[source_row]

    def data(self, index, role=Qt.DisplayRole):
        """重写 data 方法，为预警行添加浅红色背景"""
        if not index.isValid():
            return None
        source_index = self.mapToSource(index)
        if not source_index.isValid():
            return None
        if role == Qt.BackgroundRole:
            # 替代料组行：透传源模型的组色，不被预警色覆盖，保证同组视觉一致
            if self.sourceModel().data(source_index, ALT_GROUP_ROLE):
                return self.sourceModel().data(source_index, Qt.BackgroundRole)
            if self._is_alert_row(source_index.row()):
                return QColor(255, 200, 200)  # 浅红
        return self.sourceModel().data(source_index, role)
