# -*- coding: utf-8 -*-
"""主表「投料为负」标红必须覆盖替代料行（v43.208 修复：红标优先级压过替代料组色）。

根因：data() 的 BackgroundRole 先查替代料组色再查 neg_feed 红标，导致
「替代料 + 实际<0」的行被组色盖掉、不显示红标。修复后 neg_feed 红标为最高优先级，
任何实际<0 的行（无论是否替代料）一律红。
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from gui_pyside6.models.data_frame_model import DataFrameModel

pytest.importorskip("PySide6")


def _model():
    df = pd.DataFrame([
        # 行0：替代料（有 _替代料组，组色本应盖住其他标记）
        {"data_id": "A|1|1|1", "是否替代料": "是", "组件物料描述": "替代料X",
         "数量-实际": -3.0, "数量-定额": 10.0, "_替代料组": "G1"},
        # 行1：正常料 实际<0
        {"data_id": "A|1|1|2", "是否替代料": "否", "组件物料描述": "普通料",
         "数量-实际": -2.0, "数量-定额": 10.0},
        # 行2：正常料 实际>0（对照，不应红）
        {"data_id": "A|1|1|3", "是否替代料": "否", "组件物料描述": "正常",
         "数量-实际": 5.0, "数量-定额": 10.0},
    ])
    return DataFrameModel(df)


def test_neg_feed_rows_include_alt_and_normal():
    m = _model()
    assert 0 in m._neg_feed_rows, "替代料实际<0 应计入 _neg_feed_rows"
    assert 1 in m._neg_feed_rows, "正常料实际<0 应计入 _neg_feed_rows"
    assert 2 not in m._neg_feed_rows, "实际>0 不应计入 _neg_feed_rows"


def test_neg_feed_red_priority_over_alt_group_color():
    """替代料行的红标必须压过替代料组色——这是 v43.208 修复的核心。"""
    m = _model()
    for row in (0, 1):
        bg = m.data(m.index(row, 2), Qt.BackgroundRole)
        assert bg is not None, f"row {row} 应有背景色"
        assert (bg.red(), bg.green(), bg.blue()) == (255, 150, 150), \
            f"row {row} 应整行标红(255,150,150)，实际 {(bg.red(), bg.green(), bg.blue())}"
    # 对照：实际>0 的行不应是红标
    bg2 = m.data(m.index(2, 2), Qt.BackgroundRole)
    assert (bg2 is None) or (bg2.red(), bg2.green(), bg2.blue()) != (255, 150, 150)
