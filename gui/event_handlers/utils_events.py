# -*- coding: utf-8 -*-
"""故事线、替代料、BOM、预检、树视图、断点等杂项事件"""

import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from widgets import C
import os, sys as _sys, glob as _glob
import pandas as pd
from storage import storage
from core.state_store import get_state
from core.rule_engine import RuleEngine
from core.decorators import with_feedback
from core.task_manager import TaskManager
from modules.audit.models.audit_model import AuditModel
from openpyxl import Workbook, load_workbook
from copy import deepcopy
from domain.alt_material.alt_manager import save_alt_pairs, load_alt_pairs
import time, datetime, threading, traceback, json, csv, calendar


class UtilsEvents:
    """故事线、替代料、BOM、预检、树视图、断点等杂项事件"""
    def _show_storyline(self):
        """弹出故事线窗口（直接包含统计逻辑）"""
        if self.audit_data is None or self.audit_data.empty:
            messagebox.showinfo("提示", "无数据生成故事线")
            return

        lines = []
        lines.append(f"📅 统计周期：{self.start_date.get()} 至 {self.end_date.get()}")
        lines.append("")

        if '偏差金额' in self.audit_data.columns:
            total_amount = self.audit_data['偏差金额'].sum()
            lines.append(f"💰 总偏差金额：¥{total_amount:,.2f}")
        else:
            lines.append("💰 总偏差金额：无数据")

        over_col = next((c for c in self.audit_data.columns if '多耗' in c or '超耗' in c), None)
        under_col = next((c for c in self.audit_data.columns if '少耗' in c or '节约' in c), None)
        if over_col and under_col:
            lines.append(f"📈 多耗总额：¥{self.audit_data[over_col].sum():,.2f}")
            lines.append(f"📉 少耗总额：¥{self.audit_data[under_col].sum():,.2f}")

        if '偏差率(%)' in self.audit_data.columns:
            high = (self.audit_data['偏差率(%)'].abs() > 10).sum()
            medium = ((self.audit_data['偏差率(%)'].abs() >= 5) & (self.audit_data['偏差率(%)'].abs() <= 10)).sum()
            low = (self.audit_data['偏差率(%)'].abs() < 5).sum()
            lines.append("")
            lines.append(f"🔴 偏差率 >10%：{high} 行")
            lines.append(f"🟡 偏差率 5%-10%：{medium} 行")
            lines.append(f"🟢 偏差率 <5%：{low} 行")

        if '备注原因' in self.audit_data.columns:
            total = len(self.audit_data)
            has_remark = self.audit_data['备注原因'].notna().sum()
            lines.append("")
            lines.append(f"📝 备注覆盖率：{has_remark}/{total} ({has_remark/total*100:.1f}%)")

        text_content = chr(10).join(lines)

        # 创建弹窗
        d = tk.Toplevel(self.root)
        d.title("📖 本周偏差故事线")
        d.geometry("600x520")
        d.transient(self.root)
        d.grab_set()
        d.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 600) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 520) // 2
        d.geometry(f"+{x}+{y}")

        tk.Label(d, text="📖 本周偏差故事线", font=("Microsoft YaHei", 12, "bold")).pack(pady=10)
        text = tk.Text(d, font=("Microsoft YaHei", 10), wrap="word", height=20)
        text.pack(fill="both", expand=True, padx=10, pady=5)
        text.insert("1.0", text_content)
        text.configure(state="disabled")

        def copy_to_clip():
            d.clipboard_clear()
            d.clipboard_append(text_content)
            messagebox.showinfo("已复制", "故事线已复制到剪贴板")

        tk.Button(d, text="📋 复制到剪贴板", command=copy_to_clip,
                  bg="#4a90d9", fg="white", relief="flat", width=15).pack(pady=8)


    def _scan_remark_cleanup(self):
        """扫描备注数据并生成清洗建议（如存在）"""
        if self.audit_data is None or self.audit_data.empty:
            messagebox.showinfo("提示", "无数据可扫描")
            return
        # 确定物料描述列
        mat_col = None
        for col in self.audit_data.columns:
            if '物料描述' in col or '组件描述' in col:
                mat_col = col
                break





        if mat_col is None:





            mat_col = '组件物料描述'

        # 确定备注列
        remark_col = next((c for c in ['备注', '备注原因'] if c in self.audit_data.columns), '备注')











        # 清洗规则





        cleanup_rules = {





            '额定不足': '定额偏低', '定额低': '定额偏低',





            '定额高': '定额偏高', '设高': '定额偏高',





            '设低': '定额偏低', '没有定额': '系统无定额',





            '无定额': '系统无定额', '未定额': '系统无定额',





            '没用过': '未填写', '不知道': '未填写',





            '待查': '未填写', '测试': '试产',





            '试机': '试产', '打样': '试产',





            '样板': '试产', '堵': '堵料',





            '卡': '卡料', '破': '破损', '烂': '破损',





        }











        suggestions = []





        for idx, row in self.audit_data.iterrows():





            remark = str(row.get(remark_col, '')).strip()





            if not remark or remark in ('nan', 'NaN', 'None'):





                continue





            for keyword, standard in cleanup_rules.items():





                if keyword in remark and remark != standard:





                    suggestions.append({





                        'idx': idx,





                        '物料': str(row.get(mat_col, ''))[:25],





                        '当前备注': remark,





                        '建议标准化为': standard,





                        'excel_row': int(row.get('excel_row', 0)),





                        'remark_col': remark_col,





                    })





                    break





        return suggestions











    def _show_cleanup_window(self):





        """显示备注清洗标准化窗口"""





        suggestions = self._scan_remark_cleanup()





        if not suggestions:





            messagebox.showinfo("提示", "未发现可清洗的备注，数据已很规范")





            return











        d = tk.Toplevel(self.root)





        d.title("🧹 备注清洗标准化")





        d.geometry(self.config.get("ui.cleanup_window_size", "750x480"))





        d.transient(self.root)





        d.grab_set()





        d.update_idletasks()





        rx = self.root.winfo_rootx() + (self.root.winfo_width() - 750) // 2





        ry = self.root.winfo_rooty() + (self.root.winfo_height() - 480) // 2





        d.geometry(f"+{rx}+{ry}")











        tk.Label(d, text=f"发现 {len(suggestions)} 条可标准化的备注，勾选后点击执行",





                 font=("Microsoft YaHei", 10)).pack(pady=10)











        # 表格：物料 / 当前备注 / 建议标准化为





        tree_frame = tk.Frame(d)





        tree_frame.pack(fill="both", expand=True, padx=10)





        cols = ("select", "material", "current", "suggested")





        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)





        tree.heading("select", text="✓")





        tree.heading("material", text="物料描述")





        tree.heading("current", text="当前备注")





        tree.heading("suggested", text="建议标准化为")





        tree.column("select", width=30, anchor="center")





        tree.column("material", width=150, anchor="w")





        tree.column("current", width=250, anchor="w")





        tree.column("suggested", width=200, anchor="w")











        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)





        tree.configure(yscrollcommand=scroll_y.set)





        scroll_y.pack(side="right", fill="y")





        tree.pack(side="left", fill="both", expand=True)











        # 填充数据





        self._cleanup_checkboxes = {}





        for i, sug in enumerate(suggestions):





            item_id = tree.insert('', 'end', values=('☐', sug['物料'], sug['当前备注'], sug['建议标准化为']))





            self._cleanup_checkboxes[item_id] = (False, sug)











        # 点击行切换勾选状态





        def toggle_check(event):





            item_id = tree.identify_row(event.y)





            if not item_id or item_id not in self._cleanup_checkboxes:





                return





            checked, sug = self._cleanup_checkboxes[item_id]





            new_checked = not checked





            self._cleanup_checkboxes[item_id] = (new_checked, sug)





            tree.set(item_id, "select", '☑' if new_checked else '☐')











        tree.bind("<Button-1>", toggle_check)











        # 底部按钮





        btn_frame = tk.Frame(d)





        btn_frame.pack(pady=10)











        def select_all():





            for item_id in self._cleanup_checkboxes:





                _, sug = self._cleanup_checkboxes[item_id]





                self._cleanup_checkboxes[item_id] = (True, sug)





                tree.set(item_id, "select", '☑')











        def execute_cleanup():





            cleaned = 0





            for item_id, (checked, sug) in self._cleanup_checkboxes.items():





                if checked and self.audit_data is not None:





                    remark_col = sug.get('remark_col', '备注原因'); self.audit_data.at[sug['idx'], remark_col] = sug['建议标准化为']





                    cleaned += 1





            if cleaned > 0:





                self._refresh_audit_tree(self.audit_data)





            try:





                self.audit_tree['displaycolumns'] = '#all'





                self.root.update_idletasks()





                self.log("[DEBUG] AI审核完成后强制恢复displaycolumns", "info")





            except Exception as e:





                self.log(f"[ERROR] 恢复displaycolumns失败: {e}", "error")





                self._update_audit_stats()





                self._update_filter_options()





                self.log(f"🧹 备注清洗完成：{cleaned} 条已标准化", "success")





                messagebox.showinfo("完成", f"已标准化 {cleaned} 条备注")





            d.destroy()











        tk.Button(btn_frame, text="全选", command=select_all,





                  bg="#d0d7de", font=("Microsoft YaHei", 10), relief="flat", width=10).pack(side="left", padx=5)





        tk.Button(btn_frame, text="执行选中", command=execute_cleanup,





                  bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10), relief="flat", width=10).pack(side="left", padx=5)





        tk.Button(btn_frame, text="取消", command=d.destroy,





                  bg="#9E9E9E", fg="white", font=("Microsoft YaHei", 10), relief="flat", width=10).pack(side="left", padx=5)

















    def _add_alt(self):





        d = tk.Toplevel(self.root)





        d.title("添加替代料配对")





        d.geometry(self.config.get("ui.alt_dialog_size", "580x300"))





        d.transient(self.root)





        d.grab_set()





        d.configure(bg=C['bg'])











        tk.Label(d, text="物料A（编码或名称）：", font=("Microsoft YaHei", 10),





                 fg=C['text'], bg=C['bg']).pack(pady=(10, 3), anchor="w", padx=20)











        var_a = tk.StringVar()





        if hasattr(self, 'material_list') and self.material_list:





            cb_a = ttk.Combobox(d, textvariable=var_a, values=self.material_list,





                                font=("Consolas", 9), state="normal", width=65)





            cb_a.pack(padx=20, fill="x")





            cb_a.set("输入关键字或点击下拉选择...")





            def on_focus_a(e):





                if var_a.get() == "输入关键字或点击下拉选择...":





                    var_a.set("")





            cb_a.bind("<FocusIn>", on_focus_a)





        else:





            e_a = tk.Entry(d, font=("Consolas", 9), bg=C['surface2'],





                           fg=C['text'], insertbackground=C['accent'], relief="flat")





            e_a.pack(padx=20, fill="x")





            e_a.insert(0, "（未找到物料列表，请手动输入）")











        tk.Label(d, text="物料B（编码或名称）：", font=("Microsoft YaHei", 10),





                 fg=C['text'], bg=C['bg']).pack(pady=(10, 3), anchor="w", padx=20)











        var_b = tk.StringVar()





        if hasattr(self, 'material_list') and self.material_list:





            cb_b = ttk.Combobox(d, textvariable=var_b, values=self.material_list,





                                font=("Consolas", 9), state="normal", width=65)





            cb_b.pack(padx=20, fill="x")





            cb_b.set("输入关键字或点击下拉选择...")





            def on_focus_b(e):





                if var_b.get() == "输入关键字或点击下拉选择...":





                    var_b.set("")





            cb_b.bind("<FocusIn>", on_focus_b)





        else:





            e_b = tk.Entry(d, font=("Consolas", 9), bg=C['surface2'],





                           fg=C['text'], insertbackground=C['accent'], relief="flat")





            e_b.pack(padx=20, fill="x")





            e_b.insert(0, "（未找到物料列表，请手动输入）")











        # 已有配对列表（用于删除）





        lst = None  # 将在后面定义











        def confirm():





            a = var_a.get().strip()





            b = var_b.get().strip()





            if not a or not b:





                messagebox.showwarning("提示", "物料A和物料B都必须填写！")





                return











            def parse_selection(x):





                if '|' in x:





                    parts = [p.strip() for p in x.split('|')]





                    if len(parts) >= 3:





                        # 格式: 工厂 | 编码 | 名称





                        return parts[0], parts[1], parts[2]  # (工厂, 编码, 名称)





                    elif len(parts) == 2:





                        # 格式: 编码 | 名称





                        return '', parts[0], parts[1]  # (空工厂, 编码, 名称)





                    else:





                        return '', parts[0], ''  # (空工厂, 编码, 空名称)





                else:





                    # 手动输入时尝试从物料列表匹配





                    for item in getattr(self, 'material_list', []):





                        if x in item:





                            parts = [p.strip() for p in item.split('|')]





                            if len(parts) >= 3:





                                return parts[0], parts[1], parts[2]  # (工厂, 编码, 名称)





                    return '', x, x  # 兜底











            factory_a, a_code, a_name = parse_selection(a)





            factory_b, b_code, b_name = parse_selection(b)











            # Bug 6 修复：检查 A 和 B 不能是同一个物料





            if a_code == b_code:





                messagebox.showwarning("提示", "物料A和物料B不能是同一个物料！")





                return











            # 去重检查：是否已存在相同配对（编码为空时用描述匹配）





            exact_match = False





            conflict = False





            for (ea, eb) in self.alt_pairs:





                def _extract_code_and_desc(item):





                    if isinstance(item, (list, tuple)):





                        if len(item) >= 3:





                            code = str(item[1]).strip() if item[1] else ''





                            desc = str(item[2]).strip() if item[2] else ''





                            return code if code else desc  # 编码为空用描述





                        if len(item) == 2:





                            code = str(item[0]).strip() if item[0] else ''





                            desc = str(item[1]).strip() if item[1] else ''





                            return code if code else desc





                        return str(item[0]).strip() if item[0] else ''





                    s = str(item).strip()





                    return s if s else ''





                ea_key = _extract_code_and_desc(ea)





                eb_key = _extract_code_and_desc(eb)





                a_key = a_code if a_code else a_name





                b_key = b_code if b_code else b_name





                if (ea_key == a_key and eb_key == b_key) or (ea_key == b_key and eb_key == a_key):





                    exact_match = True





                    break





                if a_key in (ea_key, eb_key) or b_key in (ea_key, eb_key):





                    conflict = True











            if exact_match:





                msg = f"配对已存在：{a_code} ↔ {b_code}\n是否仍要添加？"





                if not messagebox.askyesno("重复配对", msg):





                    return





            if conflict:





                warn = f"物料 {a_code} 或 {b_code} 已存在于其他配对中，继续添加可能导致冲突。\n是否仍要添加？"





                if not messagebox.askyesno("物料冲突", warn):





                    return











            save_a = (factory_a, a_code, a_name)





            save_b = (factory_b, b_code, b_name)





            self.alt_pairs.append((save_a, save_b))





            try:





                save_alt_pairs(self.alt_pairs, log_cb=self.log)





            except Exception as e:





                messagebox.showerror("错误", f"替代料添加失败：{e}")





                return





            self._refresh_alt_view(self._alt_inner)





            messagebox.showinfo("提示", "替代料添加成功！")





            d.destroy()











        def do_del():





            if lst and lst.curselection():





                idx = lst.curselection()[0]





                del self.alt_pairs[idx]





                save_alt_pairs(self.alt_pairs, log_cb=self.log)





                self._refresh_alt_view(self._alt_inner)





                d.destroy()





            else:





                messagebox.showwarning("提示", "请先选择要删除的配对")











        btn_frame = tk.Frame(d, bg=C['bg'])





        btn_frame.pack(pady=12)





        tk.Button(btn_frame, text="✓ 确定", command=confirm, bg="#4CAF50", fg="white",





                  font=("Microsoft YaHei", 10), relief="flat", width=10).pack(side="left", padx=8)





        tk.Button(btn_frame, text="✗ 取消", command=d.destroy, bg="#9E9E9E", fg="white",





                  font=("Microsoft YaHei", 10), relief="flat", width=10).pack(side="left", padx=8)











        if self.alt_pairs:





            tk.Label(d, text="已有配对（点击可删除）：", font=("Microsoft YaHei", 9),





                     fg=C['text_dim'], bg=C['bg']).pack(pady=(10, 3))





            lst = tk.Listbox(d, font=("Consolas", 9), height=4, selectmode='single')





            lst.pack(fill="x", padx=20)





            for a, b in self.alt_pairs:





                # 解析显示





                if isinstance(a, (list, tuple)) and len(a) == 3:





                    _, a_code, a_name = a





                elif isinstance(a, (list, tuple)) and len(a) == 2:





                    a_code, a_name = a





                else:





                    a_code, a_name = str(a), ''





                if isinstance(b, (list, tuple)) and len(b) == 3:





                    _, b_code, b_name = b





                elif isinstance(b, (list, tuple)) and len(b) == 2:





                    b_code, b_name = b





                else:





                    b_code, b_name = str(b), ''





                left = f"{a_code} {a_name}" if a_name else a_code





                right = f"{b_code} {b_name}" if b_name else b_code





                lst.insert('end', left + " ⇄ " + right)





            tk.Button(d, text="删除选中配对", command=do_del, bg=C['danger'], fg="white",





                      font=("Microsoft YaHei", 9), relief="flat").pack(pady=5)























    def _del_alt(self):





        """删除替代料配对"""





        if not self.alt_pairs:





            messagebox.showinfo("提示", "当前没有替代料配对可删除")





            return





        d = tk.Toplevel(self.root)





        d.title("删除替代料配对")





        d.geometry("500x350")





        d.transient(self.root)





        d.grab_set()





        tk.Label(d, text="请选择要删除的配对：", font=("Microsoft YaHei", 10)).pack(pady=8)





        lst = tk.Listbox(d, font=("Consolas", 10), selectmode='single')





        lst.pack(fill="both", expand=True, padx=10)





        for a, b in self.alt_pairs:





            # a, b 都是 (factory, code, name) 元组





            factory_a, code_a, name_a = a if isinstance(a, tuple) else ('', a, '')





            factory_b, code_b, name_b = b if isinstance(b, tuple) else ('', b, '')





            left = f"{factory_a} {code_a} {name_a}"





            right = f"{factory_b} {code_b} {name_b}"





            lst.insert('end', left + " ⇄ " + right)





        if self.alt_pairs:





            lst.select_set(0)





        btn_frame = tk.Frame(d)





        btn_frame.pack(pady=10)





        def do_delete():





            sel = lst.curselection()





            if sel:





                del self.alt_pairs[sel[0]]





                save_alt_pairs(self.alt_pairs, log_cb=self.log)





                self._refresh_alt_view(self._alt_inner)





                d.destroy()





            else:





                messagebox.showwarning("提示", "请先选择要删除的配对")





        tk.Button(btn_frame, text="删除", command=do_delete, bg=C['danger'], fg="white",





                  font=("Microsoft YaHei", 10), relief="flat", width=10).pack(side="left", padx=5)





        tk.Button(btn_frame, text="取消", command=d.destroy, bg="#d0d7de",





                  font=("Microsoft YaHei", 10), relief="flat", width=10).pack(side="left", padx=5)

















    def _reset_alt(self):





        self.alt_pairs = []   # 清空替代料配对





        # 刷新界面显示





        canvas = self.alt_list_frame.winfo_children()[0]





        inner = canvas.winfo_children()[0]





        self._refresh_alt_view(inner)





        # 保存到配置文件





        save_alt_pairs(self.alt_pairs, log_cb=self.log)





        





























    def _refresh_alt_view(self, inner):





        for w in inner.winfo_children():





            w.destroy()





        for a, b in self.alt_pairs:





            # 期望 a, b 都是 (factory, code, name) 格式





            if isinstance(a, (list, tuple)) and len(a) >= 3:





                a_factory, a_code, a_name = a[0], a[1], a[2]





            else:





                a_factory, a_code, a_name = '', str(a), ''





            if isinstance(b, (list, tuple)) and len(b) >= 3:





                b_factory, b_code, b_name = b[0], b[1], b[2]





            else:





                b_factory, b_code, b_name = '', str(b), ''





            # 将 None / 'None' 转为空字符串





            a_code = '' if a_code in (None, 'None') else str(a_code).strip()





            a_name = '' if a_name in (None, 'None') else str(a_name).strip()





            b_code = '' if b_code in (None, 'None') else str(b_code).strip()





            b_name = '' if b_name in (None, 'None') else str(b_name).strip()





            





            # 显示：编码 + 名称（若名称存在）





            a_disp = f"{a_code} {a_name}" if a_name else a_code





            b_disp = f"{b_code} {b_name}" if b_name else b_code





            





            fr = tk.Frame(inner, bg=C['surface2'])





            fr.pack(fill="x", pady=1)





            tk.Label(fr, text=f"↔ {a_disp}", font=("Consolas", 8), fg=C['text'],





                     bg=C['surface2'], anchor="w").pack(side="left", padx=4)





            tk.Label(fr, text="|", font=("Consolas", 8), fg=C['text_dim'],





                     bg=C['surface2']).pack(side="left")





            tk.Label(fr, text=b_disp, font=("Consolas", 8), fg=C['purple'],





                     bg=C['surface2'], anchor="w").pack(side="left", padx=4)

















    def _show_alt_snapshot(self):





        """显示替代料配置的JSON快照（基于 alt_manager 动态路径）"""





        from domain.alt_material.alt_manager import _get_config_path











        config_path = _get_config_path()





        if not os.path.exists(config_path):





            messagebox.showinfo("提示",





                f"未找到配置文件：\n{config_path}\n\n当前使用默认内置替代料数据。")





            return











        try:





            with open(config_path, 'r', encoding='utf-8') as f:





                content = f.read()





            parsed = json.loads(content)





            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)





        except Exception as e:





            messagebox.showerror("读取失败", f"无法解析 JSON 文件：\n{e}")





            return











        win = tk.Toplevel(self.root)





        win.title(f"替代料快照 - {os.path.basename(config_path)}")





        win.geometry("750x550")











        frame = tk.Frame(win)





        frame.pack(fill='both', expand=True, padx=10, pady=10)











        scroll = tk.Scrollbar(frame)





        scroll.pack(side='right', fill='y')











        text = tk.Text(frame, wrap='none', yscrollcommand=scroll.set,





                       font=('Consolas', 10))





        text.pack(side='left', fill='both', expand=True)





        scroll.config(command=text.yview)











        text.insert('end', formatted)





        text.config(state='disabled')











        def copy_to_clip():





            win.clipboard_clear()





            win.clipboard_append(formatted)





            messagebox.showinfo("已复制", "JSON 内容已复制到剪贴板")











        tk.Button(win, text="复制到剪贴板", command=copy_to_clip,





                 font=("Microsoft YaHei", 10), relief="flat",





                 bg=C['accent'], fg="white").pack(pady=8)











    def _import_bom(self):





        """导入 BOM 数据文件，与旧 BOM 比对差异"""





        file_path = filedialog.askopenfilename(





            title="选择 BOM 数据文件",





            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")]





        )





        if not file_path:





            return





        try:





            self.log(f"📦 正在读取 BOM 文件：{os.path.basename(file_path)}", "info")





            new_df = pd.read_excel(file_path, sheet_name=0)





            self.log(f"   共读取 {len(new_df)} 行数据", "info")





        except Exception as e:





            messagebox.showerror("读取失败", f"无法读取 BOM 文件：{e}")





            return











        # ── 查找物料编码键 ──





        key_candidates = ['组件物料号', '物料编码', '物料号', '物料', 'code', 'material_code']





        key_col = None





        for col in key_candidates:





            if col in new_df.columns:





                key_col = col





                break





        if not key_col:





            cols_str = '、'.join(new_df.columns[:10].tolist())





            messagebox.showerror("列缺失", f"未找到物料编码列（候选：{key_candidates}）\n当前列：{cols_str}")





            return





        self.log(f"   物料编码键列：{key_col}", "info")











        # 清洗新数据





        new_df[key_col] = new_df[key_col].astype(str).str.strip()





        new_records = new_df.to_dict('records')





        new_keys = set(new_df[key_col].dropna().unique())











        # ── 加载旧 BOM ──





        old_path = self._get_bom_stored_path()





        old_records = []





        old_keys = set()





        old_key_col = key_col  # 默认使用新文件的key列





        added_count, removed_count, modified_count = 0, 0, 0





        detail_lines = []











        if os.path.exists(old_path):





            try:





                with open(old_path, 'r', encoding='utf-8') as f:





                    old_data = json.load(f)





                if isinstance(old_data, dict) and 'records' in old_data:





                    old_records = old_data['records']





                    # 使用旧BOM保存时的key列名（兼容新旧格式不一致的情况）





                    old_key_col = old_data.get('key_column', key_col)





                elif isinstance(old_data, list):





                    old_records = old_data





                    old_key_col = key_col





                else:





                    old_key_col = key_col





                old_keys = {str(r.get(old_key_col, '')).strip() for r in old_records if r.get(old_key_col)}





                self.log(f"   旧 BOM 共 {len(old_records)} 条记录", "info")





            except Exception as e:





                self.log(f"   旧 BOM 读取失败（将视为全新导入）：{e}", "warning")











        # ── 比对 ──





        if not old_keys:





            added_count = len(new_keys)





            detail_lines.append(f"🆕 全新导入，共 {added_count} 条新记录")





        else:





            added_keys = new_keys - old_keys





            removed_keys = old_keys - new_keys





            modified_count = 0











            # 快速修改检测（旧记录转dict）





            old_map = {str(r.get(old_key_col, '')).strip(): r for r in old_records if r.get(old_key_col)}





            for key in new_keys & old_keys:





                new_row = new_df[new_df[key_col] == key].iloc[0]





                old_row = old_map.get(key, {})





                changed = False





                for c in new_df.columns:





                    if c == key_col:





                        continue





                    new_val = str(new_row.get(c, '')).strip()





                    old_val = str(old_row.get(c, '')).strip()





                    if new_val != old_val:





                        changed = True





                        break





                if changed:





                    modified_count += 1











            added_count = len(added_keys)





            removed_count = len(removed_keys)











            if added_count > 0:





                sample_added = list(added_keys)[:5]





                detail_lines.append(f"🆕 新增 {added_count} 条（示例：{', '.join(sample_added)}）")





            if removed_count > 0:





                sample_removed = list(removed_keys)[:5]





                detail_lines.append(f"➖ 删除 {removed_count} 条（示例：{', '.join(sample_removed)}）")





            if modified_count > 0:





                detail_lines.append(f"✏️ 修改 {modified_count} 条")











        # ── 保存新 BOM ──





        bom_store = {





            'version': '1.0',





            'imported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),





            'key_column': key_col,





            'total_rows': len(new_df),





            'records': new_records





        }





        try:





            with open(old_path, 'w', encoding='utf-8') as f:





                json.dump(bom_store, f, ensure_ascii=False, indent=2)





            self.log(f"   BOM 已保存至：{old_path}", "info")





        except Exception as e:





            messagebox.showerror("保存失败", f"无法保存 BOM 数据：{e}")





            return











        # ── 展示对比报告 ──





        report_win = tk.Toplevel(self.root)





        report_win.title("BOM 导入报告")





        report_win.geometry(self.config.get("ui.bom_report_size", "600x400"))





        report_win.transient(self.root)





        report_win.grab_set()





        report_win.update_idletasks()





        w, h = 600, 400





        x = (report_win.winfo_screenwidth() - w) // 2





        y = (report_win.winfo_screenheight() - h) // 2





        report_win.geometry(f'{w}x{h}+{x}+{y}')











        bg_frame = Frame(report_win, bg='#1e1e1e')





        bg_frame.pack(fill='both', expand=True)











        title_label = Label(bg_frame, text="📦 BOM 导入报告", font=('微软雅黑', 14, 'bold'),





                            bg='#1e1e1e', fg='#ffffff')





        title_label.pack(pady=(20, 10))











        summary_text = f"文件：{os.path.basename(file_path)}\n"





        summary_text += f"总行数：{len(new_df)}　｜　"





        summary_text += f"🆕新增 {added_count}　｜　"





        summary_text += f"➖删除 {removed_count}　｜　"





        summary_text += f"✏️修改 {modified_count}"





        summary_label = Label(bg_frame, text=summary_text, font=('微软雅黑', 10),





                              bg='#1e1e1e', fg='#cccccc', justify='left', anchor='w')





        summary_label.pack(padx=20, fill='x')











        canvas = Canvas(bg_frame, bg='#1e1e1e', highlightthickness=0)





        scrollbar = Scrollbar(bg_frame, orient='vertical', command=canvas.yview)





        content_frame = Frame(canvas, bg='#1e1e1e')











        canvas.configure(yscrollcommand=scrollbar.set)





        canvas.pack(side='left', fill='both', expand=True, padx=(20, 0), pady=10)





        scrollbar.pack(side='right', fill='y', pady=10, padx=(0, 20))











        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor='nw')





        content_frame.bind('<Configure>',





                           lambda e: canvas.configure(scrollregion=canvas.bbox('all')))





        canvas.bind('<Configure>',





                    lambda e: canvas.itemconfig(canvas_window, width=e.width))











        if detail_lines:





            for line in detail_lines:





                color = '#1a7f37' if '新增' in line else ('#d29922' if '删除' in line else '#79c0ff')





                lbl = Label(content_frame, text=line, font=('微软雅黑', 10),





                            bg='#1e1e1e', fg=color, anchor='w', justify='left')





                lbl.pack(anchor='w', pady=2)





        else:





            Label(content_frame, text="✓ 无变更（数据完全一致）", font=('微软雅黑', 10),





                  bg='#1e1e1e', fg='#1a7f37', anchor='w').pack(anchor='w', pady=2)











        close_btn = Button(bg_frame, text="关闭", font=('微软雅黑', 10),





                           bg='#3a3a3a', fg='#ffffff', activebackground='#555555',





                           command=report_win.destroy, cursor='hand2')





        close_btn.pack(pady=15)











        self.log(f"📦 BOM 导入完成：新增 {added_count} / 删除 {removed_count} / 修改 {modified_count}", "info")





        self.log(f"   BOM 数据已保存，下次过期检查将自动对比差异", "info")

















    def _run_pre_check(self):





        """完整预检报告：列完整性 + 重复订单 + 数值异常 + 替代料配置 + 弹窗"""





        try:





            input_path = self.input_file.get()





            if not input_path or not os.path.exists(input_path):





                self.log("预检失败：输入文件不存在", "error")





                messagebox.showwarning("预检失败", "请先选择输入文件")





                return











            df = pd.read_excel(input_path, sheet_name='Data', nrows=self.config.get('precheck.sample_rows', 1000))





            results = []











            # 1. 列完整性检查（黄金模板）





            golden_cols = self.config.get('precheck.golden_columns', [





                '流程订单', '订单开始日期', '组件物料号', '组件物料描述',





                '组件数量', '单位', '工厂名称', '生产管理员描述'





            ])





            missing_cols = [col for col in golden_cols if col not in df.columns]





            if missing_cols:





                results.append(('严重', f'缺失标准列：{", ".join(missing_cols)}'))





            else:





                results.append(('通过', '黄金模板列完整'))











            # 2. 重复订单检查（日期 + 流程订单 + 物料编码 联合去重）





            date_col = None





            for col in ['订单开始日期', '订单日期', '日期']:





                if col in df.columns:





                    date_col = col





                    break





            # 确定物料编码列名





            mat_col = None





            for col in ['物料编码', '组件物料号', '物料号', '编码']:





                if col in df.columns:





                    mat_col = col





                    break





            if date_col and '流程订单' in df.columns and mat_col:





                df['_check_date'] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')





                dup_mask = df.duplicated(subset=['_check_date', '流程订单', mat_col], keep=False)





                dup_orders = df[dup_mask]





                if not dup_orders.empty:





                    dup_groups = dup_orders.groupby(['_check_date', '流程订单', mat_col]).ngroups





                    results.append(('警告', f'发现 {len(dup_orders)} 条重复记录（{dup_groups} 组重复），请检查 SAP 导出是否重复'))





                else:





                    results.append(('通过', '无重复记录（日期+订单+物料）'))





                df.drop(columns=['_check_date'], inplace=True)





            else:





                missing = []





                if not date_col: missing.append('日期列')





                if '流程订单' not in df.columns: missing.append('流程订单')





                if not mat_col: missing.append('物料编码/组件物料号')





                results.append(('警告', f'缺少必要列（{", ".join(missing)}），无法检测重复订单'))











            # 3. 数值异常检查





            if '组件数量' in df.columns:





                neg_quota = df[df['组件数量'] < 0]





                if not neg_quota.empty:





                    results.append(('警告', f'发现 {len(neg_quota)} 行定额为负数'))





                else:





                    results.append(('通过', '定额无负数'))











            # 4. 替代料配置检查





            try:





                from domain.alt_material.alt_manager import _get_config_path, load_alt_pairs





                alt_path = _get_config_path()





                if not os.path.exists(alt_path):





                    results.append(('警告', '替代料配置文件不存在，将使用内置配对'))





                else:





                    alt_pairs = load_alt_pairs(log_cb=self.log)





                    results.append(('通过', f'替代料配置加载成功，共 {len(alt_pairs)} 组配对'))





            except Exception as e:





                results.append(('严重', f'替代料配置加载失败：{e}'))











            # 5. 黄金模板对比





            try:





                gold_cols = self._load_golden_columns()





                if gold_cols:





                    actual_cols = set(df.columns)





                    template_cols = set(gold_cols)





                    missing = template_cols - actual_cols





                    extra = actual_cols - template_cols





                    if missing:





                        results.append(('严重', f'黄金模板缺失列：{", ".join(sorted(missing))}'))





                    if extra:





                        results.append(('警告', f'黄金模板多出列：{", ".join(sorted(extra))}'))





                    if not missing and not extra:





                        results.append(('通过', '黄金模板列结构完全匹配'))





                else:





                    results.append(('警告', '尚未设置黄金模板，跳过列结构对比'))





            except Exception as e:





                results.append(('警告', f'黄金模板对比失败：{e}'))











            # 汇总到日志





            self.log("📋 数据预检报告：", "info")





            for severity, msg in results:





                self.log(f" [{severity}] {msg}", severity if severity in ("通过", "警告", "严重") else "info")











            # 弹窗显示





            self._show_pre_check_report(results)











        except Exception as e:





            self.log(f"预检失败：{e}", "error")





            messagebox.showerror("预检错误", f"预检过程中发生错误：{str(e)}")











    def _load_golden_columns(self):





        """加载黄金模板列名（从配置文件，若不存在返回None）"""





        try:





            gold_path = os.path.join(os.path.expanduser('~'), '.zpp011_audit', 'golden_columns.json')





            if not os.path.exists(gold_path):





                return None





            with open(gold_path, 'r', encoding='utf-8') as f:





                return json.load(f)





        except Exception:





            return None











    def _show_pre_check_report(self, results):
        """显示预检报告（系统检查 + 数据统计），配置化列名，防御缺失列"""
        win = tk.Toplevel(self.root)
        win.title("数据预检报告")
        win.geometry("600x500")
        win.transient(self.root)
        win.grab_set()

        text = tk.Text(win, wrap="word", font=("Consolas", 10), padx=10, pady=10)
        text.pack(fill="both", expand=True)

        text.tag_configure("严重", foreground="#cf222e")
        text.tag_configure("警告", foreground="#d29922")
        text.tag_configure("通过", foreground="#1a7f37")
        text.tag_configure("标题", font=("Consolas", 12, "bold"))

        # 1. 系统检查结果
        text.insert("end", "系统检查结果\n", "标题")
        for level, msg in results:
            tag = "严重" if level == "严重" else ("警告" if level == "警告" else "通过")
            text.insert("end", msg + "\n", tag)

        # 2. 数据统计信息（配置化列名 + 防御）
        if self.audit_data is not None and not self.audit_data.empty:
            text.insert("end", "\n数据统计\n", "标题")

            # 从配置读取列名
            bias_rate_col = self.config.get('columns.bias_rate', '偏差率(%)')
            audit_status_col = self.config.get('columns.audit_status', '审核状态')

            try:
                # 检查必要列是否存在
                if bias_rate_col not in self.audit_data.columns:
                    text.insert("end", f"警告：缺少列 '{bias_rate_col}'，无法统计偏差分布。\n", "警告")
                    stats_available = False
                else:
                    stats_available = True
            except Exception as e:
                text.insert("end", f"统计计算出错：{e}\n", "严重")
                stats_available = False

            if stats_available:
                total = len(self.audit_data)
                high_dev = (self.audit_data[bias_rate_col].abs() > 10).sum()
                mid_dev = ((self.audit_data[bias_rate_col].abs() >= 5) & (self.audit_data[bias_rate_col].abs() <= 10)).sum()
                low_dev = (self.audit_data[bias_rate_col].abs() < 5).sum()

                # 审核状态列可能不存在，尝试获取
                if audit_status_col in self.audit_data.columns:
                    reviewed = (self.audit_data[audit_status_col] == '已审核').sum()
                    unreviewed = total - reviewed
                else:
                    reviewed = unreviewed = 0
                    text.insert("end", "警告：缺少审核状态列，审核统计显示为0。\n", "警告")

                stats = f"总行数：{total}\n"
                stats += f"偏差异常（≥10%）：{high_dev}\n"
                stats += f"偏差关注（5%-10%）：{mid_dev}\n"
                stats += f"偏差正常（<5%）：{low_dev}\n"
                stats += f"已审核：{reviewed}\n"
                stats += f"未审核：{unreviewed}"
                text.insert("end", stats + "\n", "通过")
        else:
            text.insert("end", "\n数据统计\n无数据\n", "标题")

        text.configure(state="disabled")

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)
        if hasattr(self, '_duplicate_records') and hasattr(self._duplicate_records, 'empty') and not self._duplicate_records.empty:
            tk.Button(btn_frame, text="导出重复数据", command=self._export_duplicate_records,
                      bg="#f0f0f0", font=("Microsoft YaHei", 9)).pack(side="left", padx=5)
        tk.Button(btn_frame, text="关闭", command=win.destroy, width=10).pack(side="left", padx=5)
    def _export_duplicate_records(self):





        if not hasattr(self, '_duplicate_records') or not hasattr(self._duplicate_records, 'empty') or self._duplicate_records.empty:





            return





        file_path = filedialog.asksaveasfilename(





            defaultextension=".xlsx",





            filetypes=[("Excel 文件", "*.xlsx")],





            initialfile="重复订单记录.xlsx"





        )





        if not file_path:





            return





        try:





            from openpyxl import Workbook





            from openpyxl.styles import PatternFill





            df = self._duplicate_records.copy()





            if '流程订单' in df.columns and '物料编码' in df.columns:





                df = df.sort_values(['流程订单', '物料编码'])





            wb = Workbook()





            ws = wb.active





            ws.title = "重复记录"





            headers = list(df.columns)





            for col_idx, h in enumerate(headers, 1):





                ws.cell(1, col_idx, h)





            colors = ["FFCCCC", "FFE5CC", "FFFFCC", "CCFFCC", "CCE5FF", "E5CCFF", "FFCCE5", "E5E5E5"]





            group_colors = {}





            group_idx = 0





            last_group = None





            for row_idx, (_, row) in enumerate(df.iterrows(), 2):





                if '流程订单' in df.columns and '物料编码' in df.columns:





                    group_key = (row['流程订单'], row['物料编码'])





                    if group_key != last_group:





                        group_idx += 1





                        last_group = group_key





                        group_colors[group_key] = colors[(group_idx - 1) % len(colors)]





                    fill_color = group_colors.get(group_key, "FFFFFF")





                else:





                    fill_color = "FFFFFF"





                for col_idx, val in enumerate(row, 1):





                    cell = ws.cell(row_idx, col_idx, val)





                    if fill_color != "FFFFFF":





                        cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")





            wb.save(file_path)





            self.log(f"重复数据已导出：{file_path}", "success")





            messagebox.showinfo("导出成功", "已导出到：" + file_path)





        except Exception as e:





            self.log(f"导出重复数据失败：{e}", "error")





            messagebox.showerror("导出失败", str(e))











    # ==================== 菜单初始化 ====================





    def _show_tree_view(self):





        """在新窗口中以树形结构展示审核数据"""





        if self.audit_data is None or self.audit_data.empty:





            messagebox.showwarning("提示", "没有可展示的数据")





            return











        # 创建新窗口





        win = tk.Toplevel(self.root)





        win.title("偏差数据 - 树形视图")





        win.geometry("1000x650")





        win.transient(self.root)





        win.grab_set()











        # Treeview





        tree = ttk.Treeview(win, show="tree headings",





                            columns=("code", "name", "order_date", "quota", "actual", "dev_rate", "status", "remark"),





                            height=25)





        tree.heading("#0", text="工厂 / 车间 / 物料分类")





        tree.heading("code", text="物料号")





        tree.heading("name", text="物料描述")





        tree.heading("order_date", text="订单日期")





        tree.heading("quota", text="定额")





        tree.heading("actual", text="实际")





        tree.heading("dev_rate", text="偏差率%")





        tree.heading("status", text="状态")





        tree.heading("remark", text="备注")











        tree.column("#0", width=220)





        tree.column("code", width=70, anchor="center")





        tree.column("name", width=100, anchor="w")





        tree.column("order_date", width=70, anchor="center")





        tree.column("quota", width=50, anchor="e")





        tree.column("actual", width=50, anchor="e")





        tree.column("dev_rate", width=55, anchor="center")





        tree.column("status", width=55, anchor="center")





        tree.column("remark", width=80, anchor="w")











        scroll = ttk.Scrollbar(win, command=tree.yview)





        tree.configure(yscrollcommand=scroll.set)





        tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)





        scroll.pack(side="right", fill="y", pady=10)











        # 灵活确定列名





        groupby_factory = next((c for c in ['工厂', '工厂名称'] if c in self.audit_data.columns), None)





        groupby_workshop = next((c for c in ['车间', '生产管理员描述'] if c in self.audit_data.columns), None)





        groupby_category = next((c for c in ['物料类型', '物料分类'] if c in self.audit_data.columns), None)





        code_col = next((c for c in ['物料编码', '组件物料号'] if c in self.audit_data.columns), '物料编码')





        name_col = next((c for c in ['物料名称', '组件物料描述'] if c in self.audit_data.columns), '物料名称')





        quota_col = next((c for c in ['定额', '数量-定额'] if c in self.audit_data.columns), '定额')





        actual_col = next((c for c in ['实际', '数量-实际'] if c in self.audit_data.columns), '实际')





        dev_col = next((c for c in ['偏差率', '偏差率(%)'] if c in self.audit_data.columns), '偏差率')





        remark_col = next((c for c in ['备注', '备注原因'] if c in self.audit_data.columns), '备注')











        if not groupby_factory:





            messagebox.showwarning("提示", "数据中未找到工厂列，无法生成树形视图")





            win.destroy()





            return











        for factory, f_grp in self.audit_data.groupby(groupby_factory):





            factory_id = tree.insert('', 'end', text=factory, open=False)











            if groupby_workshop and groupby_category:





                for (workshop, mat_cat), w_grp in f_grp.groupby([groupby_workshop, groupby_category]):





                    workshop_id = tree.insert(factory_id, 'end',





                                              text=f"{workshop} - {mat_cat}  ({len(w_grp)}条)",





                                              open=False)





                    self._insert_tree_rows(tree, workshop_id, w_grp, code_col, name_col, quota_col, actual_col, dev_col, remark_col)





            elif groupby_workshop:





                for workshop, w_grp in f_grp.groupby(groupby_workshop):





                    workshop_id = tree.insert(factory_id, 'end',





                                              text=f"{workshop}  ({len(w_grp)}条)",





                                              open=False)





                    self._insert_tree_rows(tree, workshop_id, w_grp, code_col, name_col, quota_col, actual_col, dev_col, remark_col)





            else:





                for _, row in f_grp.iterrows():





                    self._insert_tree_rows(tree, factory_id, f_grp, code_col, name_col, quota_col, actual_col, dev_col, remark_col)





                break











        self.log("[OK] tree view opened", "info")











    def _insert_tree_rows(self, tree, parent_id, grp, code_col, name_col, quota_col, actual_col, dev_col, remark_col):





        """向树形视图插入行数据"""





        for _, row in grp.iterrows():





            tree.insert(parent_id, 'end',





                        text=str(row.get(name_col, ''))[:20],





                        values=(





                            str(row.get(code_col, '')),





                            str(row.get(name_col, ''))[:20],





                            str(row.get('订单日期', ''))[:12] if pd.notna(row.get('订单日期')) else '',





                            f"{row.get(quota_col, 0):.3f}" if pd.notna(row.get(quota_col)) else '-',





                            f"{row.get(actual_col, 0):.3f}" if pd.notna(row.get(actual_col)) else '-',





                            f"{row.get(dev_col, 0):.2f}%" if pd.notna(row.get(dev_col)) else '-',





                            row.get('_audit_status', '未审核'),





                            str(row.get(remark_col, ''))[:20]





                        ))











    # ── 以下为 v30 原有的全部方法，必须完整复制到此处 ────────





    # 方法列表（请从原 v30.py 中逐个复制，确保不遗漏）：





    # _refresh_alt_view, _add_alt, _del_alt, _reset_alt,





    # _get_config_path, _save_alt_pairs, _load_alt_pairs, _extract_alt_name,





    # _select_input, _select_output, _auto_find, _preview, log, _set_step,





    # start_analysis, _analysis_thread, _on_progress, _update_timer, request_cancel,





    # _on_done, _on_cancel, _on_error, _show_step_log, open_output,





    # generate_excel_direct, _generate_excel_thread, generate_ppt, _on_ppt_done, _on_ppt_error,





    # _load_audit_data, _apply_row_colors, _edit_audit_remark, _update_audit_stats,





    # _show_audit_context_menu, _filter_audit_tree, _update_filter_options,





    # _on_filter_changed, _reset_all_filters, _refresh_audit_tree,





    # _run_ai_audit, _export_audit_excel, _batch_change_status, _batch_fill_remark,





    # _batch_export, _add_custom_status, _load_custom_statuses, _save_custom_statuses





    # 注：上面这些方法的完整代码请从 v30.py 中全选复制，插入到此处。





    # 复制时注意保持缩进（全部与 _show_tree_view 对齐，class 内部缩进 4 空格）。











    # ── 以下方法从 v30.py 完整移植 ──











    def _get_resume_state_path(self):





        """获取断点状态文件路径"""





        app_dir = os.path.join(os.path.expanduser('~'), '.zpp011_audit')





        return os.path.join(app_dir, 'resume_state.json')











    def _load_resume_state(self):





        """加载断点状态"""





        path = self._get_resume_state_path()





        if not os.path.exists(path):





            return None





        try:





            with open(path, 'r', encoding='utf-8') as f:





                return json.load(f)





        except Exception:





            return None











    def _save_resume_state(self):





        """保存断点状态"""





        app_dir = os.path.join(os.path.expanduser('~'), '.zpp011_audit')





        os.makedirs(app_dir, exist_ok=True)





        path = self._get_resume_state_path()





        





        state = {}





        # 保存选择的行





        if hasattr(self, 'current_row_idx'):





            state['selected_row'] = self.current_row_idx





        # 保存搜索文字





        if hasattr(self, 'search_var'):





            state['search_text'] = self.search_var.get()





        # 保存筛选条件





        if hasattr(self, 'filter_widgets'):





            state['filter_values'] = {}





        





        try:





            with open(path, 'w', encoding='utf-8') as f:





                json.dump(state, f, ensure_ascii=False, indent=2)





        except Exception as e:





            self.log(f"保存断点失败：{e}", "warn")

















    def _do_resume_state(self):





        """一键恢复上次审核状态"""





        state = self._load_resume_state()





        if not state:





            return





        # 恢复搜索文字





        search_text = state.get('search_text', '')





        if search_text and hasattr(self, 'search_var'):





            self.search_var.set(search_text)





        # 恢复筛选条件





        filters = state.get('filter_values', {})





        for key, value in filters.items():





            if key in self.filter_widgets:





                widget = self.filter_widgets[key]





                if key == 'name':





                    widget.delete(0, tk.END)





                    widget.insert(0, value)





                elif key == 'order_date':





                    if isinstance(widget, tuple) and len(widget) == 2 and isinstance(value, list) and len(value) == 2:





                        widget[0].delete(0, tk.END)





                        widget[0].insert(0, value[0])





                        widget[1].delete(0, tk.END)





                        widget[1].insert(0, value[1])





                else:





                    widget.set(value)





        # 重新触发筛选





        self._on_filter_changed('restore')





        # 恢复选中行





        saved_row = state.get('selected_row')





        if saved_row:





            children = self.audit_tree.get_children()





            if int(saved_row) <= len(children):





                self.audit_tree.selection_set(children[int(saved_row) - 1])





                self.audit_tree.see(children[int(saved_row) - 1])





        self.resume_btn.configure(state="disabled")





        self.log("✅ 已恢复上次审核进度", "success")

















    def _select_input(self):





        default_dir = os.path.join(os.path.expanduser("~"), "ZPP011导出文件原数据")





        os.makedirs(default_dir, exist_ok=True)





        p = filedialog.askopenfilename(





            title="选择 ZPP011 数据文件",





            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")],





            initialdir=default_dir)











        if p:





            self.input_file.set(p)











            self._preview()

















    def _select_output(self):





        p = filedialog.askdirectory(title="选择输出目录")











        if p:





            self.output_dir.set(p)

















    def _auto_find(self):





        for pattern in ['zpp011 *.xlsx', 'ZPP011 *.xlsx']:





            hits = _glob.glob(os.path.join(os.getcwd(), pattern))











            if hits:





                hits.sort(key=os.path.getmtime, reverse=True)











                self.input_file.set(hits[0])











                self._preview()











                return











            hits = _glob.glob(





                os.path.join(





                    os.path.expanduser('~'),





                    'Desktop',





                    pattern))











            if hits:





                hits.sort(key=os.path.getmtime, reverse=True)











                self.input_file.set(hits[0])











                self._preview()











                return

















    def _preview(self):





        path = self.input_file.get()











        if not path or not os.path.exists(path):





            self.preview_lbl.configure(text="❌ 文件不存在", fg=C['danger'])











            return











        try:





            df = pd.read_excel(path, sheet_name='Data', nrows=5)











            total = pd.read_excel(path, sheet_name='Data').shape[0]











            cols = df.columns.tolist()











            self.preview_lbl.configure(











                text=f"✅ {os.path.basename(path)}\n"











                f"   总行数：{total:,}  行\n"











                f"   替代料配对：{len(self.alt_pairs)}  组\n"











                f"   列数：{len(cols)}",











                fg=C['green'], justify="left"











            )











        except Exception as e:





            self.preview_lbl.configure(text=f"❌ 读取失败：{e}", fg=C['danger'])











        # 刷新物料列表（供替代料添加对话框下拉使用）





        self._load_material_list()

















    def _set_step(self, idx, done=True):





        fr_data = self.step_frames.get(idx)











        if not fr_data:





            return











        fr = fr_data['frame']











        lbl = fr.winfo_children()[0]











        color = C['green'] if done else (





            C['accent'] if idx == self._current_step else C['text_dim'])











        lbl.configure(bg=color, fg="white" if done else C['text_dim'])











        fr.configure(bg=color, relief="flat" if done else "flat")

















    def _show_step_log(self, idx):





        pass











    def _load_lock_state(self):





        return {}











    def _save_lock_state(self, locked):





        """保存列宽锁定状态"""





        try:





            from gui.ui_builder import COLUMN_WIDTHS_FILE





            state_path = COLUMN_WIDTHS_FILE.replace('column_widths.json', 'lock_state.json')





            os.makedirs(os.path.dirname(state_path), exist_ok=True)





            with open(state_path, 'w', encoding='utf-8') as f:





                json.dump({'locked': locked}, f)





        except Exception:





            pass











    def _on_close(self):





        """窗口关闭前保存断点状态"""





        try:





            self._save_resume_state()





            self.log("断点已保存", "success")





        except Exception as e:





            self.log(f"断点保存失败：{e}", "warn")





        # 保存列宽 + 窗口几何





        try:





            if hasattr(self, 'audit_tree'):





                widths = {}





                for col in self.audit_tree['columns']:





                    widths[col] = self.audit_tree.column(col, 'width')





                self.config.set('table.column_widths', widths)





            self.config.save_window_geometry(self.root)





        except Exception:





            pass





        self.root.destroy()

















    def update_progress(self, percent: int, message: str = ''):





        """更新进度条（供 Presenter 调用）"""





        self.root.after(0, lambda: [





            self.progress_var.set(percent),





            self.progress_lbl.configure(text=message) if hasattr(self, 'progress_lbl') else None





        ])











    def refresh_treeview(self, df=None):





        """刷新 Treeview（供 Presenter 调用）"""





        if df is not None:





            self.audit_data = df





        self.root.after(0, lambda: self._refresh_audit_tree(self.audit_data) if hasattr(self, '_refresh_audit_tree') else None)











    def show_error(self, msg: str, title: str = '错误'):





        """显示错误对话框（供 Presenter 调用）"""





        from tkinter import messagebox





        self.root.after(0, lambda: messagebox.showerror(title, msg))











    def show_info(self, msg: str, title: str = '提示'):





        """显示信息对话框（供 Presenter 调用）"""





        from tkinter import messagebox





        self.root.after(0, lambda: messagebox.showinfo(title, msg))











    def log_message(self, msg: str, level: str = 'info'):





        """记录日志（供 Presenter 调用）"""





        if hasattr(self, 'log'):





            self.log(msg, level)











    def set_buttons_state(self, state: str = 'normal', buttons: list = None):





        """设置按钮状态（供 Presenter 调用）"""





        if buttons is None:





            buttons = ['run_btn', 'save_btn', 'export_btn', 'ai_btn', 'auto_close_btn']





        for btn_name in buttons:





            btn = getattr(self, btn_name, None)





            if btn:





                try:





                    btn.configure(state=state)





                except:





                    pass











    def enable_buttons(self, buttons: list = None):





        """启用按钮"""





        self.set_buttons_state('normal', buttons)











    def disable_buttons(self, buttons: list = None):





        """禁用按钮"""





        self.set_buttons_state('disabled', buttons)











    def get_audit_data(self):





        """返回当前审核数据 DataFrame（供 Presenter 调用）"""





        return self.audit_data











    def get_output_path(self):





        """返回当前输出路径（供 Presenter 调用）"""





        return self.output_dir.get() if hasattr(self, 'output_dir') else ''











    def get_alt_pairs(self):





        """返回替代料配对列表（供 Presenter 调用）"""





        return getattr(self, 'alt_pairs', [])

