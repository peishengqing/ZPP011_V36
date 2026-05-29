# -*- coding: utf-8 -*-
"""视图管理：保存/加载筛选/排序偏好"""
import json
import os

VIEWS_FILE = os.path.join(os.path.expanduser('~'), '.zpp011_audit', 'views.json')


class ViewManager:
    def __init__(self):
        self.views = self._load()

    def _load(self):
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

    def list_views(self):
        return list(self.views.keys())

    def save_view(self, name, state):
        self.views[name] = state
        self._save()

    def delete_view(self, name):
        if name in self.views:
            del self.views[name]
            self._save()

    def load_view(self, name):
        return self.views.get(name, {})
