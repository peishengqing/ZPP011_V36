# -*- coding: utf-8 -*-
"""
筛选控制器（ARC-003 新增）
负责统一管理筛选状态、事件和级联逻辑
"""

from typing import Callable, List, Optional, Dict, Any
from PySide6.QtCore import QObject, QTimer
import sys
import os
import datetime
import json
import uuid
import zipfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui_pyside6.models.store import AppState, FilterRule
from gui_pyside6.models.event_bus import EventBus

class FilterPreset:
    """筛选预设记录，包含使用历史"""
    def __init__(self, name: str, rules: List[FilterRule], created_at: datetime.datetime = None, preset_id: str = None):
        self.name = name
        self.rules = rules.copy()
        self.created_at = created_at or datetime.datetime.now()
        self.used_count = 0
        self.last_used_at = None
        self.preset_id = preset_id or str(uuid.uuid4())

    def to_dict(self) -> Dict:
        return {
            'preset_id': self.preset_id,
            'name': self.name,
            'rules': [
                {'column': r.column, 'condition': r.condition, 'value': r.value}
                for r in self.rules
            ],
            'created_at': self.created_at.isoformat(),
            'created_by': self._get_user_hint(),
            'used_count': self.used_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'history': getattr(self, 'history', [])  # 使用历史
        }

    @staticmethod
    def from_dict(data: Dict) -> 'FilterPreset':
        rules = [
            FilterRule(
                column=r['column'],
                condition=r['condition'],
                value=r['value']
            )
            for r in data.get('rules', [])
        ]
        preset = FilterPreset(
            name=data['name'],
            rules=rules,
            created_at=datetime.datetime.fromisoformat(data['created_at']),
            preset_id=data.get('preset_id')
        )
        preset.used_count = data.get('used_count', 0)
        if data.get('last_used_at'):
            preset.last_used_at = datetime.datetime.fromisoformat(data['last_used_at'])
        if 'history' in data:
            preset.history = data['history']
        return preset

    def _get_user_hint(self) -> str:
        """获取用户提示"""
        import pwd
        try:
            return pwd.getpwuid(os.getuid()).pw_name
        except:
            return os.getenv('USERNAME', 'User')

    def add_history_entry(self, applied_at: datetime.datetime = None, reason: str = None):
        """添加使用历史"""
        if not hasattr(self, 'history'):
            self.history = []
        self.history.append({
            'applied_at': applied_at,
            'reason': reason,
            'timestamp': datetime.datetime.now().isoformat()
        })



