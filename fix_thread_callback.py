#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复线程回调问题：给 _load_data_worker 加日志，追踪为什么 _on_load_done 没被调用"""
import sys, os

LOG = r'C:\Users\Administrator\Desktop\zpp011_thread_log.txt'

def fix_analysis_events():
    fp = r'E:\zpp011_dev\模块化脚本\gui\event_handlers\analysis_events.py'
    print(f'处理: {fp}')
    with open(fp, 'r', encoding='utf-8') as f:
        src = f.read()
    
    modified = False
    
    # 1. 在 _load_data_worker 的 return audit_df 前加日志
    old = '        with open(r"C:\\Users\\Administrator\\Desktop\\zpp011_debug.txt", "a", encoding="utf-8") as _lf:\n            _lf.write(f"[TRACE] _load_data_worker 完成: {len(audit_df) if "audit_df" in dir() else "??"} 行\\n")\n        return audit_df'
    
    new = f'        with open(r"{LOG}", "a", encoding="utf-8") as _f:\n            _f.write(f"[THREAD] _load_data_worker 完成: {{len(audit_df)}} 行\\n")\n        return audit_df'
    
    if old in src:
        src = src.replace(old, new, 1)
        modified = True
        print('  + 修复了日志路径')
    
    # 2. 在 _load_data_worker 开头加更明显的日志
    old2 = 'def _load_data_worker(self, file_path=None):\n        """纯数据处理：查找文件、读取、清洗、构建audit_df（禁止UI操作）"""\n        with open(r"C:\\Users\\Administrator\\Desktop\\zpp011_debug.txt", "a", encoding="utf-8") as _lf:\n            _lf.write(f"[TRACE] _load_data_worker START\\n")'
    
    new2 = 'def _load_data_worker(self, file_path=None):\n        """纯数据处理：查找文件、读取、清洗、构建audit_df（禁止UI操作）"""\n        with open(r"' + LOG + '", "a", encoding="utf-8") as _f:\n            import time; _f.write(f"[THREAD] _load_data_worker START @ {time.strftime(\'%H:%M:%S\')}\\n")'
    
    if old2 in src:
        src = src.replace(old2, new2, 1)
        modified = True
        print('  + 修复了 START 日志')
    
    # 3. 在 task_manager.run 调用处加日志
    old3 = '            self.task_manager.run(\n                lambda: self._load_data_worker(file_path),\n                callback=self._on_load_done,\n                error_callback=self._on_load_error\n            )'
    
    new3 = '            with open(r"' + LOG + '", "a", encoding="utf-8") as _f:\n                import time; _f.write(f"[THREAD] task_manager.run 调用 @ {time.strftime(\'%H:%M:%S\')}\\n")\n            self.task_manager.run(\n                lambda: self._load_data_worker(file_path),\n                callback=self._on_load_done,\n                error_callback=self._on_load_error\n            )\n            with open(r"' + LOG + '", "a", encoding="utf-8") as _f:\n                _f.write(f"[THREAD] task_manager.run 已启动线程\\n")'
    
    if old3 in src:
        src = src.replace(old3, new3, 1)
        modified = True
        print('  + 添加了 task_manager.run 日志')
    
    # 4. 在 _on_load_done 开头加日志
    old4 = '    def _on_load_done(self, result_df):\n        """异步加载成功回调：处理所有UI更新"""\n        with open(r"C:\\Users\\Administrator\\Desktop\\zpp011_debug.txt", "a", encoding="utf-8") as _lf:\n            _lf.write(f"[TRACE] _on_load_done START: result_df={len(result_df) if result_df is not None else "None"} 行\\n")'
    
    new4 = '    def _on_load_done(self, result_df):\n        """异步加载成功回调：处理所有UI更新"""\n        with open(r"' + LOG + '", "a", encoding="utf-8") as _f:\n            import time; _f.write(f"[THREAD] _on_load_done 被回调! result_df={{len(result_df) if result_df is not None else \\"None\\"}} 行 @ {{time.strftime(\\'%H:%M:%S\\')}}\\n")\n        print(f"[DEBUG] _on_load_done 被回调! result_df={{len(result_df) if result_df is not None else \\"None\\"}} 行")'
    
    if old4 in src:
        src = src.replace(old4, new4, 1)
        modified = True
        print('  + 修复了 _on_load_done 日志')
    
    if modified:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f'✅ 已保存: {fp}')
        return True
    else:
        print('⚠️ 没有找到可修改的内容')
        return False

if __name__ == '__main__':
    # 清空旧日志
    if os.path.exists(LOG):
        os.remove(LOG)
    print(f'日志文件: {LOG}')
    fix_analysis_events()
    print('\n完成！请重新运行 main.py，然后查看桌面 zpp011_thread_log.txt')
