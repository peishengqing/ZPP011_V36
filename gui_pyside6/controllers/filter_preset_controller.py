# -*- coding: utf-8 -*-
"""筛选预设控制器（ARC-003 拆分产物，v43.195）。

负责：筛选预设的存取 / 应用 / 删除 / 菜单刷新，以及筛选态 ↔ JSON 互转。

模式：组合式。持有 MainWindow 引用（self.mw），方法体从 MainWindow 原样搬迁、
逻辑零改动；MainWindow 侧保留同名薄壳转发，既有调用与信号绑定签名不变。

两个 JSON 互转函数（_filters_to_jsonable / _jsonable_to_filters）保持
@staticmethod —— 它们是纯函数、不依赖任何实例状态。搬迁后薄壳通过
`self.mw.<name>` 转发（staticmethod 经实例访问合法）。

v43.282：7 个核心方法回退到 v43.195 的 filter_history 落盘实现（v43.270
Phase 5 的 fc 内存 store 引入重启丢预设 + 应用崩溃两个回归，13 个测试钉
旧契约）；Phase 5 的导入导出/复制方法保留在文件下方，仍走 fc store。
"""

from PySide6.QtWidgets import QInputDialog, QMessageBox, QFileDialog

from gui_pyside6.widgets.toast import toast


class FilterPresetController:
    """筛选预设业务控制器（纯 UI 状态存取，不触碰 analyzer 口径层）。"""

    def __init__(self, mw):
        self.mw = mw
        # 从 FilterController 获取预设管理实例
        self.filter_controller = None

    def _get_filter_controller(self):
        """ lazily 获取 filter_controller（仅 Phase 5 导入导出/复制方法使用）。"""
        if self.filter_controller is None:
            self.filter_controller = self.mw.filter_controller
        return self.filter_controller

    # ──────────────────────────────────────────────────────────────
    # 以下 7 个方法体 v43.282 回退到 v43.195 实现（ARC-003 第三刀契约）。
    # v43.270「Phase 5」把它们改走 FilterController 内存 store，引入三个回归：
    #   1) 预设存 app_state._preset_store（内存），重启即丢（旧走
    #      config_manager.filter_history，落盘持久）；
    #   2) 应用预设不再经 filter_panel.apply_filters 恢复控件，而是
    #      fc.apply_preset → app_state（_data 从未填充）→ get_filtered_dataframe
    #      返回 None → data_controller.on_data_changed(None) 崩溃；
    #   3) 13 个回归测试全红（tests/unit/test_filter_preset_controller.py 11 个
    #      + test_filter_presets.py 2 个集成），钉的正是旧契约。
    # Phase 5 的导入导出/复制（export_presets_to_file 等）保留在本文件下方，
    # 仍走 fc store——该入口后续需要与 filter_history 统一（见 version_history 备注）。
    # ──────────────────────────────────────────────────────────────

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

    # Phase 5 增强功能
    def export_presets_to_file(self, file_path=None):
        """导出所有预设到 JSON 文件"""
        fc = self._get_filter_controller()
        if fc:
            if file_path is None:
                options = QFileDialog.Options()
                file_path, _ = QFileDialog.getSaveFileName(
                    self.mw, "导出筛选预设", "", "JSON 文件 (*.json);;所有文件 (*.*)", options=options
                )
            if file_path:
                success = fc.export_presets_to_file(file_path)
                if success:
                    toast(f"已导出预设到 {file_path}", level="info", parent=self.mw)
                    return True
                else:
                    toast("导出失败", level="error", parent=self.mw)
            return False

    def import_presets_from_file(self, file_path=None):
        """导入筛选预设"""
        fc = self._get_filter_controller()
        if fc:
            if file_path is None:
                options = QFileDialog.Options()
                file_path, _ = QFileDialog.getOpenFileName(
                    self.mw, "导入筛选预设", "", "JSON 文件 (*.json);;所有文件 (*.*)", options=options
                )
            if file_path:
                imported = fc.import_presets_from_file(file_path)
                if imported:
                    toast(f"已导入 {len(imported)} 个预设", level="info", parent=self.mw)
                    self._refresh_filter_preset_menu()
                else:
                    toast("导入失败或没有新预设", level="warning", parent=self.mw)
                return imported
            return []
        return []

    def duplicate_preset(self, name):
        """复制预设"""
        fc = self._get_filter_controller()
        if fc:
            result = fc.duplicate_preset(name)
            if result:
                toast(f"已复制预设：{name}", level="info", parent=self.mw)
                self._refresh_filter_preset_menu()
                return True
            else:
                toast(f"复制失败预设：{name}", level="error", parent=self.mw)
            return False
        return False
