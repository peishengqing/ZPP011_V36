# -*- coding: utf-8 -*-
"""file_launcher.py — 跨平台「用系统默认程序打开文件/文件夹」唯一实现

背景（v43.257 收口 GUI-001 / GUI-001b）：
    审计提出 `os.startfile` 只有 Windows 能用。实际代码里三处早就写了平台分发
    （Windows=os.startfile / macOS=open / Linux=xdg-open，见 d676c1b），
    但留下四个真问题：
      ① 同一段分发在 4 处重复（export_controller / ppt_controller /
         main_window._open_file / main_window 打开备份目录内联一份）；
      ② 只有 main_window 那份有 try/except，另三处打开失败会直接把异常抛给调用方 ——
         于是「导出成功了但系统打不开」会演变成一个写着「导出失败」的误导性弹窗；
      ③ macOS/Linux 用 subprocess.run 不带 check，打不开时静默无感；
      ④ 没有 xdg-open 的精简 Linux 环境没有任何回退。

本模块是唯一实现，行为与原来的 Windows 路径完全一致（os.startfile 仍是首选），
只补：异常不外抛、失败可记日志、无 xdg-open 时回退 Qt QDesktopServices。

调用约定：任何地方要「打开文件/文件夹」都调 open_path()，不要再各自写平台判断。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import traceback


def _safe_log(log_cb, msg: str, level: str = "error") -> None:
    """日志回调三层兜底：先按 (msg, level) 调，不行按 (msg) 调，再不行静默。

    项目里 self.log 的签名是 (msg, level)，但有些调用方只收一个参数；
    少传/多传参数会抛 TypeError，把「打不开文件」这个原始问题顶掉。
    """
    if log_cb is None:
        return
    try:
        log_cb(msg, level)
    except TypeError:
        try:
            log_cb(msg)
        except Exception:
            pass
    except Exception:
        pass


def open_path(path, log_cb=None) -> bool:
    """用系统默认程序打开文件/文件夹。成功发起打开返回 True，失败返回 False。

    永不抛异常：打开失败只打 traceback + 记日志，由调用方决定要不要提示用户。
    这样「导出成功但打不开」不会被误报成「导出失败」。
    """
    p = str(path)
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(p)  # 与原实现一致：Windows 首选 ShellExecute
            return True
        if system == "Darwin":
            subprocess.run(["open", p], check=False)
            return True
        if shutil.which("xdg-open"):
            subprocess.run(["xdg-open", p], check=False)
            return True
        # 没有 xdg-open 的精简 Linux：回退 Qt 自带的打开机制
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
    except Exception as e:
        # 用户可见链路禁止静默：traceback 进日志，调用方拿到 False 自行决定提示
        traceback.print_exc()
        _safe_log(log_cb, f"无法打开 {p}: {e}", "error")
        return False
