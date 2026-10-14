# -*- coding: utf-8 -*-
"""
半成品分类控制器（ARC-003 拆分产物，v43.197）

负责：半成品重分类的自定义分类表——加载/保存/增删改/重置/导入导出，以及左侧
面板分类树的刷新与「按分类筛选主表」的选择联动。

模式：组合式。持有 MainWindow 引用（self.mw），方法体从 MainWindow 原样搬迁、
逻辑零改动；MainWindow 侧保留同名薄壳转发，故既有绑定不变：
  - components/left_panel.py:285-289  添加/删除/重置/导入/导出 五个按钮

状态归属：self._semi_categories 仍留在 MainWindow（它在 __init__ 中先于本
controller 装配点初始化，且经 view_model 间接读取），controller 经
self.mw._semi_categories 访问，零行为变化。
"""

import json
import os
import sys

from PySide6.QtCore import Qt, QItemSelection, QItemSelectionModel
from PySide6.QtWidgets import (
    QFileDialog, QMessageBox, QTreeWidgetItem,
)



class SemiCategoryController:
    """半成品分类管理控制器（纯配置与UI 联动，不触碰 analyzer 口径层）。"""

    def __init__(self, mw):
        self.mw = mw

    def _filter_semi_materials(self, category: str):
        """从左侧面板筛选材料半成品：按名称精确匹配"半成品重分类"列"""
        df = self.mw._get_master_df()
        if df is None or df.empty:
            return
        if '半成品重分类' not in df.columns:
            return
        mask = df['半成品重分类'].astype(str) == category
        title = category
        count = int(mask.sum())
        if count == 0:
            QMessageBox.information(self, "提示", f"{title}：无匹配记录")
            return
        rows = [i for i, v in enumerate(mask.values) if v]
        proxy = self.mw.table_view.model()
        src_model = proxy.sourceModel() if hasattr(proxy, "sourceModel") else None
        sel = QItemSelection()
        for i in rows:
            if src_model is not None:
                idx = proxy.mapFromSource(src_model.index(i, 0))
            else:
                idx = proxy.index(i, 0)
            if idx.isValid():
                sel.select(idx, idx)
        if not sel.isEmpty():
            self.mw.table_view.selectionModel().select(
                sel, QItemSelectionModel.Select | QItemSelectionModel.Rows
            )
        self.mw.statusBar().showMessage(f"已筛选 {title}：{count} 条记录")


    def _reset_semi_filter(self):
        """重置半成品筛选：清除主表行选中状态"""
        if not hasattr(self, 'table_view'):
            return
        self.mw.table_view.selectionModel().clearSelection()
        self.mw.statusBar().showMessage("已重置半成品筛选", 2000)


    def _load_semi_categories(self):
        """从 config/semi_user_categories.json 加载物料号→分类映射（dict格式）"""
        candidates = []
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            candidates.append(os.path.join(sys._MEIPASS, 'config', 'semi_user_categories.json'))
        _here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(_here, '..', 'config', 'semi_user_categories.json'))
        _path = next((p for p in candidates if os.path.exists(p)), None)
        if not _path:
            return {}
        try:
            with open(_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k).strip(): str(v).strip() for k, v in data.items() if k and v}
            elif isinstance(data, list):
                # 兼容旧list格式，转为dict
                result = {}
                for item in data:
                    if isinstance(item, dict):
                        name = item.get('name', '')
                        factory = item.get('factory', '')
                        # 用工厂前缀生成示例物料号
                        prefix = '400' if factory == '1101' else ('410' if factory == '1102' else '')
                        result[f"{prefix}999999"] = name
                return result
            return {}
        except Exception:
            return {}


    def _get_semi_category_list(self):
        """从当前数据和映射dict合并提取唯一分类列表（用于UI显示）

        v43.164：每项新增 `codes`（该分类下的物料编码升序列表）与 `code_count`，
        供左侧表格第3/4 列展示。新增键不影响既有 name/factory 语义。
        """
        result = []
        seen = set()

        # 优先从当前数据中提取分类（支持动态推断的"食品成品半成品"/"饮料成品半成品"等）
        df = getattr(self.mw.view_model, 'df', None) if hasattr(self, 'view_model') else None
        if df is not None and '半成品重分类' in df.columns:
            for val in df['半成品重分类'].dropna().astype(str).str.strip().unique():
                if val and val not in seen:
                    # 尝试从工厂列推断工厂
                    factory = ''
                    factory_col = '工厂' if '工厂' in df.columns else None
                    if factory_col and factory_col in df.columns:
                        factory_row = df[df['半成品重分类'] == val][factory_col].iloc[0] if not df[df['半成品重分类'] == val][factory_col].empty else ''
                        if '饮料' in str(factory_row):
                            factory = '1102'
                        elif '食品' in str(factory_row):
                            factory = '1101'
                    # 该分类在本期数据里的物料编码（展示用）
                    sub = df[df['半成品重分类'] == val]
                    code_col = '物料编码' if '物料编码' in df.columns else None
                    codes = sorted(
                        {str(c).strip() for c in sub[code_col].dropna()}
                    ) if code_col else []
                    result.append({'name': val, 'factory': factory,
                                   'codes': codes, 'code_count': len(codes)})
                    seen.add(val)

        # 补充 JSON 中尚未在数据中出现的分类
        mapping = self.mw._semi_categories
        if isinstance(mapping, dict):
            for code, cls in mapping.items():
                if cls and cls not in seen:
                    code_str = str(code).strip()
                    factory = '1101' if code_str.startswith('400') else ('1102' if code_str.startswith('410') else '')
                    result.append({'name': cls, 'factory': factory,
                                   'codes': [code_str], 'code_count': 1})
                    seen.add(cls)
        # 同一分类可能对应多个物料编码（配置兜底路径：逐条加入 seen 时会被吞掉），
        # 故上面 seen.add(cls) 之后需把同分类的其余编码补进来。
        if isinstance(mapping, dict):
            merged = {}
            for code, cls in mapping.items():
                if not cls:
                    continue
                if cls not in merged:
                    merged[cls] = []
                cs = str(code).strip()
                if cs not in merged[cls]:
                    merged[cls].append(cs)
            for item in result:
                codes = sorted(merged.get(item['name'], item.get('codes') or []))
                item['codes'] = codes
                item['code_count'] = len(codes)
        return result


    def _save_semi_categories(self, mapping):
        """将物料号→分类映射写回 config/semi_user_categories.json"""
        _here = os.path.dirname(os.path.abspath(__file__))
        _path = os.path.join(_here, '..', 'config', 'semi_user_categories.json')
        try:
            os.makedirs(os.path.dirname(_path), exist_ok=True)
            with open(_path, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


    def _refresh_semi_list_ui(self):
        """根据当前映射刷新左侧面板半成品列表显示"""
        if not hasattr(self, 'left_panel_component') or not hasattr(self.mw.left_panel_component, 'semi_tree'):
            return
        # 从 dict 映射提取唯一分类列表
        categories = self.mw._get_semi_category_list()
        tree = self.mw.left_panel_component.semi_tree
        # v43.165：默认折叠，只显示 4 个父节点（一屏可览，不引入滚动）。
        # 左栏仅 260px 宽 / 320px 高，全展开 73 行远超可视范围，故不做 expandAll。
        tree.setSortingEnabled(False)
        tree.clear()
        for cat in categories:
            factory = cat.get('factory', '')
            name = cat.get('name', '')
            codes = cat.get('codes') or []
            cnt = int(cat.get('code_count', len(codes)))
            label = f"{factory} · {name}" if factory else name
            parent = QTreeWidgetItem([label, str(cnt)])
            parent.setData(0, Qt.ItemDataRole.UserRole, name)
            for code in codes:
                # 子节点仅展示，第2 列留空；不可选中删除（叶子）
                QTreeWidgetItem(parent, [str(code), ''])
            tree.addTopLevelItem(parent)
        tree.setSortingEnabled(True)
        tree.sortByColumn(0, Qt.AscendingOrder)
        tree.clearSelection()
        if hasattr(self, 'semi_count_label'):
            total_codes = sum(int(c.get('code_count', 0)) for c in categories)
            self.mw.semi_count_label.setText(
                f"共 {len(categories)} 类 · {total_codes} 个物料"
                if total_codes else f"共 {len(categories)} 项")


    def _add_semi_category(self):
        """弹出添加分类对话框：输入名称 + 选择工厂"""
        from PySide6.QtWidgets import (
            QDialog, QDialogButtonBox, QLabel, QLineEdit,
            QComboBox, QVBoxLayout,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("添加半成品分类")
        dlg.setFixedSize(400, 180)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        # 分类名
        name_label = QLabel("分类名称：")
        name_input = QLineEdit()
        name_input.setPlaceholderText("例如：冷链原料半成品")
        layout.addWidget(name_label)
        layout.addWidget(name_input)

        # 工厂
        factory_label = QLabel("工厂：")
        factory_combo = QComboBox()
        factory_combo.addItems(["1101", "1102"])
        layout.addWidget(factory_label)
        layout.addWidget(factory_combo)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return

        cat_name = name_input.text().strip()
        if not cat_name:
            QMessageBox.warning(dlg, "提示", "分类名称不能为空")
            return
        # 检查重复（基于分类名）
        categories = self.mw._get_semi_category_list()
        if any(c['name'] == cat_name for c in categories):
            QMessageBox.warning(dlg, "提示", f"分类「{cat_name}」已存在")
            return

        factory = factory_combo.currentText()
        # 新增分类时，用一个示例物料号占位（实际物料映射需手动编辑JSON）
        prefix = '400' if factory == '1101' else ('410' if factory == '1102' else '')
        self.mw._semi_categories[f"{prefix}999999"] = cat_name
        self.mw._save_semi_categories(self.mw._semi_categories)
        self.mw._refresh_semi_list_ui()
        QMessageBox.information(dlg, "成功", f"已添加分类「{cat_name}」")


    def _delete_semi_category(self):
        """删除选中的半成品分类（v43.165：树形下不能用 currentRow() 当分类索引）"""
        tree = getattr(self.mw.left_panel_component, 'semi_tree', None)
        if tree is None:
            return
        item = tree.currentItem()
        if item is None:
            QMessageBox.warning(self, "提示", "请先选中要删除的分类")
            return
        # 只有父节点（分类级）可删；子节点是单个物料编码
        if item.childCount() == 0:
            QMessageBox.warning(self, "提示",
                                "请选中分类节点（带展开三角的行），物料编码不能单独删除")
            return
        # 从 UserRole 取分类名，不再依赖行号 —— 树形展开后行号会随子节点错位
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if not name:
            QMessageBox.warning(self, "提示", "请先选中要删除的分类")
            return
        # 从映射中删除该分类的所有条目
        self.mw._semi_categories = {k: v for k, v in self.mw._semi_categories.items() if v != name}
        self.mw._save_semi_categories(self.mw._semi_categories)
        self.mw._refresh_semi_list_ui()
        QMessageBox.information(self, "成功", f"已删除分类「{name}」")


    def _reset_semi_categories(self):
        """重置半成品分类为默认值"""
        if not QMessageBox.question(self, "确认", "确定要重置所有半成品分类吗？",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
            return
        self.mw._semi_categories = {}
        self.mw._save_semi_categories(self.mw._semi_categories)
        self.mw._refresh_semi_list_ui()
        QMessageBox.information(self, "成功", "已重置所有半成品分类")


    def _import_semi_categories(self):
        """从 JSON 文件导入半成品分类"""
        file_path, _ = QFileDialog.getOpenFileName(self, "导入半成品分类", "", "JSON files (*.json)")
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 兼容两种格式：dict {"物料号": "分类名"} 或 list [{"name": "...", "factory": "..."}]
            imported = {}
            if isinstance(data, dict):
                imported = {str(k).strip(): str(v).strip() for k, v in data.items() if k and v}
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get('name', '')
                        factory = item.get('factory', '')
                        if name:
                            prefix = '400' if factory == '1101' else ('410' if factory == '1102' else '')
                            imported[f"{prefix}999999"] = name
            # 合并
            self.mw._semi_categories.update(imported)
            self.mw._save_semi_categories(self.mw._semi_categories)
            self.mw._refresh_semi_list_ui()
            QMessageBox.information(self, "成功", f"已导入 {len(imported)} 个分类")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {e}")


    def _export_semi_categories(self):
        """导出半成品分类到 JSON 文件"""
        file_path, _ = QFileDialog.getSaveFileName(self, "导出半成品分类", "semi_categories.json", "JSON (*.json)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.mw._semi_categories, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", f"已导出到 {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")
