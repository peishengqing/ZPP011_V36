# -*- coding: utf-8 -*-
"""
ZPP011 PySide6 启动入口
裴哥 | 2026-06-04
"""
import sys
import os
import traceback

# 将项目根目录加入 sys.path，确保 gui_pyside6 可以正常导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ========== Windows 控制台环境优化（防卡死）==========
# 元凶1：快速编辑模式 —— 鼠标在控制台点一下就冻结所有 print 线程，按任意键才解
# 元凶2：后台限流 —— 窗口失焦时 Windows 降优先级 + 限制 CPU 频率
# 仅 Windows 生效，非 Windows / 无控制台环境静默跳过
if sys.platform == 'win32':
    try:
        import ctypes
        from ctypes import wintypes

        _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        _k32.GetCurrentProcess.restype = wintypes.HANDLE

        # --- 1. 关闭控制台「快速编辑模式」 ---
        STD_INPUT_HANDLE = -10
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080

        _k32.GetStdHandle.restype = wintypes.HANDLE
        _k32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        _k32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]

        _h_stdin = _k32.GetStdHandle(STD_INPUT_HANDLE)
        _mode = wintypes.DWORD()
        if _k32.GetConsoleMode(_h_stdin, ctypes.byref(_mode)):
            # 去掉 QUICK_EDIT，保留其余标志；必须同时设 EXTENDED_FLAGS 才能真正禁用
            _new_mode = (_mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
            _k32.SetConsoleMode(_h_stdin, _new_mode)

        # --- 2. 提高进程优先级（ABOVE_NORMAL，不抢实时优先级但高于普通） ---
        ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
        _k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        _k32.SetPriorityClass.restype = wintypes.BOOL
        _k32.SetPriorityClass(_k32.GetCurrentProcess(), ABOVE_NORMAL_PRIORITY_CLASS)

        # --- 3. 关闭电源限流（强制全速，Win8+） ---
        class _PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
            _fields_ = [
                ('Version', wintypes.ULONG),
                ('ControlMask', wintypes.ULONG),
                ('StateMask', wintypes.ULONG),
            ]

        _ppt = _PROCESS_POWER_THROTTLING_STATE()
        _ppt.Version = 1      # PROCESS_POWER_THROTTLING_CURRENT_VERSION
        _ppt.ControlMask = 0x1  # PROCESS_POWER_THROTTLING_EXECUTION_SPEED
        _ppt.StateMask = 0    # 0 = 关闭限速 → 全速运行

        _k32.SetProcessInformation.argtypes = [
            wintypes.HANDLE, wintypes.DWORD,
            ctypes.c_void_p, wintypes.ULONG,
        ]
        _k32.SetProcessInformation.restype = wintypes.BOOL
        _k32.SetProcessInformation(
            _k32.GetCurrentProcess(),
            4,                       # ProcessPowerThrottling（PROCESS_INFORMATION_CLASS 枚举值=4，实测 1 会报 87 参数错误）
            ctypes.byref(_ppt),
            ctypes.sizeof(_ppt),
        )
    except Exception:
        pass  # 环境优化失败不影响程序启动
# ========== 控制台环境优化结束 ==========

# ========== faulthandler：捕获原生崩溃（segfault）的 Python 堆栈 ==========
import faulthandler
# --windowed（无控制台）打包下 sys.stderr 会被置为 None，faulthandler.enable() 与
# traceback.print_exception 都会抛 RuntimeError: sys.stderr is None，导致启动即崩溃。
# 检测到无控制台时把 sys.stderr/stdout 重定向到日志文件后再启用 faulthandler 规避。
if sys.stderr is None:
    try:
        _err_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zpp011_stderr.log")
        sys.stderr = open(_err_log, "w", buffering=1)
        if sys.stdout is None:
            sys.stdout = sys.stderr
    except Exception:
        pass
faulthandler.enable()

# ========== 全局异常捕获 ==========
def global_exception_hook(exc_type, exc_value, exc_tb):
    """捕获未处理的异常，同时输出到控制台和弹窗"""
    # 1. 打印详细堆栈到控制台
    traceback.print_exception(exc_type, exc_value, exc_tb)

    # 2. 弹出错误对话框
    try:
        from PySide6.QtWidgets import QMessageBox, QApplication
        # 获取当前活跃的 QApplication 实例
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None,
                "严重错误",
                f"程序发生未捕获的异常:\n\n{str(exc_value)}\n\n详细错误信息已输出到日志文件 zpp011_stderr.log。"
            )
    except Exception:
        pass  # 如果弹窗失败，至少控制台已经有输出了

