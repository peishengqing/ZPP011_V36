# -*- coding: utf-8 -*-
r"""列头点击诊断日志（默认关闭）。

背景：v43.116~v43.119 为定位「真实鼠标下点列头没反应」在信号发射 / 点击路由 /
弹层创建三处埋了写盘日志，问题已定位并修复（见 utils/version_history.py v43.119）。

日志是诊断辅助，不应长期挂在生产主路径上：默认零 I/O，只有显式设置环境变量
ZPP011_CLICK_DEBUG=1 启动程序时才写 %TEMP%\zpp011_click.log。
"""
import os
import tempfile
import time

# 进程启动时读取一次；测试可直接改 click_debug.CLICK_DEBUG
CLICK_DEBUG = bool(os.environ.get("ZPP011_CLICK_DEBUG"))


def click_log(msg):
    """调试开关打开时追加一行日志；任何写盘失败都静默吞掉，绝不影响主流程。"""
    if not CLICK_DEBUG:
        return
    try:
        path = os.path.join(tempfile.gettempdir(), "zpp011_click.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass
