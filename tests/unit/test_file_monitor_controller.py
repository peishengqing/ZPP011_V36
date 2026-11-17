# -*- coding: utf-8 -*-
"""FileMonitorController「已加载登记」（v43.388）回归测试。

场景：文件已加载成功（手动选择或监控自动加载），但该文件随后被 Excel/WPS
占用（_monitor_file_busy=True）。修复前监控每轮扫描都把它当新文件排队、
占用重试、放弃、再排队，每 ~24 秒刷一轮日志、永不停止；修复后
mark_file_loaded 登记指纹，同一版本静默跳过；文件重新导出（指纹变化）
仍会照常触发自动加载。
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QObject  # noqa: E402

from gui_pyside6.controllers.file_monitor_controller import (  # noqa: E402
    FileMonitorController,
)


class _FakeMW(QObject):
    """最小 MainWindow 替身：监控控制器只用到 current_input_file / log / QTimer 父对象。"""

    def __init__(self):
        super().__init__()
        self.current_input_file = None
        self._heavy_busy = False
        self.logs = []

    def log(self, msg, level="info"):
        self.logs.append((level, msg))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def ctrl(qapp, tmp_path):
    mw = _FakeMW()
    c = FileMonitorController(mw)
    c._monitor_dir = str(tmp_path)      # 指向临时目录，绝不碰真实监控目录
    c._monitor_delay_ms = 0             # 立即触发加载尝试（无事件循环则不会真跑）
    return c


def _write_excel_like(path, size=100):
    with open(path, "wb") as f:
        f.write(b"x" * size)
    return str(path)


def _key(fp):
    st = os.stat(fp)
    return (os.path.normpath(fp), int(st.st_mtime), st.st_size)


def test_mark_file_loaded_registers_fingerprint(ctrl, tmp_path):
    fp = _write_excel_like(tmp_path / "a.xlsx")
    ctrl.mark_file_loaded(fp)
    assert _key(fp) in ctrl._monitor_loaded


def test_loaded_file_not_requeued_even_if_busy(ctrl, tmp_path):
    """核心回归：已登记的文件即使被占用，扫描也不再排队/刷「监控到新文件」。"""
    fp = _write_excel_like(tmp_path / "b.xlsx")
    ctrl.mark_file_loaded(fp)
    ctrl._monitor_file_busy = lambda p: True   # 模拟被 Excel/WPS 占用
    ctrl._scan_monitor_dir()                   # 第 1 轮：建立 size 基线
    ctrl._scan_monitor_dir()                   # 第 2 轮：稳定 → 应命中已加载指纹直接跳过
    assert ctrl._monitor_pending == set()
    assert not any("监控到新文件" in m for _lvl, m in ctrl.mw.logs)
    assert not any("被占用" in m for _lvl, m in ctrl.mw.logs)


def test_new_file_still_triggers(ctrl, tmp_path):
    """未登记的新文件仍照常排队提示（监控主功能不回归）。"""
    _write_excel_like(tmp_path / "c.xlsx")
    ctrl._scan_monitor_dir()
    ctrl._scan_monitor_dir()
    assert any("监控到新文件" in m for _lvl, m in ctrl.mw.logs)
    assert len(ctrl._monitor_pending) == 1


def test_reexport_triggers_again(ctrl, tmp_path):
    """同名文件重新导出（大小/mtime 变化 → 指纹不同）仍会再次排队自动加载。"""
    fp = _write_excel_like(tmp_path / "d.xlsx", size=100)
    ctrl.mark_file_loaded(fp)
    _write_excel_like(tmp_path / "d.xlsx", size=200)      # 重新导出：内容变化
    os.utime(fp, (time.time() + 10, time.time() + 10))    # 确保 mtime 变化
    assert _key(fp) != next(iter(ctrl._monitor_loaded))   # 指纹确已不同
    ctrl._monitor_last_size.pop(os.path.normpath(fp), None)
    ctrl._scan_monitor_dir()
    ctrl._scan_monitor_dir()
    assert any("监控到新文件" in m for _lvl, m in ctrl.mw.logs)
    assert len(ctrl._monitor_pending) == 1


def test_mark_file_loaded_tolerates_bad_path(ctrl):
    """登记对无效路径静默容忍（不抛异常、不崩监控、不误登记）。"""
    ctrl.mark_file_loaded(None)
    ctrl.mark_file_loaded("Z:/不存在的目录/不存在.xlsx")
    assert ctrl._monitor_loaded == set()