# 设置全局异常钩子
sys.excepthook = global_exception_hook
# ========== 全局异常捕获结束 ==========

from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtGui import QFont
from PySide6.QtCore import QCoreApplication, QSettings, QLocale, Qt, QTimer

from gui_pyside6.main_window import MainWindow


def main():
    # 高 DPI 支持（PySide6 >= 6.5 自动处理，无需手动设置）
    # 保留这两行是为了兼容旧版本，在新版本中无效果也不会报错
    # QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # Qt 6 已默认支持
    # QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # Qt 6 已默认支持

    app = QApplication(sys.argv)
    app.setApplicationName("ZPP011")
    from utils.version_history import get_current_version
    app.setApplicationVersion(get_current_version())
    app.setOrganizationName("云南达利食品有限公司")

    # 设置字体（中文友好）
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    # Fusion 样式 + 自定义 QSS 样式表
    if "Fusion" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Fusion"))

    # 注意：app 级别不加载 style.qss，因为暗色主题由 MainWindow._load_dark_theme() 内部管控
    # 如果未来需要 app 级全局样式，可以在此加载 light_theme.qss 作为基准

    win = MainWindow()
    win.showMaximized()

    # --- DEBUG 诊断：七连败后用数据定位根因（v43.25） ---
    # 打印每个关键节点的窗口实际尺寸和状态，从控制台输出定位覆盖源。
    if sys.platform == 'win32':
        import ctypes.wintypes as wintypes

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        WINDOWPLACEMENT = ctypes.Structure.__class__(
            "WINDOWPLACEMENT", (ctypes.Structure,), {
                "_fields_": [
                    ("length", ctypes.c_uint),
                    ("flags", ctypes.c_uint),
                    ("showCmd", ctypes.c_uint),
                    ("ptMinPosition", wintypes.POINT),
                    ("ptMaxPosition", wintypes.POINT),
                    ("rcNormalPosition", RECT),
                ]
            }
        )
        wp = WINDOWPLACEMENT()
        wp.length = ctypes.sizeof(WINDOWPLACEMENT)

        def _debug_window_state(tag):
            try:
                hwnd = int(win.winId())
                # GetWindowPlacement 获取 showCmd: 1=Normal, 3=Maximized
                ctypes.windll.user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
                # GetWindowRect 获取屏幕坐标
                rc = RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc))
                w = rc.right - rc.left
                h = rc.bottom - rc.top
                state_name = {1: "NORMAL", 2: "MINIMIZED", 3: "MAXIMIZED"}.get(wp.showCmd, f"UNKNOWN({wp.showCmd})")
                print(f"[MAXIMIZE-DEBUG] {tag}: showCmd={state_name}, "
                      f"rect=({rc.left},{rc.top},{rc.right},{rc.bottom}), size={w}x{h}")
            except Exception as e:
                print(f"[MAXIMIZE-DEBUG] {tag}: ERROR - {e}")

        _debug_window_state("1-showMaximized()之后")

        def _force_maximize():
            try:
                _hwnd = int(win.winId())
                if not _hwnd:
                    return
                ctypes.windll.user32.ShowWindow(_hwnd, 3)
                SWP_FRAMECHANGED = 0x0020
                SWP_NOZORDER = 0x0004
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                ctypes.windll.user32.SetWindowPos(
                    _hwnd, None, 0, 0, 0, 0,
                    SWP_FRAMECHANGED | SWP_NOZORDER | SWP_NOMOVE | SWP_NOSIZE
                )
                _debug_window_state("Win32_ShowWindow+SetWindowPos之后")
            except Exception as e:
                print(f"[MAXIMIZE-DEBUG] Win32调用异常: {e}")

        _force_maximize()
        QTimer.singleShot(100, lambda: (_force_maximize(), _debug_window_state("QTimer-100ms")))
        QTimer.singleShot(500, lambda: (_force_maximize(), _debug_window_state("QTimer-500ms")))
        QTimer.singleShot(1000, lambda: _debug_window_state("QTimer-1000ms(最终)"))
    else:
        pass

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
