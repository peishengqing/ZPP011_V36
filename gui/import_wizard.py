# -*- coding: utf-8 -*-
"""
模板导入向导 — 支持替代料配对和备注校验规则导入
（已整合 Trae 审计建议：模糊匹配、预览提示、事务回滚）
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import difflib
import pandas as pd

from core.import_handlers import import_alt_pairs_from_excel, import_rules_from_excel
from domain.alt_material.alt_manager import save_alt_pairs


class ImportWizard:
    def __init__(self, parent, alt_pairs, rules_path, on_alt_changed=None, on_rules_changed=None):
        self.parent = parent
        self.alt_pairs = alt_pairs
        self.rules_path = rules_path
        self.on_alt_changed = on_alt_changed
        self.on_rules_changed = on_rules_changed

        self.window = tk.Toplevel(parent.root)
        self.window.title("模板导入向导")
        self.window.geometry("800x600")
        self.window.minsize(700, 500)
        self.window.transient(parent.root)
        self.window.grab_set()

        self.current_step = 0
        self.steps = ["选择类型", "选择文件", "列映射", "预览与确认", "导入完成"]
        self.import_type = None
        self.excel_path = None
        self.sheet_name = None
        self.df = None
        self.column_mapping = {}
        self.parsed_data = None

        self._build_ui()
        self._show_step(0)

    # ---------- UI 构建 ----------
    def _build_ui(self):
        self.main_frame = tk.Frame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.step_label = tk.Label(self.window, text="", font=("微软雅黑", 10, "bold"))
        self.step_label.pack(pady=5)

        self.content_frame = tk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        self.button_frame = tk.Frame(self.window)
        self.button_frame.pack(fill=tk.X, padx=10, pady=10)
        self.btn_prev = tk.Button(self.button_frame, text="上一步", command=self._prev_step, state=tk.DISABLED)
        self.btn_prev.pack(side=tk.LEFT, padx=5)
        self.btn_next = tk.Button(self.button_frame, text="下一步", command=self._next_step)
        self.btn_next.pack(side=tk.RIGHT, padx=5)
        self.btn_cancel = tk.Button(self.button_frame, text="取消", command=self.window.destroy)
        self.btn_cancel.pack(side=tk.RIGHT, padx=5)

    def _show_step(self, step):
        self.current_step = step
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.step_label.config(text=f"步骤 {step+1}/{len(self.steps)}：{self.steps[step]}")

        if step == 0:
            self._step_select_type()
        elif step == 1:
            self._step_select_file()
        elif step == 2:
            self._step_column_mapping()
        elif step == 3:
            self._step_preview()
        elif step == 4:
            self._step_complete()

        self.btn_prev.config(state=tk.NORMAL if step > 0 else tk.DISABLED)
        self.btn_next.config(text="完成" if step == 3 else "下一步")

    # ---------- 步骤 0：选择类型 ----------
    def _step_select_type(self):
        tk.Label(self.content_frame, text="请选择要导入的数据类型：", font=("微软雅黑", 12)).pack(pady=20)
        frame = tk.Frame(self.content_frame)
        frame.pack()
        self.type_var = tk.StringVar(value="alt")
        tk.Radiobutton(frame, text="替代料配对（Excel）", variable=self.type_var, value="alt", font=("微软雅黑", 11)).pack(anchor='w', pady=5)
        tk.Radiobutton(frame, text="备注校验规则（Excel）", variable=self.type_var, value="rule", font=("微软雅黑", 11)).pack(anchor='w', pady=5)

    # ---------- 步骤 1：选择文件 ----------
    def _step_select_file(self):
        self.import_type = self.type_var.get()
        tk.Label(self.content_frame, text="选择 Excel 文件：", font=("微软雅黑", 11)).pack(anchor='w', pady=5)
        file_frame = tk.Frame(self.content_frame)
        file_frame.pack(fill=tk.X, pady=5)
        self.file_path_var = tk.StringVar()
        entry = tk.Entry(file_frame, textvariable=self.file_path_var, width=60)
        entry.pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="浏览", command=self._browse_file).pack(side=tk.LEFT)

        tk.Label(self.content_frame, text="工作表名称：", font=("微软雅黑", 11)).pack(anchor='w', pady=5)
        self.sheet_combo = ttk.Combobox(self.content_frame, width=40)
        self.sheet_combo.pack(anchor='w', pady=5)

        if self.import_type == 'alt':
            desc = "Excel 需包含列：工厂名称、物料A编码、物料A名称、物料B编码、物料B名称（列名可自定义，下一步映射）"
        else:
            desc = "Excel 需包含列：规则名称、条件表达式、动作类型、动作参数、启用（列名可自定义）"
        tk.Label(self.content_frame, text=desc, fg="gray", font=("微软雅黑", 9)).pack(anchor='w', pady=10)

    def _browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel 文件", "*.xlsx *.xls")])
        if path:
            self.file_path_var.set(path)
            try:
                xl = pd.ExcelFile(path)
                self.sheet_combo['values'] = xl.sheet_names
                if xl.sheet_names:
                    self.sheet_combo.set(xl.sheet_names[0])
            except Exception as e:
                messagebox.showerror("错误", f"读取文件失败：{e}")

    # ---------- 步骤 2：列映射（含模糊匹配）----------
    def _step_column_mapping(self):
        self.excel_path = self.file_path_var.get()
        self.sheet_name = self.sheet_combo.get()
        if not self.excel_path or not os.path.exists(self.excel_path):
            messagebox.showerror("错误", "请先选择有效的 Excel 文件")
            self._show_step(1)
            return
        try:
            self.df = pd.read_excel(self.excel_path, sheet_name=self.sheet_name)
            if self.df.empty:
                raise ValueError("工作表为空")
        except Exception as e:
            messagebox.showerror("错误", f"读取工作表失败：{e}")
            self._show_step(1)
            return

        cols = self.df.columns.tolist()
        tk.Label(self.content_frame, text="请映射 Excel 列到系统字段：", font=("微软雅黑", 11)).pack(anchor='w', pady=5)
        frame = tk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)

        if self.import_type == 'alt':
            fields = ["工厂名称", "物料A编码", "物料A名称", "物料B编码", "物料B名称"]
        else:
            fields = ["规则名称", "条件表达式", "动作类型", "动作参数", "启用"]

        self.mapping_vars = {}
        row = 0
        for field in fields:
            tk.Label(frame, text=field + "：").grid(row=row, column=0, sticky='e', padx=5, pady=3)
            var = tk.StringVar()
            combo = ttk.Combobox(frame, textvariable=var, values=cols, width=30)
            combo.grid(row=row, column=1, sticky='w', padx=5, pady=3)

            # ===== 模糊匹配增强 =====
            def fuzzy_match(target, candidates, threshold=0.6):
                matches = difflib.get_close_matches(target, candidates, n=1, cutoff=threshold)
                return matches[0] if matches else None

            # 先精确匹配
            for col in cols:
                if field == col or (field.replace("编码", "").replace("名称", "") in col) or (col in field):
                    var.set(col)
                    break
            else:
                matched = fuzzy_match(field, cols)
                if matched:
                    var.set(matched)
            # ===== 模糊匹配结束 =====

            self.mapping_vars[field] = var
            row += 1

        # 预览前5行
        preview_frame = tk.LabelFrame(self.content_frame, text="数据预览（前5行）", padx=5, pady=5)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        text = tk.Text(preview_frame, height=8, wrap=tk.NONE)
        scroll_y = tk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=text.yview)
        scroll_x = tk.Scrollbar(preview_frame, orient=tk.HORIZONTAL, command=text.xview)
        text.config(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        preview_text = self.df.head().to_string(index=False)
        text.insert(tk.END, preview_text)
        text.config(state=tk.DISABLED)

    # ---------- 步骤 3：预览与确认 ----------
    def _step_preview(self):
        mapping = {field: var.get() for field, var in self.mapping_vars.items()}
        if not all(mapping.values()):
            messagebox.showerror("错误", "请完成所有列映射")
            self._show_step(2)
            return
        try:
            if self.import_type == 'alt':
                self.parsed_data = self._parse_alt_data(mapping)
            else:
                self.parsed_data = self._parse_rule_data(mapping)
        except Exception as e:
            messagebox.showerror("解析错误", str(e))
            self._show_step(2)
            return

        # 显示总数及预览提示
        total_count = len(self.parsed_data)
        tk.Label(self.content_frame, text=f"共解析到 {total_count} 条记录（仅显示前20条）", font=("微软雅黑", 11)).pack(anchor='w', pady=5)

        # 预演表格
        frame = tk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True, pady=10)
        tree = ttk.Treeview(frame, columns=("col1", "col2", "col3", "col4", "col5"), show="headings", height=10)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scroll.set)

        if self.import_type == 'alt':
            tree.heading("col1", text="工厂")
            tree.heading("col2", text="物料A编码")
            tree.heading("col3", text="物料A名称")
            tree.heading("col4", text="物料B编码")
            tree.heading("col5", text="物料B名称")
            for item in self.parsed_data[:20]:
                tree.insert("", "end", values=(item['工厂'], item['物料A编码'], item['物料A名称'], item['物料B编码'], item['物料B名称']))
        else:
            tree.heading("col1", text="规则名称")
            tree.heading("col2", text="条件")
            tree.heading("col3", text="动作")
            tree.heading("col4", text="参数")
            tree.heading("col5", text="启用")
            for item in self.parsed_data[:20]:
                tree.insert("", "end", values=(item['name'], item['condition'], item['action'], item.get('param', ''), item['enabled']))

        # 导入模式
        mode_frame = tk.Frame(self.content_frame)
        mode_frame.pack(fill=tk.X, pady=10)
        tk.Label(mode_frame, text="导入模式：").pack(side=tk.LEFT)
        self.overwrite_var = tk.BooleanVar(value=False)
        tk.Radiobutton(mode_frame, text="追加（保留现有，添加新数据）", variable=self.overwrite_var, value=False).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(mode_frame, text="覆盖（清空现有，完全替换）", variable=self.overwrite_var, value=True).pack(side=tk.LEFT, padx=10)

    # ---------- 解析替代料数据 ----------
    def _parse_alt_data(self, mapping):
        df = self.df.copy()
        df.rename(columns={v: k for k, v in mapping.items()}, inplace=True)
        required = ['工厂名称', '物料A编码', '物料A名称', '物料B编码', '物料B名称']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"缺少列：{col}")
        df = df[required].dropna()
        if df.empty:
            raise ValueError("没有有效数据行")
        df = df.applymap(lambda x: str(x).strip() if pd.notna(x) else '')
        df = df[(df['物料A编码'] != '') & (df['物料B编码'] != '')]
        return df.to_dict('records')

    # ---------- 解析规则数据 ----------
    def _parse_rule_data(self, mapping):
        df = self.df.copy()
        df.rename(columns={v: k for k, v in mapping.items()}, inplace=True)
        required = ['规则名称', '条件表达式', '动作类型', '动作参数', '启用']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"缺少列：{col}")
        df = df[required].dropna()
        if df.empty:
            raise ValueError("没有有效数据行")
        records = []
        for _, row in df.iterrows():
            record = {
                'name': str(row['规则名称']).strip(),
                'condition': str(row['条件表达式']).strip(),
                'action': str(row['动作类型']).strip(),
                'enabled': str(row['启用']).strip().lower() in ('true', '是', '1', 'yes')
            }
            param = str(row['动作参数']).strip()
            if record['action'] == 'set_color':
                record['color'] = param
            elif record['action'] == 'set_remark':
                record['remark_text'] = param
            elif record['action'] == 'set_status':
                record['status'] = param
            records.append(record)
        return records

    # ---------- 步骤 4：导入完成（事务回滚）----------
    def _step_complete(self):
        if self.parsed_data is None:
            messagebox.showerror("错误", "没有可导入的数据")
            self.window.destroy()
            return

        try:
            if self.import_type == 'alt':
                # 1. 计算新配对列表（不修改原内存）
                new_pairs = import_alt_pairs_from_excel(self.parsed_data, self.alt_pairs, overwrite=self.overwrite_var.get())
                # 2. 先保存到文件（原子保存）
                save_alt_pairs(new_pairs, log_cb=self.parent.log)
                # 3. 保存成功后更新内存
                self.alt_pairs.clear()
                self.alt_pairs.extend(new_pairs)
                if self.on_alt_changed:
                    self.on_alt_changed()
                msg = f"成功导入 {len(self.parsed_data)} 条替代料配对"
            else:
                import_rules_from_excel(self.parsed_data, self.rules_path, overwrite=self.overwrite_var.get())
                if self.on_rules_changed:
                    self.on_rules_changed()
                msg = f"成功导入 {len(self.parsed_data)} 条规则"

            tk.Label(self.content_frame, text=msg, font=("微软雅黑", 12), fg="green").pack(pady=20)
            tk.Label(self.content_frame, text="导入完成！", font=("微软雅黑", 12)).pack(pady=10)
            self.btn_next.config(state=tk.DISABLED)
            self.btn_cancel.config(text="关闭")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))
            self.window.destroy()

    def _prev_step(self):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _next_step(self):
        if self.current_step == 0:
            self._show_step(1)
        elif self.current_step == 1:
            if not self.file_path_var.get() or not self.sheet_combo.get():
                messagebox.showerror("错误", "请选择文件和工作表")
                return
            self._show_step(2)
        elif self.current_step == 2:
            self._show_step(3)
        elif self.current_step == 3:
            self._show_step(4)
        else:
            self.window.destroy()