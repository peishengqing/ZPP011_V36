# -*- coding: utf-8 -*-
"""
文件监控控制器（ARC-003 第十刀，v43.206）

负责：文件夹监控、文件自动加载、占用检测等文件监控相关逻辑从 MainWindow 切出，
避免 God Object 持续膨胀。

模式：组合式。本控制器持有 MainWindow 引用（self.mw），方法体从 MainWindow
原样搬迁、逻辑零改动；MainWindow 侧保留同名薄壳转发，保证外部既有调用
（如工具栏按钮、菜单）签名不变。

import 来源说明：原方法体依赖 main_window.py 顶部的 os / QTimer 等，
本模块自行 import 同名对象，行为完全一致。
"""

import os
from PySide6.QtCore import QTimer


class FileMonitorController:
    """文件监控控制器（文件夹监控、自动加载、占用检测）"""

    def __init__(self, mw):
        self.mw = mw
        # 监控配置（与 MainWindow 中的值保持一致）
        self._monitor_dir = r"E:\ZPP011导出文件原数据"
        self._monitor_enabled = True
        self._monitor_timer = QTimer(self.mw)
        self._monitor_timer.setInterval(2000)  # 每 2 秒扫描一次
        self._monitor_last_size = {}  # path -> 上次文件大小
        self._monitor_loaded = set()  # (path, mtime, size) 已自动加载的文件指纹
        self._monitor_pending = set()  # (path, mtime, size) 已排队等待加载
        self._monitor_current_key = None  # 当前正在自动加载的文件指纹
        self._monitor_auto_loading = False  # 是否正在由监控触发自动加载
        self._monitor_delay_ms = 5000  # 延迟加载毫秒数
        self._monitor_busy_retry = 6  # 重试次数
        self._monitor_busy_interval = 3000  # 重试间隔(ms)

    # ═══════════════ 工具方法 ═══════════════

    def _is_monitor_accepted_file(self, fname):
        """判断文件名是否被监控接受（基于后缀和名称模式）"""
        fn, ext = os.path.splitext(fname)
        if ext.lower() not in (".xlsx", ".xls"):
            return False
        return True

    # ═══════════════ 监控开关 ═══════════════

    def _toggle_folder_monitor(self, checked):
        """工具栏/菜单开关：监控 E:/ZPP011导出文件原数据 目录，发现新 Excel 自动加载。"""
        self._monitor_enabled = checked
        if checked:
            # 开始监控：重置稳定性缓存，保留已加载指纹（同名文件重新导出仍可识别）
            self._monitor_last_size = {}
            if not os.path.isdir(self._monitor_dir):
                self.mw.log(f"⚠️ 监控目录不存在：{self._monitor_dir}", "warning")
            else:
                self.mw.log(f"👁 已开始监控文件夹：{self._monitor_dir}", "info")
            self._monitor_timer.start()
        else:
            self._monitor_timer.stop()
            self.mw.log("⏹ 已停止监控文件夹", "info")

    # ═══════════════ 基线设置 ═══════════════

    def _seed_monitor_baseline(self):
        """默认开启时调用：把当前目录里最新文件登记为基线，避免启动即触发一次分析，
        之后只有比基线更新的导出文件才会被自动加载。"""
        d = self._monitor_dir
        if not os.path.isdir(d):
            return
        try:
            files = [os.path.join(d, f) for f in os.listdir(d)
                     if f.lower().endswith((".xlsx", ".xls")) and self._is_monitor_accepted_file(f)]
        except Exception:
            return
        if not files:
            return
        def _mtime(fp):
            try:
                return os.stat(fp).st_mtime
            except Exception:
                return 0
        files.sort(key=_mtime, reverse=True)
        fp = os.path.normpath(files[0])
        try:
            st = os.stat(fp)
        except Exception:
            return
        self._monitor_last_size[fp] = st.st_size
        self._monitor_loaded.add((fp, int(st.st_mtime), st.st_size))

    # ═══════════════ 目录扫描 ═══════════════

    def _scan_monitor_dir(self):
        """扫描监控目录，发现新文件后延迟加载。"""
        if not self._monitor_enabled:
            return
        d = self._monitor_dir
        if not os.path.isdir(d):
            return
        try:
            files = [os.path.join(d, f) for f in os.listdir(d)
                     if f.lower().endswith((".xlsx", ".xls")) and self._is_monitor_accepted_file(f)]
        except Exception:
            return
        if not files:
            return
        # 只盯「最新」文件：按 mtime 降序取第一个，避免 NTFS 下列出顺序不定导致加载到旧文件
        def _mtime(fp):
            try:
                return os.stat(fp).st_mtime
            except Exception:
                return 0
        files.sort(key=_mtime, reverse=True)
        fp = os.path.normpath(files[0])
        try:
            st = os.stat(fp)
        except Exception:
            return
        # 稳定性判定：与上次的 size 比较，连续两次相同且 >0 视为写完，避免读半截文件
        prev = self._monitor_last_size.get(fp)
        if prev is None:
            self._monitor_last_size[fp] = st.st_size
            return
        if prev != st.st_size:
            self._monitor_last_size[fp] = st.st_size
            return
        key = (fp, int(st.st_mtime), st.st_size)
        if key in self._monitor_loaded:
            return
        # 已在等待加载队列中，避免重复排队
        if key in self._monitor_pending:
            return
        # 新稳定文件（且是当前目录最新）-> 延迟加载
        self._monitor_pending.add(key)
        self.mw.log(f"📥 监控到新文件，{self._monitor_delay_ms // 1000} 秒后自动加载：{os.path.basename(fp)}（若已自动打开请先关闭）", "info")
        QTimer.singleShot(self._monitor_delay_ms, lambda: self._monitor_try_load(fp, key))

    # ═══════════════ 文件占用检测 ═══════════════

    def _monitor_file_busy(self, fp):
        """检测文件是否被占用（与 analyzer 的占用判定一致：以 r+b 方式打开尝试）。"""
        try:
            with open(fp, "r+b"):
                pass
            return False
        except PermissionError:
            return True
        except Exception:
            return False

    # ═══════════════ 加载重试 ═══════════════

    def _monitor_try_load(self, fp, key, attempt=0):
        """延迟后真正加载：若文件仍被占用（预览窗口未关闭），自动重试若干次；
        重试耗尽则放弃本次，等下次扫描重新触发，避免直接报「被占用」。"""
        if not self._monitor_enabled:
            self._monitor_pending.discard(key)
            return
        if self._monitor_file_busy(fp):
            if attempt < self._monitor_busy_retry:
                QTimer.singleShot(self._monitor_busy_interval,
                                  lambda: self._monitor_try_load(fp, key, attempt + 1))
                return
            # 重试耗尽：移除排队标记，下次扫描会重新检测到该文件并再次尝试
            self._monitor_pending.discard(key)
            self.mw.log(f"⚠️ 文件仍被占用，暂未加载：{os.path.basename(fp)}（关闭预览后将被自动重新检测）", "warning")
            return
        # 文件可用 -> 正式加载（记录指纹 + 移除排队 + 标记为监控自动加载）
        self._monitor_pending.discard(key)
        self._monitor_loaded.add(key)
        self._monitor_current_key = key
        self._monitor_auto_loading = True
        self._auto_load_from_monitor(fp)

    # ═══════════════ 自动加载 ═══════════════

    def _auto_load_from_monitor(self, fp):
        """监控到新文件：写入当前输入文件并触发分析加载（复用主流程）。"""
        fp = os.path.normpath(fp)
        # 若分析/缓存/导出等重型操作正在进行，稍后重试（避免并发 do_analysis_v2 卡死 UI）
        if self.mw._heavy_busy or (self.mw.analysis_controller.worker and self.mw.analysis_controller.worker.isRunning()):
            # 延迟 3 秒再试一次，期间仍视为监控自动加载
            QTimer.singleShot(3000, lambda: self._auto_load_from_monitor(fp))
            return
        self.mw.current_input_file = fp
        if hasattr(self.mw, "input_file_edit") and self.mw.input_file_edit:
            self.mw.input_file_edit.setText(os.path.basename(fp))
            self.mw.input_file_edit.setToolTip(fp)
        self.mw.log(f"📥 监控到新文件，自动加载：{os.path.basename(fp)}", "info")
        self._monitor_auto_loading = True
        self.mw._start_analysis()
