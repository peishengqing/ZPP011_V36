# -*- coding: utf-8 -*-
"""
替代料配对控制器
负责：配对的增删改查、导入导出、排序、放大窗口数据管理、持久化
"""

import json
import traceback
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QDialogButtonBox, QMessageBox, QTableWidget,
    QTableWidgetItem, QMenu, QPushButton, QLabel
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from domain.alt_material.alt_manager import load_alt_pairs, save_alt_pairs, DEFAULT_ALT_PAIRS
from gui_pyside6.dialogs.import_wizard_dialog import ImportWizard


class AltController(QObject):
    """替代料配对业务控制器"""

    # 信号：数据变化时通知界面刷新
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.alt_pairs = load_alt_pairs()   # 内存中的配对列表

    # ------------------- 数据读取 -------------------
    def get_pairs(self):
        """获取当前配对列表"""
        return self.alt_pairs

    # ------------------- 增删改查 -------------------
    def add_pair(self, a, b, parent_widget=None):
        """添加一对替代料，返回是否成功"""
        for existing in self.alt_pairs:
            if (existing[0][0] == a[0] and existing[0][1] == a[1]
                    and existing[1][1] == b[1]):
                if parent_widget:
                    QMessageBox.warning(parent_widget, "提示", "该替代料配对已存在，请勿重复添加")
                return False
        self.alt_pairs.append((a, b))
        save_alt_pairs(self.alt_pairs)
        self.data_changed.emit()
        return True

    def delete_pair(self, index):
        """根据索引删除配对"""
        if 0 <= index < len(self.alt_pairs):
            del self.alt_pairs[index]
            save_alt_pairs(self.alt_pairs)
            self.data_changed.emit()
            return True
        return False

    def reset_pairs(self):
        """重置为默认配对"""
        self.alt_pairs = list(DEFAULT_ALT_PAIRS)
        save_alt_pairs(self.alt_pairs)
        self.data_changed.emit()

    def sort_pairs(self):
        """按物料A编码升序排序"""
        if not self.alt_pairs:
            return
        def get_code(pair):
            a = pair[0]
            if isinstance(a, (list, tuple)) and len(a) > 1:
                return str(a[1])
            else:
                return str(a)
        self.alt_pairs.sort(key=get_code)
        save_alt_pairs(self.alt_pairs)
        self.data_changed.emit()

    def set_pairs_from_list(self, new_pairs):
        """直接设置配对列表（用于拖拽排序/导入）"""
        self.alt_pairs = list(new_pairs)
        save_alt_pairs(self.alt_pairs)
        self.data_changed.emit()

    # ------------------- 导入导出 -------------------
    def import_from_file(self, file_path, parent_widget=None):
        """从JSON或Excel导入替代料配对"""
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported = json.load(f)
                if isinstance(imported, list):
                    self.set_pairs_from_list(imported)
                    if parent_widget:
                        QMessageBox.information(parent_widget, "成功", f"已导入 {len(imported)} 对")
                    return True
                else:
                    if parent_widget:
                        QMessageBox.warning(parent_widget, "格式错误", "JSON 文件应为列表格式")
                    return False
            else:
                # Excel 导入使用 ImportWizard，由主窗口处理
                return False
        except Exception as e:
            traceback.print_exc()
            if parent_widget:
                QMessageBox.critical(parent_widget, "错误", f"导入失败: {e}")
            return False

    def export_to_file(self, file_path):
        """导出为JSON"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.alt_pairs, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            traceback.print_exc()
            return False

    # ------------------- 辅助方法（供界面使用） -------------------
    def format_material_short(self, material):
        """返回 (显示文本, 工具提示)"""
        if isinstance(material, (list, tuple)):
            factory = material[0] if len(material) > 0 else ''
            code = material[1] if len(material) > 1 else ''
            name = material[2] if len(material) > 2 else ''
        else:
            factory = ''
            code = str(material)
            name = ''
        display = f"{code}|{name}" if code else name
        tooltip = f"工厂: {factory}\n编码: {code}\n名称: {name}" if factory else f"编码: {code}\n名称: {name}"
        return display, tooltip

    # ------------------- 交互对话框（添加配对） -------------------
    def show_add_dialog(self, parent_widget):
        """弹出添加配对的对话框，成功则返回True"""
        dialog = QDialog(parent_widget)
        dialog.setWindowTitle("添加替代料配对")
        layout = QVBoxLayout(dialog)

        a_group = QGroupBox("物料A")
        a_form = QFormLayout(a_group)
        a_factory = QLineEdit()
        a_code = QLineEdit()
        a_name = QLineEdit()
        a_form.addRow("工厂:", a_factory)
        a_form.addRow("编码:", a_code)
        a_form.addRow("名称:", a_name)
        layout.addWidget(a_group)

        b_group = QGroupBox("物料B")
        b_form = QFormLayout(b_group)
        b_factory = QLineEdit()
        b_code = QLineEdit()
        b_name = QLineEdit()
        b_form.addRow("工厂:", b_factory)
        b_form.addRow("编码:", b_code)
        b_form.addRow("名称:", b_name)
        layout.addWidget(b_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            # 清空首尾空白（半角/全角/制表符等）：复制粘贴时易带入尾空格
            a = (a_factory.text().strip(), a_code.text().strip(), a_name.text().strip())
            b = (b_factory.text().strip(), b_code.text().strip(), b_name.text().strip())
            return self.add_pair(a, b, parent_widget)
        return False

    # ------------------- 交互对话框（从主表选中行智能添加） -------------------
    def show_add_from_rows_dialog(self, parent_widget, a, b):
        """从主表选中 2 行智能添加：自动提取 (工厂, 编码, 名称) 后预览核对。

        a / b 已为 (工厂, 编码, 名称) 三元组；弹窗只读展示，支持交换 A/B，
        点「添加」才调用 add_pair 写库（重复时 add_pair 内部告警并保持打开）。
        返回是否成功添加。
        """
        dlg = QDialog(parent_widget)
        dlg.setWindowTitle("从选中行添加替代料配对")
        dlg.setMinimumWidth(440)
        outer = QVBoxLayout(dlg)

        tip = QLabel("已自动提取主表选中行的物料信息，请核对后添加到替代料配对。")
        tip.setStyleSheet("color:#888; font-size:11px;")
        outer.addWidget(tip)

        state = {'a': a, 'b': b}

        def make_group(title):
            g = QGroupBox(title)
            fl = QFormLayout(g)
            fac = QLabel(); cod = QLabel(); nam = QLabel()
            fac.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cod.setTextInteractionFlags(Qt.TextSelectableByMouse)
            nam.setTextInteractionFlags(Qt.TextSelectableByMouse)
            fl.addRow("工厂:", fac)
            fl.addRow("编码:", cod)
            fl.addRow("名称:", nam)
            return g, (fac, cod, nam)

        a_group, a_lbls = make_group("物料A")
        arrow = QLabel("↔")
        arrow.setAlignment(Qt.AlignCenter)
        b_group, b_lbls = make_group("物料B")

        def refresh():
            for lbl, val in zip(a_lbls, state['a']):
                lbl.setText((val or "").strip() or "（空）")
            for lbl, val in zip(b_lbls, state['b']):
                lbl.setText((val or "").strip() or "（空）")

        row = QHBoxLayout()
        row.addWidget(a_group)
        row.addWidget(arrow)
        row.addWidget(b_group)
        outer.addLayout(row)

        btns = QHBoxLayout()
        swap_btn = QPushButton("⇄ 交换 A/B")
        add_btn = QPushButton("添加")
        add_btn.setDefault(True)
        cancel_btn = QPushButton("取消")
        btns.addWidget(swap_btn)
        btns.addStretch()
        btns.addWidget(add_btn)
        btns.addWidget(cancel_btn)
        outer.addLayout(btns)

        refresh()

        result = {'added': False}

        def do_swap():
            state['a'], state['b'] = state['b'], state['a']
            refresh()

        def do_add():
            ok = self.add_pair(state['a'], state['b'], parent_widget)
            if ok:
                result['added'] = True
                dlg.accept()
            # 重复时 add_pair 已弹警告，保持对话框打开

        swap_btn.clicked.connect(do_swap)
        add_btn.clicked.connect(do_add)
        cancel_btn.clicked.connect(dlg.reject)

        dlg.exec()
        return result['added']

    # ------------------- 交互对话框（修改配对） -------------------
    def show_edit_dialog(self, parent_widget, old_a, old_b):
        """弹出修改配对的对话框，预填 old_a/old_b，成功返回 (a, b)，取消返回 None"""
        dialog = QDialog(parent_widget)
        dialog.setWindowTitle("修改替代料配对")
        layout = QVBoxLayout(dialog)

        a_group = QGroupBox("物料A")
        a_form = QFormLayout(a_group)
        a_factory = QLineEdit(old_a[0] if len(old_a) > 0 else '')
        a_code = QLineEdit(old_a[1] if len(old_a) > 1 else '')
        a_name = QLineEdit(old_a[2] if len(old_a) > 2 else '')
        a_form.addRow("工厂:", a_factory)
        a_form.addRow("编码:", a_code)
        a_form.addRow("名称:", a_name)
        layout.addWidget(a_group)

        b_group = QGroupBox("物料B")
        b_form = QFormLayout(b_group)
        b_factory = QLineEdit(old_b[0] if len(old_b) > 0 else '')
        b_code = QLineEdit(old_b[1] if len(old_b) > 1 else '')
        b_name = QLineEdit(old_b[2] if len(old_b) > 2 else '')
        b_form.addRow("工厂:", b_factory)
        b_form.addRow("编码:", b_code)
        b_form.addRow("名称:", b_name)
        layout.addWidget(b_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            # 同样清空首尾空白
            a = (a_factory.text().strip(), a_code.text().strip(), a_name.text().strip())
            b = (b_factory.text().strip(), b_code.text().strip(), b_name.text().strip())
            return a, b
        return None

    # ------------------- 放大窗口 -------------------
    def show_zoom_window(self, parent_widget, refresh_alt_view_callback=None):
        """显示放大窗口，支持右键删除"""
        # 保存主窗口状态，防止对话框打开/关闭后窗口位置或滚动条异常
        saved_geo = parent_widget.saveGeometry() if parent_widget else None
        
        dialog = QDialog(parent_widget)
        dialog.setWindowTitle("替代料配对详情")
        dialog.resize(900, 600)
        layout = QVBoxLayout(dialog)

        # ---- 查找栏：按物料号（A/B 编码）查找配对 ----
        search_row = QHBoxLayout()
        search_lbl = QLabel("查找:")
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("输入物料号查找（匹配 A/B 编码）")
        find_btn = QPushButton("查找")
        next_btn = QPushButton("下一个")
        clear_btn = QPushButton("清除")
        search_row.addWidget(search_lbl)
        search_row.addWidget(search_edit, 1)
        search_row.addWidget(find_btn)
        search_row.addWidget(next_btn)
        search_row.addWidget(clear_btn)

        match_rows = []
        match_idx = [0]
        sort_state = {'col': None, 'asc': True}
        status_label = QLabel("")
        status_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px 4px;")

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["物料A", "", "物料B"])
        table.horizontalHeader().setStretchLastSection(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        # 关闭排序：放大窗口按工厂分组显示，标题行参与排序会错位
        table.setSortingEnabled(False)
        # 确保缩放窗口有滚动条
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # 刷新表格内容：按工厂分组，每组一个标题行 + 该工厂配对
        def refresh_zoom_table():
            table.setRowCount(0)
            groups = {}
            order = []
            for idx, (a, b) in enumerate(self.alt_pairs):
                factory = a[0] if isinstance(a, (list, tuple)) and len(a) > 0 else ''
                if factory not in groups:
                    groups[factory] = []
                    order.append(factory)
                groups[factory].append((idx, a, b))
            for factory in order:
                items = groups[factory]
                # 组内排序：只对该工厂段内的配对行排序，标题行固定不参与
                sc = sort_state['col']
                if sc is not None:
                    def _skey(t, _sc=sc):
                        _, a, b = t
                        if _sc == 0:
                            v = a[1] if isinstance(a, (list, tuple)) and len(a) > 1 else ''
                        else:
                            v = b[1] if isinstance(b, (list, tuple)) and len(b) > 1 else ''
                        s = str(v).strip()
                        try:
                            return (0, int(s), '')
                        except (ValueError, TypeError):
                            return (1, 0, s.lower())
                    items = sorted(items, key=_skey, reverse=not sort_state['asc'])
                # 分组标题行（跨 3 列，UserRole=-1 标记为标题）
                r = table.rowCount()
                table.insertRow(r)
                title = QTableWidgetItem("工厂 %s（%d 对）" % (factory or "未知", len(items)))
                title.setFlags(Qt.NoItemFlags)
                title.setData(Qt.UserRole, -1)
                title.setBackground(QColor(70, 70, 72))
                title.setForeground(QColor(255, 255, 255))
                table.setItem(r, 0, title)
                table.setSpan(r, 0, 1, 3)
                for idx, a, b in items:
                    a_display, a_tip = self.format_material_short(a)
                    b_display, b_tip = self.format_material_short(b)
                    row = table.rowCount()
                    table.insertRow(row)
                    item_a = QTableWidgetItem(a_display)
                    item_a.setToolTip(a_tip)
                    item_a.setData(Qt.UserRole, idx)
                    table.setItem(row, 0, item_a)
                    arrow_item = QTableWidgetItem(" ↔ ")
                    arrow_item.setFlags(Qt.NoItemFlags)
                    table.setItem(row, 1, arrow_item)
                    item_b = QTableWidgetItem(b_display)
                    item_b.setToolTip(b_tip)
                    item_b.setData(Qt.UserRole, idx)
                    table.setItem(row, 2, item_b)
            table.resizeColumnsToContents()
            table.setColumnWidth(0, max(80, table.columnWidth(0)))
            table.setColumnWidth(2, max(80, table.columnWidth(2)))

        refresh_zoom_table()

        # ---- 组内排序：点列头（物料A/物料B）按编码排序，标题行固定 ----
        def on_header_clicked(col):
            if col not in (0, 2):
                return
            if sort_state['col'] == col:
                sort_state['asc'] = not sort_state['asc']
            else:
                sort_state['col'] = col
                sort_state['asc'] = True
            table.horizontalHeader().setSortIndicatorShown(True)
            table.horizontalHeader().setSortIndicator(
                col, Qt.AscendingOrder if sort_state['asc'] else Qt.DescendingOrder)
            refresh_zoom_table()

        table.horizontalHeader().setSectionsClickable(True)
        table.horizontalHeader().sectionClicked.connect(on_header_clicked)

        # ---- 查找逻辑：按物料号（编码）在 A/B 两列中匹配 ----
        def _norm(s):
            return str(s if s is not None else '').strip().lower()

        def _clear_highlight():
            for r in range(table.rowCount()):
                for c in range(3):
                    it = table.item(r, c)
                    if it:
                        if it.data(Qt.UserRole) == -1:
                            continue  # 标题行背景保持不变
                        it.setBackground(Qt.transparent)

        def do_search():
            text = _norm(search_edit.text())
            _clear_highlight()
            match_rows.clear()
            if not text:
                status_label.setText("")
                return
            for r in range(table.rowCount()):
                a_item = table.item(r, 0)
                if not a_item:
                    continue
                orig = a_item.data(Qt.UserRole)
                if orig is None or orig < 0 or orig >= len(self.alt_pairs):
                    continue
                a, b = self.alt_pairs[orig]
                code_a = a[1] if isinstance(a, (list, tuple)) and len(a) > 1 else ''
                code_b = b[1] if isinstance(b, (list, tuple)) and len(b) > 1 else ''
                if text in _norm(code_a) or text in _norm(code_b):
                    match_rows.append(r)
                    for c in range(3):
                        it = table.item(r, c)
                        if it:
                            it.setBackground(QColor(255, 235, 130))
            if match_rows:
                match_idx[0] = 0
                _select_match()
            else:
                status_label.setText("未找到匹配的配对")

        def _select_match():
            r = match_rows[match_idx[0]]
            table.selectRow(r)
            table.scrollToItem(table.item(r, 0))
            status_label.setText("匹配 %d/%d 条" % (match_idx[0] + 1, len(match_rows)))

        def goto_next():
            if not match_rows:
                return
            match_idx[0] = (match_idx[0] + 1) % len(match_rows)
            _select_match()

        def clear_search():
            search_edit.clear()
            match_rows.clear()
            match_idx[0] = 0
            _clear_highlight()
            status_label.setText("")

        find_btn.clicked.connect(do_search)
        next_btn.clicked.connect(goto_next)
        clear_btn.clicked.connect(clear_search)
        search_edit.returnPressed.connect(do_search)

        def on_context_menu(pos):
            item = table.itemAt(pos)
            if not item:
                return
            row = item.row()
            idx_item = table.item(row, 0)
            if not idx_item:
                return
            pair_idx = idx_item.data(Qt.UserRole)
            if pair_idx is None or pair_idx < 0 or pair_idx >= len(self.alt_pairs):
                return
            menu = QMenu()
            edit_action = menu.addAction("修改此配对")
            edit_action.triggered.connect(
                lambda: self._edit_from_zoom(pair_idx, refresh_zoom_table, parent_widget)
            )
            menu.addSeparator()
            delete_action = menu.addAction("删除此配对")
            delete_action.triggered.connect(
                lambda: self._delete_from_zoom(pair_idx, refresh_zoom_table, parent_widget)
            )
            menu.exec_(table.viewport().mapToGlobal(pos))

        table.customContextMenuRequested.connect(on_context_menu)
        layout.addLayout(search_row)
        layout.addWidget(table)
        layout.addWidget(status_label)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()
        
        # 恢复主窗口状态（解决对话框关闭后窗口位置错乱的问题）
        if saved_geo:
            parent_widget.restoreGeometry(saved_geo)

    def _delete_from_zoom(self, pair_idx, refresh_callback, parent_widget):
        """从放大窗口删除配对"""
        if 0 <= pair_idx < len(self.alt_pairs):
            del self.alt_pairs[pair_idx]
            save_alt_pairs(self.alt_pairs)
            refresh_callback()
            self.data_changed.emit()
            QMessageBox.information(parent_widget, "删除成功", "已删除该替代料配对")

    def _edit_from_zoom(self, pair_idx, refresh_callback, parent_widget):
        """从放大窗口修改配对"""
        if 0 <= pair_idx < len(self.alt_pairs):
            old_a, old_b = self.alt_pairs[pair_idx]
            result = self.show_edit_dialog(parent_widget, old_a, old_b)
            if result is None:
                return
            new_a, new_b = result
            self.alt_pairs[pair_idx] = (new_a, new_b)
            save_alt_pairs(self.alt_pairs)
            refresh_callback()
            self.data_changed.emit()
            QMessageBox.information(parent_widget, "修改成功", "已更新该替代料配对")