class FilterController(QObject):
    """筛选状态控制器"""

    def __init__(self, app_state: AppState, event_bus: EventBus, config_manager):
        super().__init__()
        self.app_state = app_state
        self.event_bus = event_bus
        self.config_manager = config_manager
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)  # 300ms 防抖
        self._debounce_timer.timeout.connect(self._apply_debounced_filters)
        self._pending_filter_rules: List[FilterRule] = []
        self._preview_preset: Optional[FilterPreset] = None  # 当前预览的预设

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

    # ========== Phase 5 新增：预设管理 ==========

    def save_preset(self, name: str, rules: List[FilterRule]) -> bool:
        """保存筛选预设到 store"""
        preset = FilterPreset(name, rules)
        # 从 App Storage 获取预设列表（可以在 AppState 中扩展）
        store = self.app_state.get_preset_store()
        store[name] = preset.to_dict()
        self.app_state.set_preset_store(store)
        return True

    def load_preset(self, name: str) -> Optional[FilterPreset]:
        """加载筛选预设"""
        store = self.app_state.get_preset_store()
        data = store.get(name)
        if data:
            return FilterPreset.from_dict(data)
        return None

    def delete_preset(self, name: str) -> bool:
        """删除筛选预设"""
        store = self.app_state.get_preset_store()
        if name in store:
            del store[name]
            self.app_state.set_preset_store(store)
            return True
        return False

    def list_presets(self) -> List[FilterPreset]:
        """列出所有筛选预设"""
        store = self.app_state.get_preset_store()
        presets = []
        for name, data in store.items():
            if name != "___last___":
                try:
                    presets.append(FilterPreset.from_dict(data))
                except Exception:
                    pass
        # 按使用次数降序
        return sorted(presets, key=lambda p: p.used_count, reverse=True)

    def apply_preset(self, preset: FilterPreset) -> None:
        """应用筛选预设"""
        self.set_filters(preset.rules)
        # 更新使用记录
        preset.used_count += 1
        preset.last_used_at = datetime.datetime.now()
        # 保存到 Last Used
        self._apply_preset_to_last_used(preset)
        self.apply_filters_immediately()

    def _apply_preset_to_last_used(self, preset: FilterPreset) -> None:
        """更新「上次使用」预设"""
        store = self.app_state.get_preset_store()
        store["___last___"] = preset.to_dict()
        self.app_state.set_preset_store(store)

    def get_last_used_preset(self) -> Optional[FilterPreset]:
        """获取「上次使用」预设"""
        store = self.app_state.get_preset_store()
        data = store.get("___last___")
        if data:
            return FilterPreset.from_dict(data)
        return None

    def get_preset_store(self) -> Dict:
        """获取预设存储字典"""
        # 从 AppState 的扩展中获取
        if not hasattr(self.app_state, '_preset_store'):
            self.app_state._preset_store = {}
        return self.app_state._preset_store

    def set_preset_store(self, store: Dict) -> None:
        """设置预设存储字典"""
        self.app_state._preset_store = store

    # ========== Phase 5 增强：导入导出和快速切换 ==========

    def export_presets_to_file(self, file_path: str) -> bool:
        """导出所有筛选预设到 JSON 文件"""
        try:
            presets = self.list_presets()
            export_data = {
                'version': '1.0',
                'export_time': datetime.datetime.now().isoformat(),
                'presets': [p.to_dict() for p in presets]
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_only=False, indent=2)
            return True
        except Exception:
            # 记录日志或显示错误
            return False

    def import_presets_from_file(self, file_path: str) -> List[str]:
        """从 JSON 文件导入筛选预设，返回导入的预设名称列表"""
        imported = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            store = self.get_preset_store()
            for preset_dict in import_data.get('presets', []):
                try:
                    preset = FilterPreset.from_dict(preset_dict)

                    # 避免重复（如果同名则按时间追加后缀）
                    base_name = preset.name
                    counter = 1
                    while preset.name in store:
                        preset.name = f"{base_name}_{counter}"
                        counter += 1

                    store[preset.name] = preset.to_dict()
                    imported.append(preset.name)
                except Exception:
                    continue

            self.set_preset_store(store)
            return imported
        except Exception:
            return imported

    def create_new_preset_from_dict(self, name: str, rules: List[FilterRule], preset_id: str = None) -> FilterPreset:
        """创建新的筛选预设实例"""
        preset = FilterPreset(name, rules, preset_id=preset_id)
        return preset

    def duplicate_preset(self, source_name: str) -> Optional[FilterPreset]:
        """复制一个预设"""
        source = self.load_preset(source_name)
        if not source:
            return None

        # 添加时间戳后缀
        suffix = datetime.datetime.now().strftime("_%H%M%S")
        new_name = source.name + suffix

        # 创建新的预设实例
        new_preset = self.create_new_preset_from_dict(
            name=new_name,
            rules=source.rules.copy(),
            preset_id=source.preset_id  # 保留引用但作为副本
        )

        # 保存到存储
        store = self.get_preset_store()
        store[new_name] = new_preset.to_dict()
        self.set_preset_store(store)

        return new_preset

    def clone_preset_to_current(self, preset_name: str) -> None:
        """克隆预设到当前筛选（不应用，只复制规则）"""
        preset = self.load_preset(preset_name)
        if preset:
            self.set_filters(preset.rules)

    def get_history_since(self, name: str, since_date: datetime.datetime = None) -> Optional[List[dict]]:
        """获取预设的指定日期以来的使用历史"""
        preset = self.load_preset(name)
        if not preset:
            return None

        if not since_date:
            return preset.history

        return [h for h in preset.history if datetime.datetime.fromisoformat(h['timestamp']) >= since_date]

    def export_preset_to_file_v2(self, preset_name: str, file_path: str) -> bool:
        """导出单个预设到文件"""
        preset = self.load_preset(preset_name)
        if not preset:
            return False

        export_data = {
            'version': '1.0',
            'export_time': datetime.datetime.now().isoformat(),
            'preset': preset.to_dict()
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_only=False, indent=2)
        return True

    def import_presets_from_zip(self, zip_path: str) -> List[str]:
        """从 ZIP 文件导入全部预设"""
        imported = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    if member.endswith('.json'):
                        try:
                            with zip_ref.open(member) as f:
                                content = f.read().decode('utf-8')
                                import_data = json.loads(content)
                                # 从 zip 内容导入，而不是传到外部函数
                                store = self.get_preset_store()
                                for preset_dict in import_data.get('presets', []):
                                    try:
                                        preset = FilterPreset.from_dict(preset_dict)
                                        # 避免重复
                                        base_name = preset.name
                                        counter = 1
                                        while preset.name in store:
                                            preset.name = f"{base_name}_{counter}"
                                            counter += 1
                                        store[preset.name] = preset.to_dict()
                                        imported.append(preset.name)
                                    except Exception:
                                        continue
                                self.set_preset_store(store)
                        except Exception:
                            continue
            return imported
        except Exception:
            return imported
