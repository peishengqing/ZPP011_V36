# -*- coding: utf-8 -*-
"""Fix inventory_view.py - handle CRLF line endings properly"""

filepath = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Normalize line endings for matching
content_norm = content.replace('\r\n', '\n')

# 1. Replace _import_inventory - remove self.parent.log calls
old_import_norm = '''    def _import_inventory(self):
        """导入库存表"""
        filepath = filedialog.askopenfilename(
            title="选择库存表",
            filetypes=[("Excel文件", "*.xlsx *.xls"), ("所有文件", "*.*")]
        )
        if not filepath:
            return

        try:
            self.parent.log("📥 正在加载库存数据...", "info")

            # 读取库存快照
            self.inventory_df = load_inventory_snapshot(filepath)
            self.parent.log(f"✅ 库存快照加载完成: {len(self.inventory_df)} 条记录", "info")

            # 读取入库流水
            self.inflow_df = merge_inventory_records(filepath)
            self.parent.log(f"✅ 入库流水加载完成: {len(self.inflow_df)} 条记录", "info")

            # 计算过期预警
            self.warning_df = calc_expiry_warning(self.inventory_df.copy())
            self.parent.log(f"✅ 过期预警计算完成", "info")

            # 刷新表格显示
            self._refresh_data()
            self._update_summary()

            # 显示预警统计
            expired = (self.warning_df['过期状态'] == '已过期').sum()
            expiring = (self.warning_df['过期状态'] == '即将过期(30天内)').sum()
            self.parent.log(f"⚠️ 过期预警: 已过期 {expired} 项, 即将过期 {expiring} 项", "warn")

            messagebox.showinfo("导入成功", f"库存数据导入完成！\\n库存记录: {len(self.inventory_df)} 条\\n入库记录: {len(self.inflow_df)} 条")

        except Exception as e:
            self.parent.log(f"❌ 导入失败: {e}", "error")
            messagebox.showerror("导入失败", str(e))'''

new_import_norm = '''    def _import_inventory(self):
        """导入库存表"""
        filepath = filedialog.askopenfilename(
            title="选择库存表",
            filetypes=[("Excel文件", "*.xlsx *.xls"), ("所有文件", "*.*")]
        )
        if not filepath:
            return

        try:
            # 读取库存快照
            self.inventory_df = load_inventory_snapshot(filepath)

            # 读取入库流水
            self.inflow_df = merge_inventory_records(filepath)

            # 计算过期预警
            self.warning_df = calc_expiry_warning(self.inventory_df.copy())

            # 刷新表格显示
            self._refresh_data()
            self._update_summary()

            messagebox.showinfo("导入成功", f"库存数据导入完成！\\n库存记录: {len(self.inventory_df)} 条\\n入库记录: {len(self.inflow_df)} 条")

        except Exception as e:
            messagebox.showerror("导入失败", str(e))'''

if old_import_norm in content_norm:
    content_norm = content_norm.replace(old_import_norm, new_import_norm)
    print("1. Replaced _import_inventory (removed self.parent.log)")
else:
    print("1. FAILED: _import_inventory pattern not found!")
    # Debug: find first self.parent.log position
    idx = content_norm.find('self.parent.log')
    print(f"   First self.parent.log at pos {idx}")
    print(f"   Context: ...{content_norm[max(0,idx-50):idx+80]}...")

# 2. Replace _refresh_data
old_refresh_norm = '''    def _refresh_data(self):
        """刷新表格显示"""
        if self.inventory_df is not None:
            # TODO: 刷新库存快照表格
            pass'''

new_refresh_norm = '''    def _refresh_data(self):
        """刷新表格显示"""
        # 刷新库存快照表格
        if self.inventory_df is not None and self.inventory_tree is not None:
            self.inventory_tree.delete(*self.inventory_tree.get_children())
            for _, row in self.inventory_df.iterrows():
                values = []
                for col in ['物料编码', '物料名称', '现存量', '生产日期', '保质期']:
                    val = row.get(col, '')
                    values.append(str(val) if val is not None else '')
                self.inventory_tree.insert('', 'end', values=values)

        # 刷新入库流水表格
        if self.inflow_df is not None and self.inflow_tree is not None:
            self.inflow_tree.delete(*self.inflow_tree.get_children())
            for _, row in self.inflow_df.iterrows():
                values = []
                for col in ['入库日期', '物料编码', '物料名称', '入库类型', '数量', '单位', '金额']:
                    val = row.get(col, '')
                    values.append(str(val) if val is not None else '')
                self.inflow_tree.insert('', 'end', values=values)

        # 刷新过期预警表格
        if self.warning_df is not None and self.warning_tree is not None:
            self.warning_tree.delete(*self.warning_tree.get_children())
            for _, row in self.warning_df.iterrows():
                values = []
                for col in ['物料编码', '物料名称', '剩余天数', '过期状态', '保质期']:
                    val = row.get(col, '')
                    values.append(str(val) if val is not None else '')
                self.warning_tree.insert('', 'end', values=values)'''

if old_refresh_norm in content_norm:
    content_norm = content_norm.replace(old_refresh_norm, new_refresh_norm)
    print("2. Replaced _refresh_data (implemented table filling)")
else:
    print("2. FAILED: _refresh_data pattern not found!")
    idx = content_norm.find('def _refresh_data')
    print(f"   Found def at pos {idx}")
    print(f"   Content: {content_norm[idx:idx+200]}")

# 3. Replace TODO pass blocks at end of _update_summary
old_todos_norm = '''        if self.inflow_df is not None:
            # TODO: 刷新入库流水表格
            pass
        if self.warning_df is not None:
            # TODO: 刷新过期预警表格
            pass'''

new_todos_norm = '''        # 入库流水和过期预警表格由 _refresh_data() 统一处理'''

if old_todos_norm in content_norm:
    content_norm = content_norm.replace(old_todos_norm, new_todos_norm)
    print("3. Replaced TODO pass blocks in _update_summary")
else:
    print("3. FAILED: TODO pass blocks not found!")

# Write back with CRLF
content_crlf = content_norm.replace('\n', '\r\n')
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content_crlf)

# Verify
import re
remaining = list(re.finditer(r'self\.parent\.log', content_norm))
print(f"\nVerification: {len(remaining)} self.parent.log calls remaining")
todos_remaining = list(re.finditer(r'# TODO', content_norm))
print(f"Verification: {len(todos_remaining)} TODO comments remaining")
