print("=== 运行最新代码 v39.6 ===")
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器 — 打包入口文件
"""
import sys
import os

# 确保当前目录在 Python 路径中
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后
    base_dir = sys._MEIPASS
else:
    # 开发模式
    base_dir = os.path.dirname(os.path.abspath(__file__))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# PyInstaller --noconsole: sys.stdout/stderr is None, redirect to devnull to avoid flush crash
if getattr(sys, 'frozen', False) and sys.stdout is None:
    class _NullWriter:
        def write(self, *a, **k): pass
        def flush(self): pass
        def close(self): pass
    sys.stdout = _NullWriter()
    sys.stderr = _NullWriter()

# 初始化日志系统
from core.logger import get_logger
logger = get_logger("Startup")
logger.info("程序启动")

# 初始化全局状态仓库
import atexit
from core.state_store import init_state
state = init_state()
atexit.register(lambda: state.save())

# 初始化配置管理器
from core.config_manager import ConfigManager
config = ConfigManager()
atexit.register(lambda: config._save())

# 导入并运行主程序
try:
    from gui.events import run_app
    run_app()
except Exception as e:
    import traceback
    traceback.print_exc()
    input("按回车键退出...")
