"""调试输出统一开关。

默认静默，避免正式运行时大量 print 拖慢速度、刷屏控制台。
需要排查问题时，设环境变量后重跑即可恢复全部诊断输出：

    Windows CMD:        set ZPP011_DEBUG=1 && python run_pyside6.py
    PowerShell:         $env:ZPP011_DEBUG=1; python run_pyside6.py

历史教训（2026-07-30）：控制台 print 在 Windows 上有两个隐藏成本——
① 「快速编辑模式」下鼠标点一下控制台，所有 print 线程直接冻结；
② 高频 print（如排序比较函数内）会把 stdio 调用放大到十万量级。
因此诊断打点一律走此开关，不要裸 print。
"""
import os
import sys

# 环境变量为 "1"/"true"/"yes"（不区分大小写）时开启
DEBUG_ENABLED = os.environ.get('ZPP011_DEBUG', '').strip().lower() in ('1', 'true', 'yes', 'on')


def dprint(*args, **kwargs):
    """安全调试输出：默认静默；开启后避免 Windows 控制台 GBK Errno 22 崩溃。"""
    if not DEBUG_ENABLED:
        return
    if sys.stdout is None or getattr(sys.stdout, 'closed', False):
        return
    kwargs.pop('flush', None)
    try:
        print(*args, **kwargs)
    except (OSError, UnicodeEncodeError):
        pass
