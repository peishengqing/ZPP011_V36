#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给关键方法加文件日志，追踪调用链"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

LOG = os.path.join(os.path.expanduser('~'), 'Desktop', 'zpp011_debug.txt')

def patch_file(fp):
    print(f'\n=== 处理 {fp} ===')
    with open(fp, 'r', encoding='utf-8') as f:
        src = f.read()
    
    modified = False
    orig_len = len(src)
    
    # 1. _load_data_worker START
    old = 'def _load_data_worker(self, file_path=None):\n        """纯数据处理：查找文件、读取、清洗、构建audit_df（禁止UI操作）"""'
    new = old + '\n        with open(r"' + LOG + '", "a", encoding="utf-8") as _lf:\n            _lf.write(f"[TRACE] _load_data_worker START\\n")'
    if old in src and '_load_data_worker START' not in src:
        src = src.replace(old, new, 1)
        modified = True
        print('  + _load_data_worker START')
    
    # 2. _load_data_worker 找到文件
    old2 = '                    latest_file = max(files, key=os.path.getmtime)'
    new2 = old2 + '\n                    with open(r"' + LOG + '", "a", encoding="utf-8") as _lf:\n                        _lf.write(f"[TRACE] 找到文件: {latest_file}\\n")'
    if old2 in src and '找到文件' not in src.split(old2)[1][:200] if old2 in src else False:
        pass  # 稍后处理
    
    # 简化：直接在 return audit_df 前加日志
    # 找 return audit_df
    old3 = '        return audit_df'
    new3 = '        with open(r"' + LOG + '", "a", encoding="utf-8") as _lf:\n            _lf.write(f"[TRACE] _load_data_worker 完成: {len(audit_df) if "audit_df" in dir() else "??"} 行\\n")\n        return audit_df'
    if old3 in src and 'LOAD_WORKER 完成' not in src:
        # 只在方法内第一个 return audit_df 替换
        idx = src.find(old3)
        # 检查是不是在 _load_data_worker 方法内
        method_start = src.find('def _load_data_worker')
        if method_start != -1 and idx > method_start:
            src = src[:idx] + new3 + src[idx+len(old3):]
            modified = True
            print('  + _load_data_worker return 日志')
    
    # 3. _on_load_done START
    old4 = 'def _on_load_done(self, result_df):\n        """异步加载成功回调：处理所有UI更新"""'
    new4 = old4 + '\n        with open(r"' + LOG + '", "a", encoding="utf-8") as _lf:\n            _lf.write(f"[TRACE] _on_load_done START: result_df={len(result_df) if result_df is not None else "None"} 行\\n")'
    if old4 in src and '_on_load_done START' not in src:
        src = src.replace(old4, new4, 1)
        modified = True
        print('  + _on_load_done START')
    
    # 4. _on_load_done 中 audit_data 赋值后
    old5 = '            self.audit_data = result_df'
    new5 = old5 + '\n            with open(r"' + LOG + '", "a", encoding="utf-8") as _lf:\n                _lf.write(f"[TRACE] audit_data 已赋值: {len(self.audit_data)} 行\\n")'
    if old5 in src and 'audit_data 已赋值' not in src:
        src = src.replace(old5, new5, 1)
        modified = True
        print('  + audit_data 赋值日志')
    
    # 5. _on_load_error
    old6 = 'def _on_load_error(self, error_msg):\n        """异步加载失败回调"""'
    new6 = old6 + '\n        with open(r"' + LOG + '", "a", encoding="utf-8") as _lf:\n            import traceback; _lf.write(f"[ERROR] _on_load_error: {error_msg}\\n{traceback.format_exc()}\\n")'
    if old6 in src and '_on_load_error' not in src:
        src = src.replace(old6, new6, 1)
        modified = True
        print('  + _on_load_error 日志')
    
    if modified:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f'  => 已保存 {fp} ({orig_len} -> {len(src)} bytes)')
    else:
        print(f'  => 无需修改或已修改过')
    
    return modified

# 处理两个文件
files = [
    r'E:\zpp011_dev\模块化脚本\gui\event_handlers\analysis_events.py',
    r'E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py',
]

for fp in files:
    if os.path.exists(fp):
        patch_file(fp)
    else:
        print(f'文件不存在: {fp}')

print('\n=== 完成 ===')
print(f'日志将写入: {LOG}')
print('请重新运行程序，然后查看桌面 zpp011_debug.txt')
input('按回车退出...')
