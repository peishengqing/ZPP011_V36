# -*- coding: utf-8 -*-
"""鎵归噺鎿嶄綔 + 闅旂鍖轰簨浠?""

import tkinter as tk
from tkinter import ttk, messagebox
import json, os
import pandas as pd
from widgets import C


class AuditBatchEvents:
    """鎵归噺鎿嶄綔 + 闅旂鍖轰簨浠?""
    def _batch_change_status(self, event=None):





        """鎵归噺鏇存敼閫変腑琛岀殑鐘舵€?""





        selected = self.audit_tree.selection()





        if not selected:





            messagebox.showwarning("鎻愮ず", "璇峰厛閫夋嫨瑕佹洿鏀圭姸鎬佺殑琛?)





            return











        status_options = ["宸插娉?, "闇€琛ュ娉?, "宸茬‘璁?, "寰呭鐞?, "寮傚父"]





        if hasattr(self, 'custom_statuses'):





            status_options += self.custom_statuses











        dialog = tk.Toplevel(self.root)





        dialog.title("鎵归噺鏇存敼鐘舵€?)





        dialog.geometry("300x200")





        dialog.transient(self.root)





        dialog.grab_set()





        dialog.update_idletasks()





        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2





        y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2





        dialog.geometry(f"+{x}+{y}")











        tk.Label(dialog, text=f"閫夋嫨鏂扮姸鎬侊紙灏嗕负 {len(selected)} 琛屾暟鎹洿鏀癸級:",





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





                    if mask.any() and '澶囨敞鍘熷洜' in self.audit_data.columns:





                        self.audit_data.loc[mask, '澶囨敞鍘熷洜'] = new_status





            self._update_audit_stats()





            self._update_filter_options()





            messagebox.showinfo("瀹屾垚", f"宸插皢 {len(selected)} 琛岀姸鎬佹洿鏀逛负銆寋new_status}銆?)





            dialog.destroy()











        btn_frame = tk.Frame(dialog)





        btn_frame.pack(pady=20)





        tk.Button(btn_frame, text="纭畾", width=10, command=apply_change).pack(side="left", padx=10)





        tk.Button(btn_frame, text="鍙栨秷", width=10, command=dialog.destroy).pack(side="left", padx=10)

















    def _batch_fill_remark(self, event=None):





        """鎵归噺濉啓澶囨敞"""





        selected = self.audit_tree.selection()





        if not selected:





            messagebox.showwarning("鎻愮ず", "璇峰厛閫夋嫨瑕佸～鍐欏娉ㄧ殑琛?)





            return











        # P1锛氭寜浣跨敤棰戠巼鎺掑簭鐨勯璁惧娉ㄥ垪琛?





        base_remarks = ["宸叉牳瀹烇紝鍋忓樊姝ｅ父", "宸叉矡閫氾紝纭鏃犺", "宸茶皟鏁达紝璇峰鏌?, "寰呰繘涓€姝ョ‘璁?, "鏇夸唬鏂欐浛鎹?, "宸ヨ壓璋冩暣", "搴撳瓨璋冩暣", "鍏朵粬鍘熷洜"]





        sorted_remarks, _ = self._get_sorted_remarks(base_remarks)





        remark_options = sorted_remarks + ["(娓呯┖澶囨敞)"]





        if hasattr(self, 'custom_remarks'):





            remark_options = self.custom_remarks + remark_options











        dialog = tk.Toplevel(self.root)





        dialog.title("鎵归噺濉啓澶囨敞")





        dialog.geometry("320x180")





        dialog.transient(self.root)





        dialog.grab_set()





        x = self.root.winfo_x() + (self.root.winfo_width() - 320) // 2





        y = self.root.winfo_y() + (self.root.winfo_height() - 180) // 2





        dialog.geometry(f"+{x}+{y}")











        tk.Label(dialog, text=f"閫夋嫨澶囨敞锛堝皢涓?{len(selected)} 琛屽～鍐欙級:",





                 font=("Microsoft YaHei", 10)).pack(pady=15)





        remark_var = tk.StringVar()





        remark_combo = ttk.Combobox(dialog, textvariable=remark_var, values=remark_options,





                                    width=28, font=("Microsoft YaHei", 10))





        remark_combo.pack(pady=10)





        remark_combo.focus()











        def apply_remark():





            remark = remark_var.get()





            if remark == "(娓呯┖澶囨敞)":





                remark = ""





            count = 0





            for item in selected:





                self.audit_tree.set(item, 'batch_remark', remark)  # 鍐欏叆鎵归噺澶囨敞鍒?





                excel_row = int(self.audit_tree.set(item, 'excel_row'))





                if self.audit_data is not None:





                    mask = self.audit_data['excel_row'].astype(str) == str(excel_row)





                    if mask.any():





                        # 浼樺厛鍐欏叆鎵归噺澶囨敞鍒楋紝鍏煎 fallback





                        batch_col = None





                        for col in ['鎵归噺澶囨敞鍘熷洜', '鎵归噺澶囨敞']:





                            if col in self.audit_data.columns:





                                batch_col = col





                                break





                        if batch_col:





                            self.audit_data.loc[mask, batch_col] = remark





                            count += 1





                        elif '澶囨敞鍘熷洜' in self.audit_data.columns:





                            self.audit_data.loc[mask, '澶囨敞鍘熷洜'] = remark





                            count += 1





            self._record_remark_freq(remark_var.get())  # P1锛氳褰曢鐜?





            self._update_audit_stats()





            self._update_filter_options()





            label = "娓呯┖" if not remark else f"銆寋remark}銆?





            messagebox.showinfo("瀹屾垚", f"宸蹭负 {count if count else len(selected)} 琛屽～鍐欏娉?{label}")





            dialog.destroy()











        btn_frame = tk.Frame(dialog)





        btn_frame.pack(pady=15)





        tk.Button(btn_frame, text="纭畾", width=10, command=apply_remark).pack(side="left", padx=10)





        tk.Button(btn_frame, text="鍙栨秷", width=10, command=dialog.destroy).pack(side="left", padx=10)
    def _batch_remark(self, event=None):





        """鎵归噺澶囨敞锛氫负閫変腑鐨勮娣诲姞澶囨敞锛堜笅鎷夋閫夋嫨锛屽彲杩藉姞鎹㈣锛?""





        try:





            selected = self.audit_tree.selection()





            if not selected:





                messagebox.showinfo("鎻愮ず", "璇峰厛閫変腑瑕佹坊鍔犲娉ㄧ殑琛岋紙鍙閫夛級")





                return











            # P1锛氭寜浣跨敤棰戠巼鎺掑簭鐨勯璁惧娉ㄥ垪琛?





            base_remarks = ["宸叉牳瀹烇紝鍋忓樊姝ｅ父", "宸叉矡閫氾紝纭鏃犺", "宸茶皟鏁达紝璇峰鏌?, "寰呰繘涓€姝ョ‘璁?, "鏇夸唬鏂欐浛鎹?, "宸ヨ壓璋冩暣", "搴撳瓨璋冩暣", "鍏朵粬鍘熷洜"]





            sorted_remarks, _ = self._get_sorted_remarks(base_remarks)





            remark_options = sorted_remarks + ["(娓呯┖澶囨敞)", "鈥斺€旀墜鍔ㄨ緭鍏モ€斺€?]





            if hasattr(self, 'custom_remarks'):





                remark_options = self.custom_remarks + remark_options











            dialog = tk.Toplevel(self.root)





            dialog.title("鎵归噺澶囨敞")





            dialog.geometry("360x200")





            dialog.transient(self.root)





            dialog.grab_set()





            x = self.root.winfo_x() + (self.root.winfo_width() - 360) // 2





            y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2





            dialog.geometry(f"+{x}+{y}")











            tk.Label(dialog, text=f"閫夋嫨澶囨敞锛堝皢涓?{len(selected)} 琛屽～鍐欙級:",





                     font=("Microsoft YaHei", 10)).pack(pady=10)











            remark_var = tk.StringVar()





            remark_combo = ttk.Combobox(dialog, textvariable=remark_var, values=remark_options,





                                        width=36, font=("Microsoft YaHei", 10), state="readonly")





            remark_combo.pack(pady=8)





            remark_combo.focus()











            # 鎵嬪姩杈撳叆妗嗭紙榛樿闅愯棌锛?





            input_frame = tk.Frame(dialog)





            input_frame.pack(pady=4)





            custom_entry = ttk.Entry(input_frame, width=36, font=("Microsoft YaHei", 10))





            custom_entry.pack()





            input_frame.pack_forget()  # 榛樿闅愯棌











            # 鐩戝惉閫夋嫨鍙樺寲锛屽垏鎹㈡墜鍔ㄨ緭鍏ユ





            def on_combo_change(*args):





                if remark_var.get() == "鈥斺€旀墜鍔ㄨ緭鍏モ€斺€?:





                    input_frame.pack(pady=4)





                    custom_entry.focus()





                else:





                    input_frame.pack_forget()











            remark_combo.bind("<<ComboboxSelected>>", on_combo_change)











            def apply_remark():





                remark = remark_var.get()





                if remark == "(娓呯┖澶囨敞)":





                    remark = ""





                elif remark == "鈥斺€旀墜鍔ㄨ緭鍏モ€斺€?:





                    remark = custom_entry.get().strip()





                    if not remark:





                        messagebox.showwarning("鎻愮ず", "璇疯緭鍏ュ娉ㄥ唴瀹?)





                        return





                if not remark:





                    return











                # 纭畾 DataFrame 涓殑澶囨敞鍒楀悕锛堜紭鍏堟壒閲忓娉ㄥ垪锛?





                df_remark_col = None





                for col in ['鎵归噺澶囨敞鍘熷洜', '鎵归噺澶囨敞']:





                    if col in self.audit_data.columns:





                        df_remark_col = col





                        break





                if df_remark_col is None:





                    df_remark_col = "鎵归噺澶囨敞"





                    self.audit_data[df_remark_col] = ""











                # 浣跨敤 excel_row 瀹氫綅锛屾瀯寤?item->df_idx 鏄犲皠





                item_to_idx = {}





                for item in selected:





                    excel_row = int(self.audit_tree.set(item, 'excel_row'))





                    mask = self.audit_data['excel_row'].astype(str) == str(excel_row)





                    if mask.any():





                        item_to_idx[item] = mask.idxmax()











                if not item_to_idx:





                    messagebox.showwarning("璀﹀憡", "鏃犳硶瀹氫綅閫変腑琛岋紝璇峰埛鏂伴噸璇?)





                    return











                # 杩藉姞澶囨敞锛堟崲琛岃繛鎺ワ紝鍖哄垎绗?/锛?





                count = 0





                for item, idx in item_to_idx.items():





                    self.audit_tree.set(item, 'batch_remark', remark)  # 鍒锋柊鏍戝舰鍒?





                    current = self.audit_data.at[idx, df_remark_col]





                    if pd.notna(current) and str(current).strip():





                        self.audit_data.at[idx, df_remark_col] = f"{current}\n/{remark}"





                    else:





                        self.audit_data.at[idx, df_remark_col] = remark





                    count += 1











                self._record_remark_freq(remark)  # P1锛氳褰曢鐜?





                self._refresh_audit_tree(self.audit_data)





                self._update_audit_stats()





                self._update_filter_options()





                label = "娓呯┖" if not remark else f"銆寋remark}銆?





                messagebox.showinfo("瀹屾垚", f"宸蹭负 {count} 琛屾坊鍔犲娉?{label}")





                dialog.destroy()











            btn_frame = tk.Frame(dialog)





            btn_frame.pack(pady=10)





            tk.Button(btn_frame, text="纭畾", width=10, command=apply_remark).pack(side="left", padx=10)





            tk.Button(btn_frame, text="鍙栨秷", width=10, command=dialog.destroy).pack(side="left", padx=10)











        except Exception as e:





            import traceback





            traceback.print_exc()





            messagebox.showerror("閿欒", f"鎵归噺澶囨敞澶辫触锛歿str(e)}")











    def _add_custom_status(self, event=None):





        """娣诲姞鑷畾涔夌姸鎬佹爣绛?""





        dialog = tk.Toplevel(self.root)





        dialog.title("娣诲姞鐘舵€佹爣绛?)





        dialog.geometry("280x140")





        dialog.transient(self.root)





        dialog.grab_set()





        x = self.root.winfo_x() + (self.root.winfo_width() - 280) // 2





        y = self.root.winfo_y() + (self.root.winfo_height() - 140) // 2





        dialog.geometry(f"+{x}+{y}")











        tk.Label(dialog, text="杈撳叆鏂扮姸鎬佹爣绛惧悕绉帮細", font=("Microsoft YaHei", 10)).pack(pady=10)





        name_var = tk.StringVar()





        entry = tk.Entry(dialog, textvariable=name_var, width=20, font=("Microsoft YaHei", 10))





        entry.pack(pady=8)





        entry.focus()











        def do_add():





            name = name_var.get().strip()





            if not name:





                messagebox.showwarning("鎻愮ず", "鏍囩鍚嶇О涓嶈兘涓虹┖")





                return





            if not hasattr(self, 'custom_statuses'):





                self.custom_statuses = []





            if name not in self.custom_statuses:





                self.custom_statuses.append(name)





                self._update_filter_options()





            dialog.destroy()











        btn_frame = tk.Frame(dialog)





        btn_frame.pack(pady=12)





        tk.Button(btn_frame, text="娣诲姞", width=8, command=do_add).pack(side="left", padx=8)





        tk.Button(btn_frame, text="鍙栨秷", width=8, command=dialog.destroy).pack(side="left", padx=8)

















    def _move_to_quarantine(self):





        """灏嗛€変腑鐨勮绉诲姩鍒伴殧绂诲尯锛堟爣璁颁絾涓嶅垹闄わ級"""





        try:





            selected = self.audit_tree.selection()





            if not selected:





                messagebox.showinfo("鎻愮ず", "璇峰厛閫変腑瑕侀殧绂荤殑琛?)





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





            messagebox.showinfo("瀹屾垚", f"宸查殧绂?{count} 琛?)











        except Exception as e:





            import traceback





            traceback.print_exc()





            messagebox.showerror("閿欒", f"闅旂鎿嶄綔澶辫触锛歿str(e)}")











    def _open_quarantine(self):





        """鎵撳紑闅旂鍖虹獥鍙?""





        quarantine_list = self._load_quarantine()











        win = tk.Toplevel(self.root)





        win.title("馃摝 寮傚父闅旂鍖?)





        win.geometry("900x500")





        win.transient(self.root)











        # 鈹€鈹€ 琛ㄦ牸鍖哄煙 鈹€鈹€





        tree_frame = tk.Frame(win)





        tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))











        # 澶嶇敤瀹℃牳琛ㄦ牸鐨勫垪瀹氫箟





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











        # 濉厖鏁版嵁





        for i, rec in enumerate(quarantine_list):





            vals = [rec.get(col, '') for col in cols]





            tag = 'row_even' if i % 2 == 0 else 'row_odd'





            tree.insert('', 'end', values=vals, tags=(tag,))





        tree.tag_configure('row_even', background='#f5f7fa')





        tree.tag_configure('row_odd', background='#ffffff')











        # 鈹€鈹€ 鎿嶄綔鎸夐挳 鈹€鈹€





        btn_frame = tk.Frame(win, bg=C['bg'])





        btn_frame.pack(fill="x", padx=10, pady=(5, 10))











        def restore_selected():





            selected = tree.selection()





            if not selected:





                messagebox.showwarning("鎻愮ず", "璇峰厛閫夋嫨瑕佹仮澶嶇殑琛?)





                return





            restored = []





            for item in selected:





                vals = tree.item(item, 'values')





                rec = dict(zip(cols, vals))





                quarantine_list.remove(rec)





                restored.append(rec)











                # 閲嶆柊鎻掑叆瀹℃牳琛ㄦ牸锛堝鏋滄湁 audit_data锛?





                if self.audit_data is not None:





                    new_row = pd.DataFrame([{





                        'excel_row': int(rec.get('excel_row', 0)),





                        '鐗╂枡缂栫爜': rec.get('鐗╂枡缂栫爜', ''),





                        '鐗╂枡鍚嶇О': rec.get('鐗╂枡鍚嶇О', ''),





                        '宸ュ巶鍚嶇О': rec.get('宸ュ巶鍚嶇О', ''),





                        '杞﹂棿': rec.get('杞﹂棿', ''),





                        '璁㈠崟鏃ユ湡': rec.get('璁㈠崟鏃ユ湡', ''),





                        '瀹氶': float(rec.get('瀹氶', 0)) if rec.get('瀹氶') not in ('', '-', None) else 0,





                        '瀹為檯': float(rec.get('瀹為檯', 0)) if rec.get('瀹為檯') not in ('', '-', None) else 0,





                        '鍋忓樊鐜?%)': float(str(rec.get('鍋忓樊鐜?%)', '0')).rstrip('%')),





                        '鍋忓樊鏁伴噺': float(rec.get('鍋忓樊鏁伴噺', 0)) if rec.get('鍋忓樊鏁伴噺') not in ('', '-', None) else 0,





                        '澶囨敞鍘熷洜': rec.get('澶囨敞鍘熷洜', ''),





                        '澶囨敞鏉ユ簮': rec.get('澶囨敞鏉ユ簮', ''),





                        '缁勪欢鐗╂枡鍙?: rec.get('缁勪欢鐗╂枡鍙?, ''),





                        '缁勪欢鐗╂枡鎻忚堪': rec.get('缁勪欢鐗╂枡鎻忚堪', ''),





                        '鏁伴噺-瀹氶': float(rec.get('鏁伴噺-瀹氶', 0)) if rec.get('鏁伴噺-瀹氶') not in ('', '-', None) else 0,





                        '鏁伴噺-瀹為檯': float(rec.get('鏁伴噺-瀹為檯', 0)) if rec.get('鏁伴噺-瀹為檯') not in ('', '-', None) else 0,





                        '鐢熶骇绠＄悊鍛樻弿杩?: rec.get('鐢熶骇绠＄悊鍛樻弿杩?, ''),





                    }])





                    self.audit_data = pd.concat([self.audit_data, new_row], ignore_index=True)











                tree.delete(item)











            self._save_quarantine(quarantine_list)





            self._refresh_audit_tree(self.audit_data)





            self._update_audit_stats()





            self._update_filter_options()





            self.log(f"馃摛 宸蹭粠闅旂鍖烘仮澶?{len(restored)} 鏉¤褰?, "info")





            messagebox.showinfo("瀹屾垚", f"宸叉仮澶?{len(restored)} 鏉¤褰曞埌瀹℃牳琛ㄦ牸")











        def clear_all():





            if not quarantine_list:





                messagebox.showinfo("鎻愮ず", "闅旂鍖哄凡绌?)





                return





            if messagebox.askyesno("纭", f"纭畾娓呯┖鎵€鏈?{len(quarantine_list)} 鏉￠殧绂昏褰曪紵姝ゆ搷浣滀笉鍙仮澶嶃€?):





                quarantine_list.clear()





                self._save_quarantine(quarantine_list)





                for item in tree.get_children():





                    tree.delete(item)





                self.log("馃棏锔?闅旂鍖哄凡娓呯┖", "info")











        def export_quarantine():





            if not quarantine_list:





                messagebox.showwarning("鎻愮ず", "娌℃湁鍙鍑虹殑鏁版嵁")





                return





            file_path = filedialog.asksaveasfilename(





                title="瀵煎嚭闅旂鍖?, defaultextension=".xlsx",





                filetypes=[("Excel 鏂囦欢", "*.xlsx"), ("CSV 鏂囦欢", "*.csv")]





            )





            if not file_path:





                return





            try:





                export_df = pd.DataFrame(quarantine_list)





                if file_path.endswith('.csv'):





                    export_df.to_csv(file_path, index=False, encoding='utf-8-sig')





                else:





                    export_df.to_excel(file_path, index=False, engine='openpyxl')





                self.log(f"馃摛 闅旂鍖哄凡瀵煎嚭锛歿file_path}", "success")





                messagebox.showinfo("瀵煎嚭鎴愬姛", f"宸插鍑?{len(quarantine_list)} 鏉¤褰?)





            except Exception as e:





                messagebox.showerror("瀵煎嚭澶辫触", str(e))











        tk.Button(btn_frame, text="猬?鎭㈠閫変腑", command=restore_selected,





                  bg="#10b981", fg="white", font=("Microsoft YaHei", 10), relief="flat",





                  width=12).pack(side="left", padx=(0, 8))





        tk.Button(btn_frame, text="馃棏锔?娓呯┖闅旂鍖?, command=clear_all,





                  bg="#ef4444", fg="white", font=("Microsoft YaHei", 10), relief="flat",





                  width=12).pack(side="left", padx=(0, 8))





        tk.Button(btn_frame, text="馃摛 瀵煎嚭", command=export_quarantine,





                  bg="#3b82f6", fg="white", font=("Microsoft YaHei", 10), relief="flat",





                  width=12).pack(side="left")
    def _quarantine_selected(self):





        """灏嗛€変腑琛岀Щ鍏ラ殧绂诲尯"""





        selected = self.audit_tree.selection()





        if not selected:





            messagebox.showwarning("鎻愮ず", "璇峰厛閫夋嫨瑕佺Щ鍏ラ殧绂诲尯鐨勮")





            return











        quarantine_list = self._load_quarantine()





        removed_indices = []











        for item in selected:





            values = self.audit_tree.item(item, 'values')





            cols = self.audit_tree['columns']





            record = dict(zip(cols, values))





            record['_quarantined_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')





            quarantine_list.append(record)











            # 浠庡簳灞?DataFrame 涓Щ闄ゅ搴旇





            excel_row = int(record.get('excel_row', 0))





            if self.audit_data is not None:





                mask = self.audit_data['excel_row'].astype(str) == str(excel_row)





                removed_indices.extend(self.audit_data[mask].index.tolist())





                self.audit_data = self.audit_data[~mask]











        # 淇濆瓨闅旂鍖烘枃浠?





        self._save_quarantine(quarantine_list)











        # 浠庤〃鏍间腑绉婚櫎閫変腑琛?





        for item in selected:





            self.audit_tree.delete(item)











        # 鍒锋柊缁熻鍜岀瓫閫?





        self._update_audit_stats()





        self._update_filter_options()





        self._apply_row_colors()











        self.log(f"馃敀 宸插皢 {len(selected)} 鏉¤褰曠Щ鍏ラ殧绂诲尯锛堢疮璁?{len(quarantine_list)} 鏉★級", "info")





        messagebox.showinfo("瀹屾垚", f"宸茬Щ鍏ラ殧绂诲尯 {len(selected)} 鏉¤褰曘€俓n闅旂鍖虹疮璁★細{len(quarantine_list)} 鏉?)

















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
