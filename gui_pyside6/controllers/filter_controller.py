# -*- coding: utf-8 -*-
"""
筛选控制器（ARC-003 新增）
负责统一管理筛选状态、事件和级联逻辑
"""

from typing import Callable, List, Optional, Dict, Any
from PySide6.QtCore import QObject, QTimer
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui_pyside6.models.store import AppState, FilterRule
from gui_pyside6.models.event_bus import EventBus


class FilterController(QObject):
    """筛选状态控制器"""

    def __init__(self, app_state: AppState, event_bus: EventBus):
        super().__init__()
        self.app_state = app_state
        self.event_bus = event_bus
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)  # 300ms 防抖
        self._debounce_timer.timeout.connect(self._apply_debounced_filters)
        self._pending_filter_rules: List[FilterRule] = []

    def reset(self) -> None:
        """重置筛选状态"""
        self.app_state.set_filters([])
        self.event_bus.filters_reset.emit()

    def set_filters(self, rules: List[FilterRule]) -> None:
        """设置筛选规则（立即应用）"""
        self._pending_filter_rules = rules
        self._apply_debounced_filters()

    def add_filter(self, column: str, condition: str, value: Any) -> None:
        """添加一个筛选条件"""
        rule = FilterRule(column=column, condition=condition, value=value)
        self._pending_filter_rules.append(rule)
        self._apply_debounced_filters()

    def update_filter(self, index: int, column: str, condition: str, value: Any) -> None:
        """更新指定索引的筛选条件"""
        if 0 <= index < len(self._pending_filter_rules):
            rule = FilterRule(column=column, condition=condition, value=value)
            self._pending_filter_rules[index] = rule
            self._apply_debounced_filters()

    def remove_filter(self, index: int) -> None:
        """移除指定索引的筛选条件"""
        if 0 <= index < len(self._pending_filter_rules):
            del self._pending_filter_rules[index]
            self._apply_debounced_filters()

    def clear_last_filter(self) -> None:
        """移除最后添加的筛选条件"""
        if self._pending_filter_rules:
            self._pending_filter_rules.pop()
            self._apply_debounced_filters()

    def _apply_debounced_filters(self) -> None:
        """应用筛选（防抖）"""
        self._debounce_timer.stop()
        self._debounce_timer.start()

    def apply_filters_immediately(self) -> None:
        """立即应用筛选（不防抖）"""
        self._debounce_timer.stop()
        self.app_state.set_filters(self._pending_filter_rules.copy())
        self.event_bus.filters_changed.emit()
        self.event_bus.filters_applied.emit()

    def get_filters(self) -> List[FilterRule]:
        """获取当前筛选规则"""
        return self.app_state.get_filters()

    def get_filtered_dataframe(self) -> Optional[Any]:
        """获取筛选后的 DataFrame"""
        return self.app_state.get_filtered_data()

    def create_filters_from_dict(self, filter_dict: Dict[str, Any]) -> List[FilterRule]:
        """
        从字典转换筛选规则（用于 FilterPanel 与 FilterController 桥接）

        FilterPanel.get_filters() 返回的 dict 格式：
        {
            factory_col: "食品",
            workshop_col: "车间1",
            _process_order: "123,456",
            _dev_rate_abs_ge_10: True,
            _dev_rate_range: "绝对值>=10%",
            ...
        }
        """
        filters = []
        for key, value in filter_dict.items():
            if key == "_process_order":
                # 流程订单：逗号分隔
                filters.append(FilterRule(key, 'contains', value.split(',')[0]))
                for part in value.split(',')[1:]:
                    filters.append(FilterRule(key, 'contains', part))
            elif key == "_product_code":
                # 产品物料号：逗号分隔
                filters.append(FilterRule(key, 'contains', value.split(',')[0]))
                for part in value.split(',')[1:]:
                    filters.append(FilterRule(key, 'contains', part))
            elif key == "_material_code":
                # 物料编码：逗号分隔
                filters.append(FilterRule(key, 'contains', value.split(',')[0]))
                for part in value.split(',')[1:]:
                    filters.append(FilterRule(key, 'contains', part))
            elif key == "_material_names":
                # 物料名称：模糊搜索，逗号分隔
                for name in value.split(','):
                    filters.append(FilterRule(key, 'contains', name.strip()))
            elif key == "_dev_rate_abs_ge_10":
                # 特殊数值筛选
                filters.append(FilterRule('偏差率', '>=', 10.0))
                filters.append(FilterRule('偏差率', '<=', -10.0))
            elif key == "_dev_rate_range":
                # 偏差率范围
                range_text = value
                if range_text == "绝对值>=10%":
                    filters.append(FilterRule('偏差率', '>=', 10.0))
                    filters.append(FilterRule('偏差率', '<=', -10.0))
                elif range_text == ">10%":
                    filters.append(FilterRule('偏差率', '>', 10.0))
                elif range_text == ">20%":
                    filters.append(FilterRule('偏差率', '>', 20.0))
                elif range_text == ">30%":
                    filters.append(FilterRule('偏差率', '>', 30.0))
                elif range_text == "<-10%":
                    filters.append(FilterRule('偏差率', '<', -10.0))
                elif range_text == "<-20%":
                    filters.append(FilterRule('偏差率', '<', -20.0))
                elif range_text == "<-30%":
                    filters.append(FilterRule('偏差率', '<', -30.0))
            elif key == "_changed_only":
                # 审核后变更标记
                filters.append(FilterRule('_post_audit_changed', '=', 1))
            elif key == "_quarantined_only":
                # 隔离区标记
                filters.append(FilterRule('_quarantined', '=', 1))
            elif key == "_substitute_only":
                # 替代料标记
                filters.append(FilterRule('是否替代料', 'contains', '是'))
            elif key == "_unused_only":
                # 未投料标记
                filters.append(FilterRule('偏差率', '=', -100.0))
            elif key == "_alert_only":
                # 偏差率预警
                filters.append(FilterRule('偏差率', '>', 10.0))
            elif key == "_plain_only":
                # 无标记（所有标记都忽略）
                filters.append(FilterRule('_post_audit_changed', '=', 0))
                filters.append(FilterRule('_quarantined', '=', 0))
                filters.append(FilterRule('是否替代料', 'contains', '否'))
            elif key in ('_date_start', '_date_end'):
                # 日期范围
                if isinstance(value, str):
                    # QDate 值
                    from datetime import date
                    try:
                        y, m, d = map(int, value.split('-'))
                        qdate = date(y, m, d)
                        filters.append(FilterRule(key, '==', qdate))
                    except:
                        pass
            elif key in ('_semi_class_set',):
                # 半成品分类集
                if value:
                    for cls in value:
                        filters.append(FilterRule(key, 'contains', cls))
            elif key in ('_units',):
                # 单位列表
                if isinstance(value, set):
                    for u in value:
                        filters.append(FilterRule('单位', 'contains', u))
            elif key.startswith('_'):
                # 内部筛选键，跳过
                continue
            else:
                # 普通条件
                filters.append(FilterRule(key, '=', value))

        return filters

    @staticmethod
    def potential_values(df: Any, column: str, exclude_filter: List[FilterRule] = None) -> List[Any]:
        """
        获取某列的候选值（用于级联筛选）

        Args:
            df: 源 DataFrame
            column: 列名
            exclude_filter: 排除的筛选条件（如其他筛选条件）

        Returns:
            唯一值列表
        """
        if exclude_filter is None:
            exclude_filter = []

        # 应用其他筛选条件
        for rule in exclude_filter:
            if rule.column in df.columns:
                if rule.condition == '=':
                    df = df[df[rule.column] == rule.value]
                elif rule.condition == '!=':
                    df = df[df[rule.column] != rule.value]
                elif rule.condition == 'contains':
                    df = df[df[rule.column].astype(str).str.contains(str(rule.value), na=False)]

        if column in df.columns:
            return df[column].unique().tolist()
        return []

    def update_cascades(self, source_column: str, target_rules: List[FilterRule]) -> None:
        """
        更新级联筛选下的可用值

        Args:
            source_column: 源列名（值变化影响级联的列）
            target_rules: 目标筛选规则列表（依赖源列的值更新）
        """
        current_date = self.app_state.get_data()
        if current_date is None:
            return

        for rule in target_rules:
            # 获取源候选值
            if source_column in current_date.columns:
                rule.value = current_date[source_column].unique().tolist()
            else:
                rule.value = []

        # 立即应用筛选以触发事件
        self.apply_filters_immediately()

    def connect_filters_changed(self, callback: Callable) -> None:
        """连接筛选变化事件"""
        self.event_bus.on_filters_changed(callback)

    def connect_filtersApplied(self, callback: Callable) -> None:
        """连接筛选应用事件"""
        self.event_bus.on_filters_applied(callback)

    def connect_filtersReset(self, callback: Callable) -> None:
        """连接筛选重置事件"""
        self.event_bus.on_filters_reset(callback)
