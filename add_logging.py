#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给关键方法加 self.log 追踪调用链"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir(r'E:\zpp011_dev\模块化脚本')

files_to_patch = [
    'gui/event_handlers/analysis_events.py',
    'gui/event_handlers/table_events.py',
]

for fp in files_to_patch:
    print(f'\n=== 处理 {fp} ===')
    with open(fp, 'r', encoding='utf-8') as f:
        src = f.read()
    
    modified = False
    
    # 1. _load_data_worker: 加 START 日志
    old = 'def _load_data_worker(self, file_path=None):\n        """纯数据处理：查找文件、读取、清洗、构建audit_df（禁止UI操作）"""'
    new = old + '\n        self.log("[TRACE] _load_data_worker START", "info")'
    if old in src and '[TRACE] _load_data_worker START' not in src:
        src = src.replace(old, new)
        modified = True
        print('  + _load_data_worker START log')
    
    # 2. _load_data_worker: 找到文件后加日志
    old2 = '            latest_file = max(files, key=os.path.getmtime)'
    new2 = old2 + '\n            self.log(f"[TRACE] _load_data_worker 找到文件: {latest_file}", "info")'
    if old2 in src and '找到文件' not in src.split(old2)[1][:200]:
        src = src.replace(old2, new2, 1)
        modified = True
        print('  + 找到文件 log')
    
    # 3. _load_data_worker: 构建完 audit_df 后加日志
    old3 = '        # 调试：对比 订单300354378+物料10000000 的数据'
    new3 = '        self.log(f"[TRACE] _load_data_worker 完成, audit_df={len(audit_df)}行", "info")\n\n' + old3
    if old3 in src and 'audit_df='] not in src:
        src = src.replace(old3, new3)
        modified = True
        print('  + audit_df 完成 log')
    
    # 4. _on_load_done: 加 START 日志
    old4 = 'def _on_load_done(self, result_df):\n        """异步加载成功回调：更新UI（禁止耗时操作）"""'
    new4 = old4 + '\n        self.log(f"[TRACE] _on_load_done START, result_df={len(result_df)}行", "info")'
    if old4 in src and '[TRACE] _on_load_done START' not in src:
        src = src.replace(old4, new4)
        modified = True
        print('  + _on_load_done START log')
    
    # 5. _on_load_done: audit_data 赋值后加日志
    old5 = '        self.audit_data = result_df.copy()'
    new5 = old5 + '\n        self.log(f"[TRACE] audit_data 已赋值, {len(self.audit_data)}行", "info")'
    if old5 in src and 'audit_data 已赋值' not in src:
        src = src.replace(old5, new5, 1)
        modified = True
        print('  + audit_data 赋值 log')
    
    # 6. _on_load_error: 加日志
    old6 = 'def _on_load_error(self, error_msg):\n        """异步加载失败回调"""'
    new6 = old6 + '\n        self.log(f"[TRACE] _on_load_error: {error_msg}", "error")'
    if old6 in src and '[TRACE] _on_load_error' not in src:
        src = src.replace(old6, new6)
        modified = True
        print('  + _on_load_error log')
    
    if modified:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f'  => 已保存 {fp}')
    else:
        print(f'  => 无需修改或已修改过')

# 处理 table_events.py
fp2 = 'gui/event_handlers/table_events.py'
print(f'\n=== 处理 {fp2} ===')
with open(fp2, 'r', encoding='utf-8') as f:
    src2 = f.read()

modified2 = False

# _refresh_audit_tree START
old = 'def _refresh_audit_tree(self, df, skip_auto_sort=False):\n        """用给定的 DataFrame 刷新智能审核表格"""'
new = old + '\n        self.log(f"[TRACE] _refresh_audit_tree START, df={len(df)}行", "info")'
if old in src2 and '[TRACE] _refresh_audit_tree START' not in src2:
    src2 = src2.replace(old, new)
    modified2 = True
    print('  + _refresh_audit_tree START log')

# 在 insert 循环后加日志（找 for i, (_, row) in enumerate(df.iterrows()) 后面）
old2 = '        for i, (_, row) in enumerate(df.iterrows(), 1):'
# 找对应的循环结束（下一个同级缩进的语句），在它前面加日志
# 简单做法：在方法结束前（before the displaycolumns restore）加日志
old3 = '        try:\n            self.audit_tree.configure('
new3 = '        self.log(f"[TRACE] _refresh_audit_tree 插入完成, 实际插入? audit_data={len(df)}行", "info")\n\n' + old3
if old3 in src2 and '插入完成' not in src2:
    src2 = src2.replace(old3, new3, 1)
    modified2 = True
    print('  + 插入完成 log')

if modified2:
    with open(fp2, 'w', encoding='utf-8') as f:
        f.write(src2)
    print(f'  => 已保存 {fp2}')
else:
    print(f'  => 无需修改或已修改过')

print('\n=== 完成 ===')
input('按回车退出...')
