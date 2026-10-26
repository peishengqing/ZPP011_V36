# -*- coding: utf-8 -*-
"""筛选预设控制器（ARC-003 拆分产物，v43.195）

负责：筛选预设的存取 / 应用 / 删除 / 菜单刷新，以及筛选态 ↔ JSON 互转。

模式：组合式。持有 MainWindow 引用（self.mw），方法体从 MainWindow 原样搬迁、
逻辑零改动；MainWindow 侧保留同名薄壳转发，既有调用与信号绑定签名不变。

两个 JSON 互转函数（_filters_to_jsonable / _jsonable_to_filters）保持
@staticmethod —— 它们是纯函数、不依赖任何实例状态。搬迁后薄壳通过
`self.mw.<name>` 转发（staticmethod 经实例访问合法）。
"""

import datetime

from PySide6.QtWidgets import QInputDialog, QMessageBox, QFileDialog

from gui_pyside6.widgets.toast import toast


class FilterPresetController:
    """筛选预设业务控制器（纯 UI 状态存取，不触碰 analyzer 口径层）。"""

    def __init__(self, mw):
        self.mw = mw
        # 从 FilterController 获取预设管理实例
        self.filter_controller = None

    def _get_filter_controller(self):
        """ lazily 获取 filter_controller """
        if not hasattr(self.mw, 'filter_controller') or self.filter_controller is None:
            self.filter_controller = self.mw.filter_controller
        return self.filter_controller

    def _filter_preset_store(self):
        """使用 FilterController 的预设存储 API"""
        fc = self._get_filter_controller()
        if fc:
            return fc.get_preset_store()
        return {}

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
            fc = self._get_filter_controller()
            if fc:
                # 收集当前筛选
                state = self.mw._filters_to_jsonable(self.mw.filter_panel.get_filters())
                if not state:
                    return
                # 创建预设并应用
                preset = fc.create_new_preset_from_dict("___last___", [], preset_id="___last___")
                # 转换为 FilterRule
                rules = fc.create_filters_from_dict(state)
                # 设置使用记录
                preset.rules = rules
                preset.last_used_at = datetime.datetime.now()
                # 保存到 Last Used
                fc._apply_preset_to_last_used(preset)
                # 刷新菜单
                self._refresh_filter_preset_menu()
        except Exception as e:
            toast(f"保存上次使用失败：{e}", level="error", parent=self.mw)

    def _save_filter_preset(self, name):
        """保存当前筛选为预设（使用 FilterController API）"""
        fc = self._get_filter_controller()
        if fc:
            rules = fc.create_filters_from_dict(self.mw.filter_panel.get_filters())
            fc.save_preset(name, rules)
            toast("筛选预设已保存：%s" % name, level="info", parent=self.mw)
            self._refresh_filter_preset_menu()
            return True
        return False

    def _prompt_save_preset(self):
        fc = self._get_filter_controller()
        if fc:
            # 获取现有预设数量
            existing = [k for k in self._filter_preset_store() if k != "___last___"]
            n = len(existing)
            name, ok = QInputDialog.getText(
                self.mw, "保存筛选预设", "预设名称：", text=f"预设 {n + 1}"
            )
            name = (name or "").strip()
            if not ok or not name:
                return
            if name == "___last___":
                QMessageBox.warning(self.mw, "保存筛选预设", "名称「___last___」为系统保留，请换一个。")
                return
            self._save_filter_preset(name)

    def _apply_filter_preset(self, name):
        """应用筛选预设（支持 last 和具体名）"""
        fc = self._get_filter_controller()
        if fc:
            if name == "___last___":
                preset = fc.get_last_used_preset()
            else:
                preset = fc.load_preset(name)
            if preset:
                fc.apply_preset(preset)
                toast(f"已应用预设：{name}", level="info", parent=self.mw)
            else:
                toast(f"没有找到预设：{name}", level="error", parent=self.mw)
        else:
            # 后向兼容：使用旧方法
            store = self._filter_preset_store()
            state = store.get(name)
            if state is None:
                toast(f"暂无{'' if name == '___last___' else '预设「' + name + '」'}记录", level="info", parent=self.mw)
                return
            self.mw.filter_panel.apply_filters(self._jsonable_to_filters(state))
            toast(f"已应用{'' if name == '___last___' else '筛选预设：' + name}", level="info", parent=self.mw)

    def _delete_filter_preset(self, name):
        fc = self._get_filter_controller()
        if fc:
            result = fc.delete_preset(name)
            if result:
                toast(f"已删除预设：{name}", level="info", parent=self.mw)
                self._refresh_filter_preset_menu()
            else:
                toast(f"删除失败：{name}", level="error", parent=self.mw)
        else:
            # 后向兼容
            store = self._filter_preset_store()
            if name in store:
                del store[name]
                self.mw.config_manager.set("filter_history", store)
                self._refresh_filter_preset_menu()
                toast("已删除筛选预设：%s" % name, level="info", parent=self.mw)

    def _refresh_filter_preset_menu(self):
        fc = self._get_filter_controller()
        if fc:
            # 使用 FilterController 的预设管理
            names = [k for k in self._filter_preset_store() if k != "___last___"]
            self.mw.filter_panel.set_preset_names(names, fc.get_last_used_preset() is not None)
        else:
            # 后向兼容
            try:
                names = [k for k in self._filter_preset_store() if k != "___last___"]
                self.mw.filter_panel.set_preset_names(names, "___last___" in self._filter_preset_store())
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
