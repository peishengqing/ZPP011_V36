# -*- coding: utf-8 -*-
"""整改回归：EventBus 单例复位可用（v43.406，审核报告 P1-5）。

原实现 `reset(self)` 是实例方法却引用 `cls`，而调用方 `reset_event_bus()` 又按
类调用 `EventBus.reset()` —— 两条路径都错（NameError / TypeError）。改为
classmethod 后：类调用、实例调用、模块级 reset_event_bus() 三者均可用。
"""
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_class_level_reset_works(qapp):
    from gui_pyside6.models.event_bus import EventBus

    EventBus._instance = None
    first = EventBus.get()
    assert EventBus.get() is first, "单例语义：两次 get 应返回同一对象"

    EventBus.reset()          # 原实现：TypeError（缺 self）/ NameError（cls 未定义）
    assert EventBus._instance is None
    assert EventBus.get() is not first, "reset 之后应能拿到新实例"


def test_instance_level_reset_still_works(qapp):
    from gui_pyside6.models.event_bus import EventBus

    EventBus._instance = None
    bus = EventBus.get()
    bus.reset()               # 兼容旧用法（实例调用 classmethod）
    assert EventBus._instance is None


def test_module_level_reset_event_bus(qapp):
    from gui_pyside6.models import event_bus as mod

    EventBus = mod.EventBus
    EventBus._instance = None
    mod._event_bus = None
    assert mod.get_event_bus() is not None
    mod.reset_event_bus()     # 原实现：走到 EventBus.reset() 即崩
    assert mod._event_bus is None
