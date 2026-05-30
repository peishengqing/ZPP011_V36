# -*- coding: utf-8 -*-
"""视图管理：保存/加载筛选/排序偏好"""
import json
import os
from typing import Dict, List, Any

VIEWS_FILE = os.path.join(os.path.expanduser('~'), '.zpp011_audit', 'views.json')


class ViewManager:
    def __init__(self):
        self.views = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(VIEWS_FILE):
            try:
                with open(VIEWS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save(self):
        os.makedirs(os.path.dirname(VIEWS_FILE), exist_ok=True)
        with open(VIEWS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.views, f, indent=2, ensure_ascii=False)

    def list_views(self) -> List[str]:
        return list(self.views.keys())

    def save_view(self, name: str, state: Dict[str, Any]):
        self.views[name] = state
        self._save()

    def delete_view(self, name: str):
        if name in self.views:
            del self.views[name]
            self._save()

    def load_view(self, name: str) -> Dict[str, Any]:
        return self.views.get(name, {})

    def get_current_state(self, app) -> Dict[str, Any]:
        """从当前界面收集视图状态"""
        state = {}
        # 1. 筛选条件（filter_widgets）
        filters = {}
        for key, widget in app.filter_widgets.items():
            if key == 'order_date':
                if isinstance(widget, tuple) and len(widget) == 2:
                    start = widget[0].get() if hasattr(widget[0], 'get') else ''
                    end = widget[1].get() if hasattr(widget[1], 'get') else ''
                    filters[key] = [start, end]
                else:
                    val = widget.get() if hasattr(widget, 'get') else ''
                    if val and val != '全部':
                        filters[key] = val
            else:
                val = widget.get() if hasattr(widget, 'get') else ''
                if val and val != '全部':
                    filters[key] = val
        state['filters'] = filters

        # 2. 排序状态
        if hasattr(app, 'sort_columns'):
            state['sort_columns'] = app.sort_columns

        # 3. 列顺序（displaycolumns）
        if hasattr(app, 'audit_tree'):
            state['displaycolumns'] = list(app.audit_tree['displaycolumns'])

        # 4. 列宽
        widths = {}
        if hasattr(app, 'audit_tree'):
            for col in app.audit_tree['columns']:
                widths[col] = app.audit_tree.column(col, 'width')
        state['column_widths'] = widths

        return state

    def apply_state(self, app, state: Dict[str, Any]):
        """将保存的状态应用到界面"""
        # 1. 恢复筛选条件
        filters = state.get('filters', {})
        for key, value in filters.items():
            if key in app.filter_widgets:
                widget = app.filter_widgets[key]
                if key == 'order_date':
                    if isinstance(widget, tuple) and len(widget) == 2 and isinstance(value, (list, tuple)) and len(value) == 2:
                        start_w, end_w = widget
                        start_w.delete(0, 'end')
                        start_w.insert(0, value[0])
                        end_w.delete(0, 'end')
                        end_w.insert(0, value[1])
                else:
                    widget.set(value)

        # 2. 恢复排序
        sort_cols = state.get('sort_columns', [])
        if sort_cols and hasattr(app, '_apply_sort_and_refresh'):
            app.sort_columns = sort_cols
            app._apply_sort_and_refresh()

        # 3. 恢复列顺序（displaycolumns）
        disp_cols = state.get('displaycolumns', [])
        if disp_cols and hasattr(app, 'audit_tree'):
            current_cols = list(app.audit_tree['columns'])
            valid = [c for c in disp_cols if c in current_cols]
            if valid:
                app.audit_tree['displaycolumns'] = tuple(valid)

        # 4. 恢复列宽
        widths = state.get('column_widths', {})
        for col, w in widths.items():
            if hasattr(app, 'audit_tree') and col in app.audit_tree['columns']:
                app.audit_tree.column(col, width=w)

        # 5. 触发一次筛选刷新
        if hasattr(app, '_on_filter_changed'):
            app._on_filter_changed(None)
