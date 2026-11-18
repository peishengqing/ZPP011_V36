# -*- coding: utf-8 -*-
"""标题栏「全部 / 食品 / 饮料」三段开关用例（v44.01）。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui_pyside6.components.title_bar import TitleBarWidget  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def bar(app):
    w = TitleBarWidget("v44.01")
    yield w
    w.deleteLater()


def test_defaults_to_all_and_locks_factories_before_data(bar):
    assert bar.current_factory_key() == "全部"
    assert bar._factory_buttons["全部"].isChecked()
    assert not bar._factory_buttons["1101"].isEnabled()
    assert not bar._factory_buttons["1102"].isEnabled()


def test_available_factories_unlock_buttons(bar):
    bar.set_available_factories(["全部", "1101食品", "1102"])
    assert bar._factory_buttons["1101"].isEnabled()
    assert bar._factory_buttons["1102"].isEnabled()


def test_missing_factory_stays_disabled(bar):
    bar.set_available_factories(["全部", "1102"])
    assert not bar._factory_buttons["1101"].isEnabled()
    assert bar._factory_buttons["1102"].isEnabled()


def test_clicking_food_emits_1101(bar):
    bar.set_available_factories(["全部", "1101", "1102"])
    got = []
    bar.factory_selected.connect(got.append)
    bar._factory_buttons["1101"].click()
    assert got == ["1101"]


def test_clicking_beverage_emits_1102(bar):
    bar.set_available_factories(["全部", "1101", "1102"])
    got = []
    bar.factory_selected.connect(got.append)
    bar._factory_buttons["1102"].click()
    assert got == ["1102"]


def test_set_current_factory_syncs_display_name(bar):
    bar.set_available_factories(["全部", "1101食品", "1102"])
    bar.set_current_factory("1101食品")
    assert bar.current_factory_key() == "1101"
    bar.set_current_factory("全部")
    assert bar.current_factory_key() == "全部"


def test_set_current_factory_falls_back_when_disabled(bar):
    bar.set_available_factories(["全部", "1101"])
    bar.set_current_factory("1102")
    assert bar.current_factory_key() == "全部"
