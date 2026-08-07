# -*- coding: utf-8 -*-
"""PySide6 迁移核心模块测试（无需 GUI 窗口）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import tempfile
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from gui_pyside6.models.data_frame_model import DataFrameModel
from core.rule_engine import RuleEngine
from core.import_handlers import import_alt_pairs_from_excel

# ---------- Qt Application Fixture ----------
@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------- TestDataFrameModel ----------
class TestDataFrameModel:
    def test_row_count(self, qapp):
        df = pd.DataFrame({"A": [1, 2], "B": ["a", "b"]})
        model = DataFrameModel(df)
        assert model.rowCount() == 2
        # setDataFrame 会在最前插入 _read / _read_source 两列（已读状态），故列数 = 数据列 + 2
        assert model.columnCount() == 4

    def test_display_role(self, qapp):
        df = pd.DataFrame({"A": [1, 2]})
        model = DataFrameModel(df)
        # 第0列是已读状态列（未读显示 🔘），第1列是已读来源；数据列 A 前移 2 位
        assert model.data(model.index(0, 0)) == "🔘"
        assert model.data(model.index(0, 2)) == "1"
        assert model.data(model.index(1, 2)) == "2"

    def test_edit_enabled_only_remark(self, qapp):
        df = pd.DataFrame({"备注": ["x"], "其他": ["y"]})
        model = DataFrameModel(df)
        # 模型为只读：备注列不再可编辑（人工改备注会污染已读变更检测基线）
        # setDataFrame 插入 2 个元列（_read, _read_source），数据列位置整体后移 2
        meta = 2
        idx = model.index(0, meta + df.columns.get_loc("备注"))
        assert not (model.flags(idx) & Qt.ItemIsEditable)
        idx2 = model.index(0, meta + df.columns.get_loc("其他"))
        assert not (model.flags(idx2) & Qt.ItemIsEditable)

    def test_set_data_is_readonly(self, qapp):
        df = pd.DataFrame({"备注": [""]})
        model = DataFrameModel(df)
        # 第0列是只读的已读状态列，备注列在数据列首位（元列之后，即第 2 列）
        idx = model.index(0, 2)
        # 模型只读：setData 返回 False 且 DataFrame 不被修改
        assert model.setData(idx, "新备注", Qt.EditRole) is False
        assert model.getDataFrame().iloc[0]["备注"] == ""


# ---------- TestRuleEngine ----------
class TestRuleEngine:
    def test_should_ai_audit_high_dev_no_remark(self):
        engine = RuleEngine()
        assert engine.should_ai_audit(15.0, "") is True

    def test_should_ai_audit_low_dev_with_remark(self):
        engine = RuleEngine()
        assert engine.should_ai_audit(5.0, "已备注") is False

    def test_should_ai_audit_zero_dev(self):
        engine = RuleEngine()
        assert engine.should_ai_audit(0.0, "") is False

    def test_check_auto_close_condition(self):
        engine = RuleEngine()
        row = {"审核状态": "已审核", "备注原因": "test"}
        result = engine.check_auto_close_condition(row)
        assert isinstance(result, bool)

    def test_get_band_color(self):
        engine = RuleEngine()
        # get_band_color 是 get_color_for_deviation_rate 的别名
        color = engine.get_band_color(15.0)
        assert isinstance(color, str)
        assert color.startswith("#")


# ---------- TestImportHandler ----------
class TestImportHandler:
    def test_alt_import_basic(self):
        data = [{"工厂名称": "厂A", "物料A编码": "A1", "物料A名称": "A1名",
                 "物料B编码": "B1", "物料B名称": "B1名"}]
        current = []
        result = import_alt_pairs_from_excel(data, current, overwrite=False)
        assert len(result) == 1
        # pair = ((factory, code_a, name_a), (factory, code_b, name_b))
        assert result[0][0][1] == "A1"
        assert result[0][1][1] == "B1"

    def test_alt_import_dedup(self):
        data = [{"工厂名称": "厂A", "物料A编码": "A1", "物料A名称": "A1名",
                 "物料B编码": "B1", "物料B名称": "B1名"}]
        current = []
        result = import_alt_pairs_from_excel(data, current, overwrite=False)
        # 再次导入相同数据，去重后长度仍为 1
        result2 = import_alt_pairs_from_excel(data, result, overwrite=False)
        assert len(result2) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
