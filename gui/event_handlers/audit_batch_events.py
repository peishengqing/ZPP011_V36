# -*- coding: utf-8 -*-
"""批量操作 + 隔离区事件"""

import tkinter as tk
from tkinter import ttk, messagebox
import json, os
import pandas as pd
from core.decorators import with_feedback
from widgets import C

def _safe_for_gbk(text):
    if not text: return text
    result = []
    for c in text:
        try:
            c.encode('gbk')
            result.append(c)
        except UnicodeEncodeError:
            pass
    return ''.join(result)


class AuditBatchEvents:
    """批量操作 + 隔离区事件"""
    def _batch_change_status(self, event=None):





        """批量更改选中行的状态"""





        selected = self.audit_tree.selection()





        if not selected:





            messagebox.showwarning(_safe_for_gbk("提示"), _safe_for_gbk("请先选择要更改状态的行"))





            return











        status_options = ["已备注", "需补备注", "已确认", "待处理", "异常"]





        if hasattr(self, 'custom_statuses'):





            status_options += self.custom_statuses











        dialog = tk.Toplevel(self.root)





        dialog.title("批量更改状态")





        dialog.geometry("300x200")





        dialog.transient(self.root)





        dialog.grab_set()





        dialog.update_idletasks()





        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2





        y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2





        dialog.geometry(f"+{x}+{y}")











        tk.Label(dialog, text=f"选择新状态（将为 {len(selected)} 行数据更改）:",





                 font=("Microsoft YaHei", 10)).pack(pady=15)





        status_var = tk.StringVar(value=status_options[0])





        status_combo = ttk.Combobox(dialog, textvariable=status_var, values=status_options,





                                    state="readonly", width=20, font=("Microsoft YaHei", 10))





        status_combo.pack(pady=10)











        def apply_change():





            new_status = status_var.get()





            for item in selected:





                self.audit_tree.set(item, 'status', new_status)





                excel_row = int(self.audit_tree.set(item, 'excel_row'))





                if self.audit_data is not None:





                    mask = self.audit_data['excel_row'].astype(str) == str(excel_row)





                    if mask.any() and '备注原因' in self.audit_data.columns:





                        self.audit_data.loc[mask, '备注原因'] = new_status
                        self._invalidate_tag_cache()  # Task 007





            self._update_audit_stats()





            self._update_filter_options()





            messagebox.showinfo(_safe_for_gbk("完成"), _safe_for_gbk(f"已将 {len(selected)} 行状态更改为「{new_status}」"))


        # Audit log (Task 004)
        if hasattr(self, 'audit_logger'):
            self.audit_logger.log(
                action='batch_change_status',
                old_value=old_status,
                new_value=new_status,
                source='batch'
            )




            dialog.destroy()











        btn_frame = tk.Frame(dialog)





        btn_frame.pack(pady=20)





        tk.Button(btn_frame, text="确定", width=10, command=apply_change).pack(side="left", padx=10)





        tk.Button(btn_frame, text="取消", width=10, command=dialog.destroy).pack(side="left", padx=10)

















    def _batch_fill_remark(self, event=None):





        """批量填写备注"""





        selected = self.audit_tree.selection()





        if not selected:





            messagebox.showwarning(_safe_for_gbk("提示"), _safe_for_gbk("请先选择要填写备注的行"))





            return











        # P1：按使用频率排序的预设备注列表





        base_remarks = ["已核实，偏差正常", "已沟通，确认无误", "已调整，请复查", "待进一步确认", "替代料替换", "工艺调整", "库存调整", "其他原因"]





        sorted_remarks, _ = self._get_sorted_remarks(base_remarks)





        remark_options = sorted_remarks + ["(清空备注)"]





        if hasattr(self, 'custom_remarks'):





            remark_options = self.custom_remarks + remark_options











        dialog = tk.Toplevel(self.root)





        dialog.title("批量填写备注")





        dialog.geometry("320x180")





        dialog.transient(self.root)





        dialog.grab_set()





        x = self.root.winfo_x() + (self.root.winfo_width() - 320) // 2





        y = self.root.winfo_y() + (self.root.winfo_height() - 180) // 2





        dialog.geometry(f"+{x}+{y}")











        tk.Label(dialog, text=f"选择备注（将为 {len(selected)} 行填写）:",





                 font=("Microsoft YaHei", 10)).pack(pady=15)





        remark_var = tk.StringVar()





        remark_combo = ttk.Combobox(dialog, textvariable=remark_var, values=remark_options,





                                    width=28, font=("Microsoft YaHei", 10))





        remark_combo.pack(pady=10)





        remark_combo.focus()











        def apply_remark():





            remark = remark_var.get()

            # 检查是否选择了备注内容
            if not remark or remark == '——手动输入——':
                messagebox.showwarning(
                    _safe_for_gbk('提示'),
                    _safe_for_gbk('请从下拉框选择备注内容，或选择"——手动输入——"后输入自定义备注')
                )
                return





            if remark == "(清空备注)":





                remark = ""





            count = 0





            for item in selected:





                self.audit_tree.set(item, 'batch_remark', remark)  # 写入批量备注列





                excel_row = int(self.audit_tree.set(item, 'excel_row'))





                if self.audit_data is not None:





                    mask = self.audit_data['excel_row'].astype(str) == str(excel_row)





                    if mask.any():





                        # 优先写入批量备注列，兼容 fallback





                        batch_col = None





                        for col in ['批量备注原因', '批量备注']:





                            if col in self.audit_data.columns:





                                batch_col = col





                                break





                        if batch_col:





                            self.audit_data.loc[mask, batch_col] = remark





                            count += 1





                        elif '备注原因' in self.audit_data.columns:





                            self.audit_data.loc[mask, '备注原因'] = remark
                            self._invalidate_tag_cache()  # Task 007





                            count += 1





            self._record_remark_freq(remark_var.get())  # P1：记录频率





            self._update_audit_stats()





            self._update_filter_options()





            label = "清空" if not remark else f"「{remark}」"





            messagebox.showinfo(_safe_for_gbk("完成"), _safe_for_gbk(f"已为 {count if count else len(selected)} 行填写备注 {label}"))





            dialog.destroy()











        btn_frame = tk.Frame(dialog)





        btn_frame.pack(pady=15)





        tk.Button(btn_frame, text="确定", width=10, command=apply_remark).pack(side="left", padx=10)





        tk.Button(btn_frame, text="取消", width=10, command=dialog.destroy).pack(side="left", padx=10)











    @with_feedback("批量备注完成", "批量备注失败")





    def _batch_remark(self, event=None):





        """批量备注：为选中的行添加备注（下拉框选择，可追加换行）"""





        try:





            selected = self.audit_tree.selection()





            if not selected:





                messagebox.showinfo(_safe_for_gbk("提示"), _safe_for_gbk("请先选中要添加备注的行（可多选）"))





                return











            # P1：按使用频率排序的预设备注列表





            base_remarks = ["已核实，偏差正常", "已沟通，确认无误", "已调整，请复查", "待进一步确认", "替代料替换", "工艺调整", "库存调整", "其他原因"]





            sorted_remarks, _ = self._get_sorted_remarks(base_remarks)





            remark_options = sorted_remarks + ["(清空备注)", "——手动输入——"]





            if hasattr(self, 'custom_remarks'):





                remark_options = self.custom_remarks + remark_options











            dialog = tk.Toplevel(self.root)





            dialog.title("批量备注")





            dialog.geometry("360x200")





            dialog.transient(self.root)





            dialog.grab_set()





            x = self.root.winfo_x() + (self.root.winfo_width() - 360) // 2





            y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2





            dialog.geometry(f"+{x}+{y}")











            tk.Label(dialog, text=f"选择备注（将为 {len(selected)} 行填写）:",





                     font=("Microsoft YaHei", 10)).pack(pady=10)











            remark_var = tk.StringVar()





            remark_combo = ttk.Combobox(dialog, textvariable=remark_var, values=remark_options,





                                        width=36, font=("Microsoft YaHei", 10), state="readonly")





            remark_combo.pack(pady=8)





            remark_combo.focus()











            # 手动输入框（默认隐藏）





            input_frame = tk.Frame(dialog)





            input_frame.pack(pady=4)





            custom_entry = ttk.Entry(input_frame, width=36, font=("Microsoft YaHei", 10))





            custom_entry.pack()





            input_frame.pack_forget()  # 默认隐藏











            # 监听选择变化，切换手动输入框





            def on_combo_change(*args):





                if remark_var.get() == "——手动输入——":





                    input_frame.pack(pady=4)





                    custom_entry.focus()





                else:





                    input_frame.pack_forget()











            remark_combo.bind("<<ComboboxSelected>>", on_combo_change)











            def apply_remark():





                remark = remark_var.get()





                if remark == "(清空备注)":





                    remark = ""





                elif remark == "——手动输入——":





                    remark = custom_entry.get().strip()





                    if not remark:





                        messagebox.showwarning(_safe_for_gbk("提示"), _safe_for_gbk("请输入备注内容"))





                        return





                if not remark:





                    return











                # 确定 DataFrame 中的备注列名（优先批量备注列）





                df_remark_col = None





                for col in ['批量备注原因', '批量备注']:





                    if col in self.audit_data.columns:





                        df_remark_col = col





                        break





                if df_remark_col is None:





                    df_remark_col = "批量备注"





                    self.audit_data[df_remark_col] = ""











                # 使用 excel_row 定位，构建 item->df_idx 映射





                item_to_idx = {}





                for item in selected:





                    excel_row = int(self.audit_tree.set(item, 'excel_row'))





                    mask = self.audit_data['excel_row'].astype(str) == str(excel_row)





                    if mask.any():





                        item_to_idx[item] = mask.idxmax()











                if not item_to_idx:





                    messagebox.showwarning(_safe_for_gbk("警告"), _safe_for_gbk("无法定位选中行，请刷新重试"))





                    return











                # 追加备注（换行连接，区分符 /）





                count = 0





                for item, idx in item_to_idx.items():





                    self.audit_tree.set(item, 'batch_remark', remark)  # 刷新树形列





                    current = self.audit_data.at[idx, df_remark_col]





                    if pd.notna(current) and str(current).strip():





                        self.audit_data.at[idx, df_remark_col] = f"{current}\n/{remark}"





                    else:





                        self.audit_data.at[idx, df_remark_col] = remark





                    count += 1











                self._record_remark_freq(remark)  # P1：记录频率





                self._refresh_audit_tree(self.audit_data)





                self._update_audit_stats()





                self._update_filter_options()





                label = "清空" if not remark else f"「{remark}」"





                messagebox.showinfo(_safe_for_gbk("完成"), _safe_for_gbk(f"已为 {count} 行添加备注 {label}"))


        # Audit log (Task 004)




                dialog.destroy()











            btn_frame = tk.Frame(dialog)





            btn_frame.pack(pady=10)





            tk.Button(btn_frame, text="确定", width=10, command=apply_remark).pack(side="left", padx=10)





            tk.Button(btn_frame, text="取消", width=10, command=dialog.destroy).pack(side="left", padx=10)











        except Exception as e:





            import traceback





            traceback.print_exc()





            messagebox.showerror(_safe_for_gbk("错误"), _safe_for_gbk(f"批量备注失败：{str(e)}"))











    def _add_custom_status(self, event=None):





        """添加自定义状态标签"""





        dialog = tk.Toplevel(self.root)





        dialog.title("添加状态标签")





        dialog.geometry("280x140")





        dialog.transient(self.root)





        dialog.grab_set()





        x = self.root.winfo_x() + (self.root.winfo_width() - 280) // 2





        y = self.root.winfo_y() + (self.root.winfo_height() - 140) // 2





        dialog.geometry(f"+{x}+{y}")











        tk.Label(dialog, text="输入新状态标签名称：", font=("Microsoft YaHei", 10)).pack(pady=10)





        name_var = tk.StringVar()





        entry = tk.Entry(dialog, textvariable=name_var, width=20, font=("Microsoft YaHei", 10))





        entry.pack(pady=8)





        entry.focus()











        def do_add():





            name = name_var.get().strip()





            if not name:





                messagebox.showwarning(_safe_for_gbk("提示"), _safe_for_gbk("标签名称不能为空"))





                return





            if not hasattr(self, 'custom_statuses'):





                self.custom_statuses = []





            if name not in self.custom_statuses:





                self.custom_statuses.append(name)





                self._update_filter_options()





            dialog.destroy()











        btn_frame = tk.Frame(dialog)





        btn_frame.pack(pady=12)





        tk.Button(btn_frame, text="添加", width=8, command=do_add).pack(side="left", padx=8)





        tk.Button(btn_frame, text="取消", width=8, command=dialog.destroy).pack(side="left", padx=8)

















    def _move_to_quarantine(self):





        """将选中的行移动到隔离区（标记但不删除）"""





        try:





            selected = self.audit_tree.selection()





            if not selected:





                messagebox.showinfo(_safe_for_gbk("提示"), _safe_for_gbk("请先选中要隔离的行"))





                return











            if 'is_quarantined' not in self.audit_data.columns:





                self.audit_data['is_quarantined'] = False











            count = 0





            for item in selected:





                values = self.audit_tree.item(item, 'values')





                idx = int(values[0]) - 1 if values and str(values[0]).isdigit() else 0





                self.audit_data.at[idx, 'is_quarantined'] = True





                count += 1











            self._refresh_audit_tree(self.audit_data)





            messagebox.showinfo(_safe_for_gbk("完成"), _safe_for_gbk(f"已隔离 {count} 行"))











        except Exception as e:





            import traceback





            traceback.print_exc()





            messagebox.showerror(_safe_for_gbk("错误"), _safe_for_gbk(f"隔离操作失败：{str(e)}"))











    def _open_quarantine(self):





        """打开隔离区窗口"""





        quarantine_list = self._load_quarantine()











        win = tk.Toplevel(self.root)





        win.title("📦 异常隔离区")





        win.geometry("900x500")





        win.transient(self.root)











        # ── 表格区域 ──





        tree_frame = tk.Frame(win)





        tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))











        # 复用审核表格的列定义





        cols = self.audit_tree['columns']





        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15,





                            selectmode="extended")





        _QUAR_COL_DISPLAY = getattr(self, '_COL_DISPLAY', {})





        for col in cols:





            tree.heading(col, text=_QUAR_COL_DISPLAY.get(col, col))





            tree.column(col, width=self.audit_tree.column(col, 'width'), anchor="w")











        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)





        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)





        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)





        scroll_y.pack(side="right", fill="y")





        scroll_x.pack(side="bottom", fill="x")





        tree.pack(side="left", fill="both", expand=True)











        # 填充数据





        for i, rec in enumerate(quarantine_list):





            vals = [rec.get(col, '') for col in cols]





            tag = 'row_even' if i % 2 == 0 else 'row_odd'





            tree.insert('', 'end', values=vals, tags=(tag,))





        tree.tag_configure('row_even', background='#f5f7fa')





        tree.tag_configure('row_odd', background='#ffffff')











        # ── 操作按钮 ──





        btn_frame = tk.Frame(win, bg=C['bg'])





        btn_frame.pack(fill="x", padx=10, pady=(5, 10))











        def restore_selected():





            selected = tree.selection()





            if not selected:





                messagebox.showwarning(_safe_for_gbk("提示"), _safe_for_gbk("请先选择要恢复的行"))





                return





            restored = []





            for item in selected:





                vals = tree.item(item, 'values')





                rec = dict(zip(cols, vals))





                quarantine_list.remove(rec)





                restored.append(rec)











                # 重新插入审核表格（如果有 audit_data）





                if self.audit_data is not None:





                    new_row = pd.DataFrame([{





                        'excel_row': int(rec.get('excel_row', 0)),





                        '物料编码': rec.get('物料编码', ''),





                        '物料名称': rec.get('物料名称', ''),





                        '工厂名称': rec.get('工厂名称', ''),





                        '车间': rec.get('车间', ''),





                        '订单日期': rec.get('订单日期', ''),





                        '定额': float(rec.get('定额', 0)) if rec.get('定额') not in ('', '-', None) else 0,





                        '实际': float(rec.get('实际', 0)) if rec.get('实际') not in ('', '-', None) else 0,





                        '偏差率(%)': float(str(rec.get('偏差率(%)', '0')).rstrip('%')),





                        '偏差数量': float(rec.get('偏差数量', 0)) if rec.get('偏差数量') not in ('', '-', None) else 0,





                        '备注原因': rec.get('备注原因', ''),





                        '备注来源': rec.get('备注来源', ''),





                        '组件物料号': rec.get('组件物料号', ''),





                        '组件物料描述': rec.get('组件物料描述', ''),





                        '数量-定额': float(rec.get('数量-定额', 0)) if rec.get('数量-定额') not in ('', '-', None) else 0,





                        '数量-实际': float(rec.get('数量-实际', 0)) if rec.get('数量-实际') not in ('', '-', None) else 0,





                        '生产管理员描述': rec.get('生产管理员描述', ''),





                    }])





                    self.audit_data = pd.concat([self.audit_data, new_row], ignore_index=True)











                tree.delete(item)











            self._save_quarantine(quarantine_list)





            self._refresh_audit_tree(self.audit_data)





            self._update_audit_stats()





            self._update_filter_options()





            self.log(f"📤 已从隔离区恢复 {len(restored)} 条记录", "info")





            messagebox.showinfo(_safe_for_gbk("完成"), _safe_for_gbk(f"已恢复 {len(restored)} 条记录到审核表格"))











        def clear_all():





            if not quarantine_list:





                messagebox.showinfo(_safe_for_gbk("提示"), _safe_for_gbk("隔离区已空"))





                return





            if messagebox.askyesno(_safe_for_gbk("确认"), _safe_for_gbk(f"确定清空所有 {len(quarantine_list)} 条隔离记录？此操作不可恢复。")):





                quarantine_list.clear()





                self._save_quarantine(quarantine_list)





                for item in tree.get_children():





                    tree.delete(item)





                self.log("🗑️ 隔离区已清空", "info")











        def export_quarantine():





            if not quarantine_list:





                messagebox.showwarning(_safe_for_gbk("提示"), _safe_for_gbk("没有可导出的数据"))





                return





            file_path = filedialog.asksaveasfilename(





                title="导出隔离区", defaultextension=".xlsx",





                filetypes=[("Excel 文件", "*.xlsx"), ("CSV 文件", "*.csv")]





            )





            if not file_path:





                return





            try:





                export_df = pd.DataFrame(quarantine_list)





                if file_path.endswith('.csv'):





                    export_df.to_csv(file_path, index=False, encoding='utf-8-sig')





                else:





                    export_df.to_excel(file_path, index=False, engine='openpyxl')





                self.log(f"📤 隔离区已导出：{file_path}", "success")





                messagebox.showinfo(_safe_for_gbk("导出成功"), _safe_for_gbk(f"已导出 {len(quarantine_list)} 条记录"))





            except Exception as e:





                messagebox.showerror(_safe_for_gbk("导出失败"), _safe_for_gbk(str(e)))











        tk.Button(btn_frame, text="⬆ 恢复选中", command=restore_selected,





                  bg="#10b981", fg="white", font=("Microsoft YaHei", 10), relief="flat",





                  width=12).pack(side="left", padx=(0, 8))





        tk.Button(btn_frame, text="🗑️ 清空隔离区", command=clear_all,





                  bg="#ef4444", fg="white", font=("Microsoft YaHei", 10), relief="flat",





                  width=12).pack(side="left", padx=(0, 8))





        tk.Button(btn_frame, text="📤 导出", command=export_quarantine,





                  bg="#3b82f6", fg="white", font=("Microsoft YaHei", 10), relief="flat",





                  width=12).pack(side="left")

















    @with_feedback("移入隔离区成功", "移入隔离区失败")





    def _quarantine_selected(self):





        """将选中行移入隔离区"""





        selected = self.audit_tree.selection()





        if not selected:





            messagebox.showwarning(_safe_for_gbk("提示"), _safe_for_gbk("请先选择要移入隔离区的行"))





            return











        quarantine_list = self._load_quarantine()





        removed_indices = []











        for item in selected:





            values = self.audit_tree.item(item, 'values')





            cols = self.audit_tree['columns']





            record = dict(zip(cols, values))





            record['_quarantined_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')





            quarantine_list.append(record)











            # 从底层 DataFrame 中移除对应行





            excel_row = int(record.get('excel_row', 0))





            if self.audit_data is not None:





                mask = self.audit_data['excel_row'].astype(str) == str(excel_row)





                removed_indices.extend(self.audit_data[mask].index.tolist())





                self.audit_data = self.audit_data[~mask]











        # 保存隔离区文件





        self._save_quarantine(quarantine_list)











        # 从表格中移除选中行





        for item in selected:





            self.audit_tree.delete(item)











        # 刷新统计和筛选





        self._update_audit_stats()





        self._update_filter_options()





        self._apply_row_colors()











        self.log(f"🔒 已将 {len(selected)} 条记录移入隔离区（累计 {len(quarantine_list)} 条）", "info")





        messagebox.showinfo(_safe_for_gbk("完成"), _safe_for_gbk(f"已移入隔离区 {len(selected)} 条记录。\n隔离区累计：{len(quarantine_list)} 条"))

















    def _load_quarantine(self):





        p = self._get_quarantine_path()





        if not os.path.exists(p):





            return []





        try:





            with open(p, 'r', encoding='utf-8') as f:





                return json.load(f)





        except Exception:





            return []











    def _save_quarantine(self, data):





        with open(self._get_quarantine_path(), 'w', encoding='utf-8') as f:





            json.dump(data, f, ensure_ascii=False, indent=2)











    def _get_quarantine_path(self):





        d = os.path.join(os.path.expanduser('~'), '.zpp011_audit')





        os.makedirs(d, exist_ok=True)





        return os.path.join(d, 'quarantine.json')
