# -*- coding: utf-8 -*-
"""
可视化规则配置对话框 (PySide6 版本)
完全迁移自 tkinter 版本，保留所有功能：
- 规则列表（增删改查、上下移动）
- 条件构造器（多条件 AND/OR，动态增减）
- 动作配置（set_color, set_remark, set_status）
- 测试面板（模拟数据，实时评估）
- 原子保存 + 备份
"""

import os
import json
import uuid
import shutil
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QListWidget, QListWidgetItem,
    QWidget, QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton, QTextEdit,
    QSpinBox, QDoubleSpinBox, QGroupBox, QMessageBox, QFileDialog, QColorDialog,
    QScrollArea, QFrame, QSizePolicy, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QPalette, QFont

import pandas as pd
from core.rule_engine import safe_eval_condition, ALLOWED_FIELDS, OP_MAP

# ========== 字段显示映射 ==========
FIELD_DISPLAY = {
    'dev_rate': '偏差率(%)',
    'deviation_amount': '偏差金额(元)',
    'remark': '备注内容',
    'remark_status': '备注状态',
    'is_alt': '是否替代料'
}
# 反向映射
DISPLAY_TO_FIELD = {v: k for k, v in FIELD_DISPLAY.items()}

# ========== 原子保存函数 ==========
def atomic_save_json(data, file_path):
    """原子保存 JSON 数据到文件"""
    try:
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        raise ValueError(f"数据无法序列化: {e}")
    dir_name = os.path.dirname(file_path) or '.'
    fd, tmp_path = tempfile.mkstemp(suffix='.json', dir=dir_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json_str)
    except Exception as e:
        os.close(fd)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise IOError(f"写入临时文件失败: {e}")
    backup_path = file_path + ".backup"
    has_backup = False
    if os.path.exists(file_path):
        shutil.copy2(file_path, backup_path)
        has_backup = True
    try:
        os.replace(tmp_path, file_path)
    except Exception as e:
        if has_backup and os.path.exists(backup_path):
            shutil.copy2(backup_path, file_path)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise IOError(f"原子替换失败: {e}")
    if has_backup and os.path.exists(backup_path):
        os.remove(backup_path)


def _clear_layout(layout):
    """安全清除 layout 中所有控件"""
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
        sub_layout = item.layout()
        if sub_layout:
            _clear_layout(sub_layout)


class ConditionRowWidget(QWidget):
    """单行条件控件（字段、运算符、值）"""
    def __init__(self, parent=None, default_cond=None, on_delete=None):
        super().__init__(parent)
        self.on_delete = on_delete
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 字段下拉框（显示中文，内部存英文）
        self.field_combo = QComboBox()
        for field, display in FIELD_DISPLAY.items():
            self.field_combo.addItem(display, field)
        layout.addWidget(self.field_combo)

        # 运算符下拉框
        self.op_combo = QComboBox()
        for op in OP_MAP.keys():
            self.op_combo.addItem(op)
        layout.addWidget(self.op_combo)

        # 值输入控件（动态变化）
        self.value_container = QWidget()
        self.value_layout = QHBoxLayout(self.value_container)
        self.value_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.value_container)

        # 删除按钮
        del_btn = QPushButton("❌")
        del_btn.setFixedSize(24, 24)
        del_btn.clicked.connect(self._on_delete)
        layout.addWidget(del_btn)

        # 存储条件数据
        self.field = default_cond.get('field', 'dev_rate') if default_cond else 'dev_rate'
        self.op = default_cond.get('op', '>=') if default_cond else '>='
        self.value = default_cond.get('value', '') if default_cond else ''

        # 设置当前值
        idx = self.field_combo.findData(self.field)
        if idx >= 0:
            self.field_combo.setCurrentIndex(idx)
        self.op_combo.setCurrentText(self.op)
        self._update_value_widget()
        # 连接信号
        self.field_combo.currentIndexChanged.connect(self._on_field_changed)
        self.op_combo.currentTextChanged.connect(self._on_op_changed)

    def _on_field_changed(self):
        self.field = self.field_combo.currentData()
        self._update_value_widget()

    def _on_op_changed(self, text):
        self.op = text
        self._update_value_widget()

    def _update_value_widget(self):
        # 清空旧控件
        _clear_layout(self.value_layout)
        op = self.op
        field = self.field
        if op == 'empty':
            # 无需值输入，显示只读标签
            label = QLabel("(无需值)")
            label.setStyleSheet("color: gray;")
            self.value_layout.addWidget(label)
            self.value = ''
        else:
            # 根据字段类型选择输入控件
            if field in ('dev_rate', 'deviation_amount'):
                spin = QDoubleSpinBox()
                spin.setRange(-1000000, 1000000)
                spin.setDecimals(2)
                try:
                    spin.setValue(float(self.value) if self.value else 0)
                except (ValueError, TypeError):
                    spin.setValue(0)
                spin.valueChanged.connect(lambda v: setattr(self, 'value', v))
                self.value_layout.addWidget(spin)
            else:
                line = QLineEdit()
                line.setText(str(self.value))
                line.textChanged.connect(lambda v: setattr(self, 'value', v))
                self.value_layout.addWidget(line)

    def _on_delete(self):
        if self.on_delete:
            self.on_delete(self)

    def get_condition(self):
        """返回条件字典"""
        if self.op == 'empty':
            return {'field': self.field, 'op': self.op, 'value': ''}
        if hasattr(self, 'value_container'):
            # 从 value_container 取控件
            for i in range(self.value_container.layout().count()):
                w = self.value_container.layout().itemAt(i).widget()
                if isinstance(w, QDoubleSpinBox):
                    self.value = w.value()
                    break
                elif isinstance(w, QLineEdit):
                    self.value = w.text()
                    break
        return {'field': self.field, 'op': self.op, 'value': self.value}


