#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 调试入口 - 捕获所有启动期错误
"""
import os
import sys
import traceback
import datetime

# 日志文件在桌面，方便查看
LOG = os.path.join(os.path.expanduser('~'), 'Desktop', 'zpp011_bootstrap.log')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")

log("=" * 60)
log("main_debug.py 启动")
log(f"sys.frozen = {getattr(sys, 'frozen', False)}")
log(f"sys.executable = {sys.executable}")
log(f"sys.argv[0] = {sys.argv[0]}")

try:
    log("正在导入 main...")
    import main
    log("main 导入成功")
    
    log("正在调用 main.main()...")
    main.main()
    log("main() 正常返回")
    
except Exception as e:
    log(f"CRASH: {type(e).__name__}: {e}")
    log(traceback.format_exc())
    # 也弹窗，确保用户能看到
    import tkinter.messagebox as mb
    mb.showerror("启动失败", f"{type(e).__name__}\n\n{e}\n\n详情见桌面 zpp011_bootstrap.log")
    raise
