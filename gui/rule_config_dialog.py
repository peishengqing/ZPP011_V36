# gui/rule_config_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, simpledialog
import json
import os
import uuid
from core.rule_atomic_save import atomic_save_json
from core.rule_engine import safe_eval_condition, ALLOWED_FIELDS, OP_MAP

# 字段英→中映射（用于UI显示）
FIELD_DISPLAY = {
    'dev_rate': '偏差率(%)',
    'deviation_amount': '偏差金额(元)',
    'remark': '备注内容',
    'remark_status': '备注状态',
    'is_alt': '是否替代料',
    '定额': '定额',
    '实际': '实际',
    '偏差率(%)': '偏差率(%)',
    '备注原因': '备注原因',
}

# 中→英反向映射
FIELD_REVERSE = {v: k for k, v in FIELD_DISPLAY.items()}

class RuleConfigDialog:
    def __init__(self, parent, rules_path, on_rules_changed_callback=None):
        self.parent = parent
        self.rules_path = rules_path
        self.on_rules_changed = on_rules_changed_callback
        self.rules = self.load_rules()
        self.current_index = None
        self.unsaved = False

        self.window = tk.Toplevel(parent)
        self.window.title("可视化规则配置")
        self.window.geometry("1050x800")
        self.window.minsize(900, 650)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()
        self._refresh_rule_list()
        self._clear_edit_area()

    def load_rules(self):
        if os.path.exists(self.rules_path):
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('rules', [])
        return []

    def _build_ui(self):
        # 左侧框架：规则列表
        left_frame = tk.Frame(self.window, width=280, bg='#f0f0f0')
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        left_frame.pack_propagate(False)

        tk.Label(left_frame, text="规则列表", font=('微软雅黑', 10, 'bold')).pack(anchor='w', padx=5, pady=2)

        # 规则列表框（支持双击编辑）
        self.rule_listbox = tk.Listbox(left_frame, height=20, activestyle='none')
        self.rule_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        self.rule_listbox.bind('<<ListboxSelect>>', self.on_rule_select)
        self.rule_listbox.bind('<Double-Button-1>', self.on_rule_double_click)

        # 规则列表按钮行
        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="➕ 新增", command=self.add_rule).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="🗑 删除", command=self.delete_rule).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="⬆ 上移", command=self.move_rule_up).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="⬇ 下移", command=self.move_rule_down).pack(side=tk.LEFT, padx=2)

        # 右侧框架：编辑区
        right_frame = tk.Frame(self.window)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 规则名称与启用
        name_frame = tk.Frame(right_frame)
        name_frame.pack(fill=tk.X, pady=2)
        tk.Label(name_frame, text="规则名称:", width=10, anchor='e').pack(side=tk.LEFT)
        self.rule_name_var = tk.StringVar()
        tk.Entry(name_frame, textvariable=self.rule_name_var, width=35).pack(side=tk.LEFT, padx=5)
        self.enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(name_frame, text="启用", variable=self.enabled_var).pack(side=tk.LEFT, padx=10)

        # 条件构造器区域（可滚动）
        cond_frame = tk.LabelFrame(right_frame, text="条件", padx=5, pady=5)
        cond_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        # 添加滚动条
        cond_canvas = tk.Canvas(cond_frame, highlightthickness=0)
        cond_scrollbar = ttk.Scrollbar(cond_frame, orient="vertical", command=cond_canvas.yview)
        self.cond_container = tk.Frame(cond_canvas)
        self.cond_container.bind("<Configure>", lambda e: cond_canvas.configure(scrollregion=cond_canvas.bbox("all")))
        cond_canvas.create_window((0, 0), window=self.cond_container, anchor="nw")
        cond_canvas.configure(yscrollcommand=cond_scrollbar.set)
        cond_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cond_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 条件行存储：key=uuid, value={frame, field_var, op_var, value_var, delete_btn}
        self.cond_rows = {}
        # 组合方式
        combine_frame = tk.Frame(cond_frame)
        combine_frame.pack(fill=tk.X, pady=2)
        tk.Label(combine_frame, text="条件组合方式:").pack(side=tk.LEFT)
        self.cond_combine_op = tk.StringVar(value="and")
        tk.Radiobutton(combine_frame, text="并且 (AND)", variable=self.cond_combine_op, value="and").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(combine_frame, text="或者 (OR)", variable=self.cond_combine_op, value="or").pack(side=tk.LEFT, padx=5)
        tk.Button(combine_frame, text="➕ 添加条件", command=self.add_condition_row).pack(side=tk.RIGHT, padx=5)

        # 动作配置区域
        action_frame = tk.LabelFrame(right_frame, text="动作", padx=5, pady=5)
        action_frame.pack(fill=tk.X, pady=5)
        tk.Label(action_frame, text="动作类型:").grid(row=0, column=0, sticky='e', padx=5)
        self.action_type_var = tk.StringVar(value="set_color")
        ACTION_DISPLAY = {
            'set_color': '设置背景色', 'set_remark': '添加备注',
            'set_status': '设置状态', 'set_audit_result': '设置审核结果'
        }
        action_combo = ttk.Combobox(action_frame, textvariable=self.action_type_var,
                                    values=list(ACTION_DISPLAY.keys()), state="readonly", width=15)
        action_combo.grid(row=0, column=1, sticky='w', padx=5)
        action_combo.bind("<<ComboboxSelected>>", self.on_action_type_change)

        self.action_params_frame = tk.Frame(action_frame)
        self.action_params_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        self.action_params = {}

        # 测试面板
        test_frame = tk.LabelFrame(right_frame, text="测试规则", padx=5, pady=5)
        test_frame.pack(fill=tk.X, pady=5)

        # 动态创建测试输入控件（字段名中文显示）
        self.test_vars = {}
        row_idx = 0
        for field in ALLOWED_FIELDS:
            display_name = FIELD_DISPLAY.get(field, field)
            tk.Label(test_frame, text=f"{display_name}:").grid(row=row_idx, column=0, sticky='e', padx=5)
            if field in ('dev_rate', 'deviation_amount'):
                var = tk.DoubleVar(value=0.0)
                entry = tk.Entry(test_frame, textvariable=var, width=15)
            elif field == 'is_alt':
                var = tk.BooleanVar(value=False)
                entry = tk.Checkbutton(test_frame, variable=var)
            else:
                var = tk.StringVar(value="")
                entry = tk.Entry(test_frame, textvariable=var, width=20)
            entry.grid(row=row_idx, column=1, sticky='w', padx=5)
            self.test_vars[field] = var
            row_idx += 1

        tk.Button(test_frame, text="▶ 测试当前规则", command=self.test_rule).grid(row=row_idx, column=0, pady=5)
        self.test_result_label = tk.Label(test_frame, text="", fg="blue")
        self.test_result_label.grid(row=row_idx, column=1, sticky='w', pady=5)

        # 底部按钮
        bottom_frame = tk.Frame(right_frame)
        bottom_frame.pack(fill=tk.X, pady=10)
        tk.Button(bottom_frame, text="保存", command=self.save_rules, bg='#28a745', fg='white', width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(bottom_frame, text="取消", command=self.on_close, width=10).pack(side=tk.LEFT, padx=5)

    # ---------- 规则列表操作 ----------
    def _refresh_rule_list(self):
        self.rule_listbox.delete(0, tk.END)
        for i, rule in enumerate(self.rules):
            name = rule.get('name', f'规则{i+1}')
            enabled = rule.get('enabled', True)
            display = f"{'✓' if enabled else '✗'} {name}"
            self.rule_listbox.insert(tk.END, display)

    def on_rule_select(self, event):
        selection = self.rule_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx == self.current_index:
            return
        # 检查未保存更改
        if self.unsaved:
            if not messagebox.askyesno("未保存更改", "当前规则未保存，是否放弃更改并切换？"):
                # 恢复之前的选中
                if self.current_index is not None:
                    self.rule_listbox.selection_clear(0, tk.END)
                    self.rule_listbox.selection_set(self.current_index)
                return
        self.current_index = idx
        rule = self.rules[idx]
        self.load_rule_to_ui(rule)

    def on_rule_double_click(self, event):
        """双击规则名称快速编辑名称"""
        selection = self.rule_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        rule = self.rules[idx]
        new_name = simpledialog.askstring("编辑规则名称", "请输入新名称:", initialvalue=rule.get('name', ''))
        if new_name:
            rule['name'] = new_name
            self.unsaved = True
            self._refresh_rule_list()
            # 如果当前编辑的规则就是这个，更新UI
            if self.current_index == idx:
                self.rule_name_var.set(new_name)

    def move_rule_up(self):
        if self.current_index is None or self.current_index == 0:
            return
        idx = self.current_index
        self.rules[idx], self.rules[idx-1] = self.rules[idx-1], self.rules[idx]
        self.current_index = idx - 1
        self.unsaved = True
        self._refresh_rule_list()
        self.rule_listbox.selection_clear(0, tk.END)
        self.rule_listbox.selection_set(self.current_index)
        # 重新加载当前规则（索引变了，但内容不变）
        self.load_rule_to_ui(self.rules[self.current_index])

    def move_rule_down(self):
        if self.current_index is None or self.current_index == len(self.rules)-1:
            return
        idx = self.current_index
        self.rules[idx], self.rules[idx+1] = self.rules[idx+1], self.rules[idx]
        self.current_index = idx + 1
        self.unsaved = True
        self._refresh_rule_list()
        self.rule_listbox.selection_clear(0, tk.END)
        self.rule_listbox.selection_set(self.current_index)
        self.load_rule_to_ui(self.rules[self.current_index])

    # ---------- 规则编辑区 ----------
    def load_rule_to_ui(self, rule):
        self.rule_name_var.set(rule.get('name', ''))
        self.enabled_var.set(rule.get('enabled', True))

        cond = rule.get('condition')
        # 清空现有条件行
        for row_id in list(self.cond_rows.keys()):
            self.cond_rows[row_id]['frame'].destroy()
        self.cond_rows.clear()

        if isinstance(cond, dict):
            self.cond_combine_op.set(cond.get('operator', 'and'))
            for sub_cond in cond.get('conditions', []):
                self.add_condition_row(sub_cond)
        else:
            # 字符串表达式：显示只读提示
            expr_frame = tk.Frame(self.cond_container)
            expr_frame.pack(fill=tk.X, pady=2)
            tk.Label(expr_frame, text="原始表达式（只读）:").pack(side=tk.LEFT)
            expr_entry = tk.Entry(expr_frame, width=40, state='readonly')
            expr_entry.insert(0, str(cond))
            expr_entry.pack(side=tk.LEFT, padx=5)
            self.cond_rows['_string_expr'] = {'frame': expr_frame}
            # 可选：显示转换建议
            messagebox.showinfo("提示", "当前规则为字符串表达式，无法完全可视化。建议重新配置。")

        action_type = rule.get('action', 'set_color')
        self.action_type_var.set(action_type)
        self.on_action_type_change()
        if action_type == 'set_color':
            color = rule.get('color', '#ffcccc')
            self.action_params.get('color_var', tk.StringVar()).set(color)
            if 'color_preview' in self.action_params:
                self.action_params['color_preview'].config(bg=color)
        elif action_type == 'set_remark':
            text = rule.get('remark_text', '')
            self.action_params.get('remark_var', tk.StringVar()).set(text)
        elif action_type == 'set_status':
            status = rule.get('status', '需补备注')
            self.action_params.get('status_var', tk.StringVar()).set(status)
        self.unsaved = False

    def add_condition_row(self, default_cond=None):
        row_id = str(uuid.uuid4())
        frame = tk.Frame(self.cond_container)
        frame.pack(fill=tk.X, pady=2)

        # 字段选择（显示中文）
        default_field = default_cond.get('field', 'dev_rate') if default_cond else 'dev_rate'
        field_var = tk.StringVar(value=FIELD_DISPLAY.get(default_field, default_field))
        field_display_list = [FIELD_DISPLAY.get(f, f) for f in ALLOWED_FIELDS]
        field_combo = ttk.Combobox(frame, textvariable=field_var, values=field_display_list, width=12, state='readonly')
        field_combo.pack(side=tk.LEFT, padx=2)

        # 运算符选择（中文显示）
        OP_DISPLAY = {
            '>=': '≥ (大于等于)', '>': '> (大于)', '==': '= (等于)',
            '!=': '≠ (不等于)', '<': '< (小于)', '<=': '≤ (小于等于)',
            'contains': '包含', 'empty': '为空'
        }
        default_op = default_cond.get('op', '>=') if default_cond else '>='
        op_var = tk.StringVar(value=OP_DISPLAY.get(default_op, default_op))
        op_display_list = [OP_DISPLAY.get(o, o) for o in list(OP_MAP.keys())]
        op_combo = ttk.Combobox(frame, textvariable=op_var, values=op_display_list, width=12, state='readonly')
        op_combo.pack(side=tk.LEFT, padx=2)

        # 值输入区域
        value_frame = tk.Frame(frame)
        value_frame.pack(side=tk.LEFT, padx=2)
        value_var = tk.StringVar(value=str(default_cond.get('value', '')) if default_cond else '')

        def update_value_widget(*args):
            for w in value_frame.winfo_children():
                w.destroy()
            op = op_var.get()
            field = field_var.get()
            if op == 'empty':
                tk.Label(value_frame, text="(无需值)", fg="gray").pack(side=tk.LEFT)
                value_var.set("")
                return
            if field in ('dev_rate', 'deviation_amount'):
                spinbox = tk.Spinbox(value_frame, from_=-100000, to=100000, increment=1,
                                     textvariable=value_var, width=10)
                spinbox.pack(side=tk.LEFT)
            else:
                entry = tk.Entry(value_frame, textvariable=value_var, width=15)
                entry.pack(side=tk.LEFT)

        field_var.trace_add('write', update_value_widget)
        op_var.trace_add('write', update_value_widget)
        update_value_widget()

        # 删除按钮（独立删除该条件行）
        def delete_this_row():
            frame.destroy()
            del self.cond_rows[row_id]
        del_btn = tk.Button(frame, text="❌", command=delete_this_row, width=2)
        del_btn.pack(side=tk.LEFT, padx=2)

        self.cond_rows[row_id] = {
            'id': row_id,
            'frame': frame,
            'field_var': field_var,
            'op_var': op_var,
            'value_var': value_var,
        }

    def get_current_condition_dict(self):
        conditions = []
        for row_id, row_data in self.cond_rows.items():
            if row_id == '_string_expr':
                continue
            field_display = row_data['field_var'].get()
            # 中文→英文
            field = FIELD_REVERSE.get(field_display, field_display)
            op = row_data['op_var'].get()
            # 运算符也是中文显示，需要还原
            OP_REVERSE = {
                '≥ (大于等于)': '>=', '> (大于)': '>', '= (等于)': '==',
                '≠ (不等于)': '!=', '< (小于)': '<', '≤ (小于等于)': '<=',
                '包含': 'contains', '为空': 'empty'
            }
            op = OP_REVERSE.get(op, op)
            value = row_data['value_var'].get()
            if op not in ('contains', 'empty'):
                try:
                    value = float(value)
                except ValueError:
                    pass
            conditions.append({'field': field, 'op': op, 'value': value})
        if not conditions:
            return {}  # 空条件（永不匹配）
        if len(conditions) == 1:
            return conditions[0]
        else:
            return {'operator': self.cond_combine_op.get(), 'conditions': conditions}

    def get_current_action_dict(self):
        action_type = self.action_type_var.get()
        action_dict = {'action': action_type}
        if action_type == 'set_color':
            color_var = self.action_params.get('color_var')
            if color_var:
                action_dict['color'] = color_var.get()
        elif action_type == 'set_remark':
            remark_var = self.action_params.get('remark_var')
            if remark_var:
                action_dict['remark_text'] = remark_var.get()
        elif action_type == 'set_status':
            status_var = self.action_params.get('status_var')
            if status_var:
                action_dict['status'] = status_var.get()
        return action_dict

    def on_action_type_change(self, event=None):
        for widget in self.action_params_frame.winfo_children():
            widget.destroy()
        self.action_params.clear()
        action_type = self.action_type_var.get()
        if action_type == 'set_color':
            tk.Label(self.action_params_frame, text="背景色:").pack(side=tk.LEFT)
            color_var = tk.StringVar(value="#ffcccc")
            entry = tk.Entry(self.action_params_frame, textvariable=color_var, width=10)
            entry.pack(side=tk.LEFT, padx=5)
            def choose():
                color = colorchooser.askcolor(title="选择颜色", initialcolor=color_var.get())
                if color[1]:
                    color_var.set(color[1])
                    preview_label.config(bg=color[1])
            tk.Button(self.action_params_frame, text="选择", command=choose).pack(side=tk.LEFT)
            preview_label = tk.Label(self.action_params_frame, text="  ", width=3, bg=color_var.get(), relief='sunken')
            preview_label.pack(side=tk.LEFT, padx=5)
            self.action_params['color_var'] = color_var
            self.action_params['color_preview'] = preview_label
            # 实时更新预览
            def update_preview(*args):
                preview_label.config(bg=color_var.get())
            color_var.trace_add('write', update_preview)
        elif action_type == 'set_remark':
            tk.Label(self.action_params_frame, text="备注内容:").pack(side=tk.LEFT)
            remark_var = tk.StringVar()
            entry = tk.Entry(self.action_params_frame, textvariable=remark_var, width=40)
            entry.pack(side=tk.LEFT, padx=5)
            self.action_params['remark_var'] = remark_var
        elif action_type == 'set_status':
            tk.Label(self.action_params_frame, text="状态:").pack(side=tk.LEFT)
            status_var = tk.StringVar(value="需补备注")
            combo = ttk.Combobox(self.action_params_frame, textvariable=status_var,
                                 values=["已备注", "需补备注", "已审核", "未审核"], width=15)
            combo.pack(side=tk.LEFT, padx=5)
            self.action_params['status_var'] = status_var

    # ---------- 测试功能 ----------
    def _format_action(self, action_dict):
        """将动作字典转为中文描述"""
        action_type = action_dict.get('action', '')
        if action_type == 'set_color':
            color = action_dict.get('color', '#ffcccc')
            return f"设置背景色为 {color}"
        elif action_type == 'set_remark':
            text = action_dict.get('remark_text', '')
            return f"添加备注：{text}"
        elif action_type == 'set_status':
            status = action_dict.get('status', '需补备注')
            return f"设置状态为：{status}"
        elif action_type == 'set_audit_result':
            result = action_dict.get('audit_result', '')
            return f"设置审核结果：{result}"
        return str(action_dict)

    def test_rule(self):
        row_data = {field: var.get() for field, var in self.test_vars.items()}
        row_data['is_alt'] = bool(row_data['is_alt'])
        for field in ('dev_rate', 'deviation_amount'):
            try:
                row_data[field] = float(row_data[field])
            except:
                row_data[field] = 0.0
        cond_dict = self.get_current_condition_dict()
        if not cond_dict:
            self.test_result_label.config(text="⚠️ 规则无条件，永不匹配", fg="orange")
            return
        try:
            matched = safe_eval_condition(cond_dict, row_data)
            if matched:
                action = self.get_current_action_dict()
                action_desc = self._format_action(action)
                self.test_result_label.config(text=f"✅ 匹配成功！将执行：{action_desc}", fg="green")
            else:
                self.test_result_label.config(text="❌ 不匹配", fg="red")
        except Exception as e:
            self.test_result_label.config(text=f"⚠️ 测试出错: {e}", fg="orange")

    # ---------- 保存与新增删除 ----------
    def save_rules(self):
        name = self.rule_name_var.get().strip()
        if not name:
            messagebox.showerror("错误", "规则名称不能为空")
            return
        # 更新当前规则
        rule = {
            'name': name,
            'enabled': self.enabled_var.get(),
            'condition': self.get_current_condition_dict(),
            **self.get_current_action_dict()
        }
        if self.current_index is not None:
            self.rules[self.current_index] = rule
        else:
            self.rules.append(rule)
            self.current_index = len(self.rules) - 1
        try:
            atomic_save_json({'rules': self.rules}, self.rules_path)
            messagebox.showinfo("保存成功", "规则已保存")
            self.unsaved = False
            self._refresh_rule_list()
            # 通知主窗口刷新
            if self.on_rules_changed:
                self.on_rules_changed()
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def add_rule(self):
        name = simpledialog.askstring("新增规则", "请输入规则名称:")
        if not name:
            return
        new_rule = {
            'name': name,
            'enabled': True,
            'condition': {'field': 'dev_rate', 'op': '>=', 'value': 10},
            'action': 'set_color',
            'color': '#ffcccc'
        }
        self.rules.append(new_rule)
        self.current_index = len(self.rules) - 1
        self.unsaved = True
        self._refresh_rule_list()
        self.rule_listbox.selection_clear(0, tk.END)
        self.rule_listbox.selection_set(self.current_index)
        self.load_rule_to_ui(new_rule)

    def delete_rule(self):
        if self.current_index is None:
            messagebox.showwarning("警告", "请先选中要删除的规则")
            return
        if messagebox.askyesno("确认删除", f"确定删除规则「{self.rule_name_var.get()}」吗？"):
            del self.rules[self.current_index]
            self.current_index = None
            self.unsaved = True
            self._refresh_rule_list()
            self._clear_edit_area()

    def _clear_edit_area(self):
        self.rule_name_var.set("")
        self.enabled_var.set(True)
        for row_id in list(self.cond_rows.keys()):
            self.cond_rows[row_id]['frame'].destroy()
        self.cond_rows.clear()
        self.action_type_var.set("set_color")
        self.on_action_type_change()
        self.test_result_label.config(text="")

    def on_close(self):
        if self.unsaved:
            ans = messagebox.askyesnocancel("未保存更改", "规则尚未保存，是否保存？")
            if ans is True:
                self.save_rules()
                self.window.destroy()
            elif ans is False:
                self.window.destroy()
            else:
                return
        else:
            self.window.destroy()