class RuleConfigDialog(QDialog):
    """规则配置对话框"""
    def __init__(self, parent, rules_path, on_rules_changed_callback=None):
        super().__init__(parent)
        self.setWindowTitle("可视化规则配置")
        self.resize(1000, 750)
        self.setMinimumSize(800, 600)

        self.rules_path = rules_path
        self.on_rules_changed = on_rules_changed_callback
        self.rules = self._load_rules()
        self.current_index = None
        self.unsaved = False

        self._build_ui()
        self._refresh_rule_list()
        self._clear_edit_area()

    def _load_rules(self):
        if os.path.exists(self.rules_path):
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('rules', [])
        return []

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # 左侧：规则列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.rule_list = QListWidget()
        self.rule_list.itemClicked.connect(self._on_rule_selected)
        left_layout.addWidget(self.rule_list)
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ 新增")
        self.add_btn.clicked.connect(self._add_rule)
        self.del_btn = QPushButton("🗑 删除")
        self.del_btn.clicked.connect(self._delete_rule)
        self.up_btn = QPushButton("⬆ 上移")
        self.up_btn.clicked.connect(self._move_rule_up)
        self.down_btn = QPushButton("⬇ 下移")
        self.down_btn.clicked.connect(self._move_rule_down)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)
        left_layout.addLayout(btn_layout)
        main_layout.addWidget(left_widget, 1)

        # 右侧：编辑区
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 规则名称与启用
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("规则名称:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        self.enabled_cb = QCheckBox("启用")
        self.enabled_cb.setChecked(True)
        name_layout.addWidget(self.enabled_cb)
        name_layout.addStretch()
        right_layout.addLayout(name_layout)

        # 条件构造器（可滚动）
        cond_group = QGroupBox("条件")
        cond_layout = QVBoxLayout(cond_group)
        self.cond_scroll = QScrollArea()
        self.cond_scroll.setWidgetResizable(True)
        self.cond_container = QWidget()
        self.cond_container_layout = QVBoxLayout(self.cond_container)
        self.cond_scroll.setWidget(self.cond_container)
        cond_layout.addWidget(self.cond_scroll)
        # 组合方式
        combine_layout = QHBoxLayout()
        combine_layout.addWidget(QLabel("条件组合方式:"))
        self.combine_and = QCheckBox("并且 (AND)")
        self.combine_or = QCheckBox("或者 (OR)")
        self.combine_and.setChecked(True)
        self.combine_and.toggled.connect(lambda: self.combine_or.setChecked(not self.combine_and.isChecked()))
        self.combine_or.toggled.connect(lambda: self.combine_and.setChecked(not self.combine_or.isChecked()))
        combine_layout.addWidget(self.combine_and)
        combine_layout.addWidget(self.combine_or)
        combine_layout.addStretch()
        cond_layout.addLayout(combine_layout)
        # 添加条件按钮
        add_cond_btn = QPushButton("➕ 添加条件")
        add_cond_btn.clicked.connect(self._add_condition_row)
        cond_layout.addWidget(add_cond_btn)
        right_layout.addWidget(cond_group)

        # 动作配置
        action_group = QGroupBox("动作")
        action_layout = QGridLayout(action_group)
        action_layout.addWidget(QLabel("动作类型:"), 0, 0)
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems(["set_color", "set_remark", "set_status"])
        self.action_type_combo.currentTextChanged.connect(self._on_action_type_changed)
        action_layout.addWidget(self.action_type_combo, 0, 1)
        self.action_param_widget = QWidget()
        self.action_param_layout = QVBoxLayout(self.action_param_widget)
        action_layout.addWidget(self.action_param_widget, 1, 0, 1, 2)
        right_layout.addWidget(action_group)

        # 测试面板
        test_group = QGroupBox("测试规则")
        test_layout = QGridLayout(test_group)
        self.test_inputs = {}
        row = 0
        for field, display in FIELD_DISPLAY.items():
            test_layout.addWidget(QLabel(display + ":"), row, 0)
            if field in ('dev_rate', 'deviation_amount'):
                widget = QDoubleSpinBox()
                widget.setRange(-1000000, 1000000)
                widget.setDecimals(2)
            elif field == 'is_alt':
                widget = QCheckBox()
            else:
                widget = QLineEdit()
            test_layout.addWidget(widget, row, 1)
            self.test_inputs[field] = widget
            row += 1
        test_btn = QPushButton("▶ 测试当前规则")
        test_btn.clicked.connect(self._test_rule)
        test_layout.addWidget(test_btn, row, 0, 1, 2)
        self.test_result_label = QLabel("")
        test_layout.addWidget(self.test_result_label, row+1, 0, 1, 2)
        right_layout.addWidget(test_group)

        # 底部按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_rules)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        right_layout.addLayout(btn_layout)

        main_layout.addWidget(right_widget, 2)

        # 存储条件行
        self.cond_rows = []

    def _refresh_rule_list(self):
        self.rule_list.clear()
        for i, rule in enumerate(self.rules):
            name = rule.get('name', f'规则{i+1}')
            enabled = rule.get('enabled', True)
            display = f"{'✓' if enabled else '✗'} {name}"
            self.rule_list.addItem(display)

    def _on_rule_selected(self, item):
        idx = self.rule_list.row(item)
        if idx == self.current_index:
            return
        if self.unsaved:
            reply = QMessageBox.question(self, "未保存更改", "当前规则未保存，是否放弃更改并切换？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                if self.current_index is not None:
                    self.rule_list.setCurrentRow(self.current_index)
                return
        self.current_index = idx
        rule = self.rules[idx]
        self._load_rule_to_ui(rule)

    def _load_rule_to_ui(self, rule):
        self.name_edit.setText(rule.get('name', ''))
        self.enabled_cb.setChecked(rule.get('enabled', True))

        cond = rule.get('condition')
        # 清空现有条件行
        for row in self.cond_rows:
            row.deleteLater()
        self.cond_rows.clear()
        _clear_layout(self.cond_container_layout)

        if isinstance(cond, dict) and 'operator' in cond:
            # 结构化条件
            if cond.get('operator') == 'and':
                self.combine_and.setChecked(True)
            else:
                self.combine_or.setChecked(True)
            for sub_cond in cond.get('conditions', []):
                self._add_condition_row(sub_cond)
        elif isinstance(cond, dict):
            # 单条件
            self.combine_and.setChecked(True)
            self._add_condition_row(cond)
        else:
            # 字符串表达式，显示只读提示
            expr_label = QLabel(f"原始表达式（只读）: {cond}")
            self.cond_container_layout.addWidget(expr_label)
            self.cond_rows.append(expr_label)
            QMessageBox.information(self, "提示", "当前规则为字符串表达式，无法完全可视化，建议重新配置。")

        # 动作
        action_type = rule.get('action', 'set_color')
        idx = self.action_type_combo.findText(action_type)
        if idx >= 0:
            self.action_type_combo.setCurrentIndex(idx)
        self._on_action_type_changed(action_type)
        if action_type == 'set_color':
            color = rule.get('color', '#ffcccc')
            edit = self.action_param_widget.findChild(QLineEdit)
            if edit:
                edit.setText(color)
        elif action_type == 'set_remark':
            text = rule.get('remark_text', '')
            edit = self.action_param_widget.findChild(QLineEdit)
            if edit:
                edit.setText(text)
        elif action_type == 'set_status':
            status = rule.get('status', '需补备注')
            combo = self.action_param_widget.findChild(QComboBox)
            if combo:
                combo.setCurrentText(status)
        self.unsaved = False

    def _add_condition_row(self, default_cond=None):
        row = ConditionRowWidget(self.cond_container, default_cond, self._remove_condition_row)
        self.cond_container_layout.addWidget(row)
        self.cond_rows.append(row)

    def _remove_condition_row(self, row):
        row.deleteLater()
        if row in self.cond_rows:
            self.cond_rows.remove(row)

    def _on_action_type_changed(self, action_type):
        # 安全清除旧布局中的控件
        _clear_layout(self.action_param_layout)
        if isinstance(action_type, str):
            at = action_type
        else:
            at = self.action_type_combo.currentText()
        if at == 'set_color':
            self.action_param_layout.addWidget(QLabel("背景色:"))
            color_edit = QLineEdit("#ffcccc")
            self.action_param_layout.addWidget(color_edit)
            pick_btn = QPushButton("选择颜色")
            pick_btn.clicked.connect(lambda: self._pick_color(color_edit))
            self.action_param_layout.addWidget(pick_btn)
        elif at == 'set_remark':
            self.action_param_layout.addWidget(QLabel("备注内容:"))
            remark_edit = QLineEdit()
            self.action_param_layout.addWidget(remark_edit)
        elif at == 'set_status':
            self.action_param_layout.addWidget(QLabel("状态:"))
            status_combo = QComboBox()
            status_combo.addItems(["已备注", "需补备注", "已审核", "未审核"])
            self.action_param_layout.addWidget(status_combo)
        self.action_param_layout.addStretch()

    def _pick_color(self, line_edit):
        color = QColorDialog.getColor()
        if color.isValid():
            line_edit.setText(color.name())

    def _get_current_condition_dict(self):
        if not self.cond_rows:
            return {}
        conditions = []
        for row in self.cond_rows:
            if isinstance(row, ConditionRowWidget):
                conditions.append(row.get_condition())
        if len(conditions) == 0:
            return {}
        if len(conditions) == 1:
            return conditions[0]
        operator = 'and' if self.combine_and.isChecked() else 'or'
        return {'operator': operator, 'conditions': conditions}

    def _get_current_action_dict(self):
        action_type = self.action_type_combo.currentText()
        action_dict = {'action': action_type}
        if action_type == 'set_color':
            color_edit = self.action_param_widget.findChild(QLineEdit)
            if color_edit:
                action_dict['color'] = color_edit.text()
        elif action_type == 'set_remark':
            remark_edit = self.action_param_widget.findChild(QLineEdit)
            if remark_edit:
                action_dict['remark_text'] = remark_edit.text()
        elif action_type == 'set_status':
            combo = self.action_param_widget.findChild(QComboBox)
            if combo:
                action_dict['status'] = combo.currentText()
        return action_dict

    def _test_rule(self):
        # 收集测试数据
        row_data = {}
        for field, widget in self.test_inputs.items():
            if isinstance(widget, QDoubleSpinBox):
                row_data[field] = widget.value()
            elif isinstance(widget, QCheckBox):
                row_data[field] = widget.isChecked()
            else:
                row_data[field] = widget.text()
        cond_dict = self._get_current_condition_dict()
        if not cond_dict:
            self.test_result_label.setText("⚠️ 规则无条件，永不匹配")
            self.test_result_label.setStyleSheet("color: orange;")
            return
        try:
            matched = safe_eval_condition(cond_dict, row_data)
            if matched:
                action = self._get_current_action_dict()
                action_desc = self._format_action(action)
                self.test_result_label.setText(f"✅ 匹配成功！将执行：{action_desc}")
                self.test_result_label.setStyleSheet("color: green;")
            else:
                self.test_result_label.setText("❌ 不匹配")
                self.test_result_label.setStyleSheet("color: red;")
        except Exception as e:
            self.test_result_label.setText(f"⚠️ 测试出错: {e}")
            self.test_result_label.setStyleSheet("color: orange;")

    def _format_action(self, action_dict):
        action_type = action_dict.get('action')
        if action_type == 'set_color':
            color = action_dict.get('color', '#ffcccc')
            return f"设置背景色为 {color}"
        elif action_type == 'set_remark':
            text = action_dict.get('remark_text', '')
            return f"添加备注：{text}"
        elif action_type == 'set_status':
            status = action_dict.get('status', '需补备注')
            return f"设置状态为：{status}"
        return str(action_dict)

    def _save_rules(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "错误", "规则名称不能为空")
            return
        rule = {
            'name': name,
            'enabled': self.enabled_cb.isChecked(),
            'condition': self._get_current_condition_dict(),
            **self._get_current_action_dict()
        }
        if self.current_index is not None:
            self.rules[self.current_index] = rule
        else:
            self.rules.append(rule)
            self.current_index = len(self.rules) - 1
        try:
            atomic_save_json({'rules': self.rules}, self.rules_path)
            QMessageBox.information(self, "保存成功", "规则已保存")
            self.unsaved = False
            self._refresh_rule_list()
            if self.on_rules_changed:
                self.on_rules_changed()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def _add_rule(self):
        name, ok = QInputDialog.getText(self, "新增规则", "请输入规则名称:")
        if ok and name.strip():
            new_rule = {
                'name': name.strip(),
                'enabled': True,
                'condition': {'field': 'dev_rate', 'op': '>=', 'value': 10},
                'action': 'set_color',
                'color': '#ffcccc'
            }
            self.rules.append(new_rule)
            self.current_index = len(self.rules) - 1
            self.unsaved = True
            self._refresh_rule_list()
            self.rule_list.setCurrentRow(self.current_index)
            self._load_rule_to_ui(new_rule)

    def _delete_rule(self):
        if self.current_index is None:
            QMessageBox.warning(self, "警告", "请先选中要删除的规则")
            return
        rule_name = self.name_edit.text()
        reply = QMessageBox.question(self, "确认删除", f"确定删除规则「{rule_name}」吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.rules[self.current_index]
            self.current_index = None
            self.unsaved = True
            self._refresh_rule_list()
            self._clear_edit_area()

    def _move_rule_up(self):
        if self.current_index is None or self.current_index == 0:
            return
        idx = self.current_index
        self.rules[idx], self.rules[idx-1] = self.rules[idx-1], self.rules[idx]
        self.current_index = idx - 1
        self.unsaved = True
        self._refresh_rule_list()
        self.rule_list.setCurrentRow(self.current_index)
        self._load_rule_to_ui(self.rules[self.current_index])

    def _move_rule_down(self):
        if self.current_index is None or self.current_index == len(self.rules)-1:
            return
        idx = self.current_index
        self.rules[idx], self.rules[idx+1] = self.rules[idx+1], self.rules[idx]
        self.current_index = idx + 1
        self.unsaved = True
        self._refresh_rule_list()
        self.rule_list.setCurrentRow(self.current_index)
        self._load_rule_to_ui(self.rules[self.current_index])

    def _clear_edit_area(self):
        self.name_edit.clear()
        self.enabled_cb.setChecked(True)
        for row in self.cond_rows:
            row.deleteLater()
        self.cond_rows.clear()
        _clear_layout(self.cond_container_layout)
        self.action_type_combo.setCurrentIndex(0)
        self._on_action_type_changed('set_color')
        self.test_result_label.clear()
