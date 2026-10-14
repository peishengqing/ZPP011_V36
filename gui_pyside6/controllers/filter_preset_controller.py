# -*- coding: utf-8 -*-
"""筛选预设控制器（ARC-003 拆分产物，v43.195）

负责：筛选预设的存取 / 应用 / 删除 / 菜单刷新，以及筛选态 ↔ JSON 互转。

模式：组合式。持有 MainWindow 引用（self.mw），方法体从 MainWindow 原样搬迁、
逻辑零改动；MainWindow 侧保留同名薄壳转发，既有调用与信号绑定签名不变。

两个 JSON 互转函数（_filters_to_jsonable / _jsonable_to_filters）保持
@staticmethod —— 它们是纯函数、不依赖任何实例状态。搬迁后薄壳通过
`self.mw.<name>` 转发（staticmethod 经实例访问合法）。
"""

from PySide6.QtWidgets import QInputDialog, QMessageBox

from gui_pyside6.widgets.toast import toast


class FilterPresetController:
    """筛选预设业务控制器（纯 UI 状态存取，不触碰 analyzer 口径层）。"""

    def __init__(self, mw):
        self.mw = mw

    def _filter_preset_store(self):
        return dict(self.mw.config_manager.get("filter_history") or {})

    @staticmethod
    def _filters_to_jsonable(state):
        """get_filters() 里的 set / (列, set) 结构转 JSON 可存形式。"""
        out = {}
        for k, v in (state or {}).items():
            if isinstance(v, set):
                out[k] = sorted(str(x) for x in v)
            elif isinstance(v, tuple) and len(v) == 2 and isinstance(v[1], set):
                out[k] = {"col": v[0], "values": sorted(str(x) for x in v[1])}
            else:
                out[k] = v
        return out

    @staticmethod
    def _jsonable_to_filters(state):
        """_filters_to_jsonable 的逆变换（供 apply_filters 使用）。"""
        out = {}
        for k, v in (state or {}).items():
            if k == "_semi_class_set" and isinstance(v, list):
                out[k] = set(v)
            elif k == "_units" and isinstance(v, dict):
                out[k] = (v.get("col"), set(v.get("values", [])))
            else:
                out[k] = v
        return out

    def _capture_last_used_filter(self):
        """每次发起分析前，把当前筛选记为「上次使用」，预设菜单可一键恢复。"""
        try:
            state = self.mw._filters_to_jsonable(self.mw.filter_panel.get_filters())
            if not state:
                return
            store = self.mw._filter_preset_store()
            store["___last___"] = state
            self.mw.config_manager.set("filter_history", store)
            self.mw._refresh_filter_preset_menu()
        except Exception:
            pass

    def _save_filter_preset(self, name):
        state = self.mw._filters_to_jsonable(self.mw.filter_panel.get_filters())
        store = self.mw._filter_preset_store()
        store[name] = state
        self.mw.config_manager.set("filter_history", store)
        self.mw._refresh_filter_preset_menu()
        toast("筛选预设已保存：%s" % name, level="info", parent=self.mw)

    def _prompt_save_preset(self):
        n = len([k for k in self.mw._filter_preset_store() if k != "___last___"])
        name, ok = QInputDialog.getText(self.mw, "保存筛选预设", "预设名称：", text="预设 %d" % (n + 1))
        name = (name or "").strip()
        if not ok or not name:
            return
        if name == "___last___":
            QMessageBox.warning(self.mw, "保存筛选预设", "名称「___last___」为系统保留，请换一个。")
            return
        self.mw._save_filter_preset(name)

    def _apply_filter_preset(self, name):
        store = self.mw._filter_preset_store()
        state = store.get(name)
        if state is None:
            toast("暂无%s记录" % ("「上次使用」" if name == "___last___" else "预设「%s」" % name), level="info", parent=self.mw)
            return
        self.mw.filter_panel.apply_filters(self.mw._jsonable_to_filters(state))
        toast("已应用%s" % ("「上次使用」筛选" if name == "___last___" else "筛选预设：" + name), level="info", parent=self.mw)

    def _delete_filter_preset(self, name):
        store = self.mw._filter_preset_store()
        if name in store:
            del store[name]
            self.mw.config_manager.set("filter_history", store)
            self.mw._refresh_filter_preset_menu()
            toast("已删除筛选预设：%s" % name, level="info", parent=self.mw)

    def _refresh_filter_preset_menu(self):
        try:
            names = [k for k in self.mw._filter_preset_store() if k != "___last___"]
            self.mw.filter_panel.set_preset_names(names, "___last___" in self.mw._filter_preset_store())
        except Exception:
            pass
