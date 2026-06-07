# -*- coding: utf-8 -*-
# 此脚本生成 tests/test_pyside6_migration.py
import os

Q = '"'  # ASCII double quote
Q3 = "''"  # triple single quotes for wrapping strings with quotes

def w(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Written: {path}')

# Build test file content line by line, using Q for all strings
P = '    '  # indent

content = f'''# -*- coding: utf-8 -*-
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
        df = pd.DataFrame({{Q}A{Q}: [1, 2], {Q}B{Q}: [{Q}a{Q}, {Q}b{Q}]}})
        model = DataFrameModel(df)
        assert model.rowCount() == 2
        assert model.columnCount() == 2

    def test_display_role(self, qapp):
        df = pd.DataFrame({{Q}A{Q}: [1, 2]}})
        model = DataFrameModel(df)
        assert model.data(model.index(0, 0)) == {Q}1{Q}
        assert model.data(model.index(1, 0)) == {Q}2{Q}

    def test_edit_enabled_only_remark(self, qapp):
        df = pd.DataFrame({{Q}备注{Q}: [{Q}x{Q}], {Q}其他{Q}: [{Q}y{Q}]}})
        model = DataFrameModel(df)
        idx = model.index(0, df.columns.get_loc({Q}备注{Q}))
        assert model.flags(idx) & Qt.ItemIsEditable
        idx2 = model.index(0, df.columns.get_loc({Q}其他{Q}))
        assert not (model.flags(idx2) & Qt.ItemIsEditable)

    def test_set_data_updates_df(self, qapp):
        df = pd.DataFrame({{Q}备注{Q}: [{Q}{Q}]}})
        model = DataFrameModel(df)
        idx = model.index(0, 0)
        assert model.setData(idx, {Q}新备注{Q}, Qt.EditRole) is True
        assert model.getDataFrame().iloc[0][{Q}备注{Q}] == {Q}新备注{Q}


# ---------- TestRuleEngine ----------
class TestRuleEngine:
    def test_should_ai_audit_high_dev_no_remark(self):
        engine = RuleEngine()
        assert engine.should_ai_audit(15.0, {Q}{Q}) is True

    def test_should_ai_audit_low_dev_with_remark(self):
        engine = RuleEngine()
        assert engine.should_ai_audit(5.0, {Q}已备注{Q}) is False

    def test_should_ai_audit_zero_dev(self):
        engine = RuleEngine()
        assert engine.should_ai_audit(0.0, {Q}{Q}) is False

    def test_check_auto_close_condition(self):
        engine = RuleEngine()
        row = {{Q}审核状态{Q}: {Q}已审核{Q}, {Q}备注原因{Q}: {Q}test{Q}}}
        result = engine.check_auto_close_condition(row)
        assert isinstance(result, bool)

    def test_get_band_color(self):
        engine = RuleEngine()
        color = engine.get_band_color(15.0)
        assert isinstance(color, str)
        assert color.startswith({Q}#{Q})


# ---------- TestImportHandler ----------
class TestImportHandler:
    def test_alt_import_basic(self):
        data = [{{{Q}工厂名称{Q}: {Q}厂A{Q}, {Q}物料A编码{Q}: {Q}A1{Q}, {Q}物料A名称{Q}: {Q}A1名{Q},
                  {Q}物料B编码{Q}: {Q}B1{Q}, {Q}物料B名称{Q}: {Q}B1名{Q}}}]
        current = []
        result = import_alt_pairs_from_excel(data, current, overwrite=False)
        assert len(result) == 1
        assert result[0][{Q}alt_material_code{Q}] == {Q}B1{Q}

    def test_alt_import_dedup(self):
        data = [{{{Q}工厂名称{Q}: {Q}厂A{Q}, {Q}物料A编码{Q}: {Q}A1{Q}, {Q}物料A名称{Q}: {Q}A1名{Q},
                  {Q}物料B编码{Q}: {Q}B1{Q}, {Q}物料B名称{Q}: {Q}B1名{Q}}}]
        current = []
        result = import_alt_pairs_from_excel(data, current, overwrite=False)
        result2 = import_alt_pairs_from_excel(data, result, overwrite=False)
        assert len(result2) >= 1


if __name__ == {Q}__main__{Q}:
    pytest.main([__file__, {Q}-v{Q}])
'''

# The above has {{Q}} which we need to replace with actual quotes
# Let's do it differently - write raw lines

base = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(base, 'test_pyside6_migration.py')

lines = []
a = lines.append

# Use simple ASCII string building
D = '"'   # double quote
S = "'"   # single quote

a('# -*- coding: utf-8 -*-')
a('"""PySide6 迁移核心模块测试（无需 GUI 窗口）"""')
a('import sys, os')
a('sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))')
a('')
a('import pytest')
a('import pandas as pd')
a('import tempfile')
a('import json')
a('')
a('from PySide6.QtCore import Qt')
a('from PySide6.QtWidgets import QApplication')
a('from gui_pyside6.models.data_frame_model import DataFrameModel')
a('from core.rule_engine import RuleEngine')
a('from core.import_handlers import import_alt_pairs_from_excel')
a('')
a('')
a('# ---------- Qt Application Fixture ----------')
a('@pytest.fixture(scope=' + D + 'session' + D + ', autouse=True)')
a('def qapp():')
a('    app = QApplication.instance()')
a('    if app is None:')
a('        app = QApplication([])')
a('    return app')
a('')
a('')
a('# ---------- TestDataFrameModel ----------')
a('class TestDataFrameModel:')
a('    def test_row_count(self, qapp):')
a('        df = pd.DataFrame({' + D + 'A' + D + ': [1, 2], ' + D + 'B' + D + ': [' + D + 'a' + D + ', ' + D + 'b' + D + ']}')
a('        model = DataFrameModel(df)')
a('        assert model.rowCount() == 2')
a('        assert model.columnCount() == 2')
a('')
a('    def test_display_role(self, qapp):')
a('        df = pd.DataFrame({' + D + 'A' + D + ': [1, 2]})')
a('        model = DataFrameModel(df)')
a('        assert model.data(model.index(0, 0)) == ' + D + '1' + D)
a('        assert model.data(model.index(1, 0)) == ' + D + '2' + D)
a('')
a('    def test_edit_enabled_only_remark(self, qapp):')
a('        df = pd.DataFrame({' + D + '备注' + D + ': [' + D + 'x' + D + '], ' + D + '其他' + D + ': [' + D + 'y' + D + ']})')
a('        model = DataFrameModel(df)')
a('        idx = model.index(0, df.columns.get_loc(' + D + '备注' + D + '))')
a('        assert model.flags(idx) & Qt.ItemIsEditable')
a('        idx2 = model.index(0, df.columns.get_loc(' + D + '其他' + D + '))')
a('        assert not (model.flags(idx2) & Qt.ItemIsEditable)')
a('')
a('    def test_set_data_updates_df(self, qapp):')
a('        df = pd.DataFrame({' + D + '备注' + D + ': [' + D + D + ']})')
a('        model = DataFrameModel(df)')
a('        idx = model.index(0, 0)')
a('        assert model.setData(idx, ' + D + '新备注' + D + ', Qt.EditRole) is True')
a('        assert model.getDataFrame().iloc[0][' + D + '备注' + D + '] == ' + D + '新备注' + D)
a('')
a('')
a('# ---------- TestRuleEngine ----------')
a('class TestRuleEngine:')
a('    def test_should_ai_audit_high_dev_no_remark(self):')
a('        engine = RuleEngine()')
a('        assert engine.should_ai_audit(15.0, ' + D + D + ') is True')
a('')
a('    def test_should_ai_audit_low_dev_with_remark(self):')
a('        engine = RuleEngine()')
a('        assert engine.should_ai_audit(5.0, ' + D + '已备注' + D + ') is False')
a('')
a('    def test_should_ai_audit_zero_dev(self):')
a('        engine = RuleEngine()')
a('        assert engine.should_ai_audit(0.0, ' + D + D + ') is False')
a('')
a('    def test_check_auto_close_condition(self):')
a('        engine = RuleEngine()')
a('        row = {' + D + '审核状态' + D + ': ' + D + '已审核' + D + ', ' + D + '备注原因' + D + ': ' + D + 'test' + D + '}')
a('        result = engine.check_auto_close_condition(row)')
a('        assert isinstance(result, bool)')
a('')
a('    def test_get_band_color(self):')
a('        engine = RuleEngine()')
a('        color = engine.get_band_color(15.0)')
a('        assert isinstance(color, str)')
a('        assert color.startswith(' + D + '#' + D + ')')
a('')
a('')
a('# ---------- TestImportHandler ----------')
a('class TestImportHandler:')
a('    def test_alt_import_basic(self):')
a('        data = [{' + D + '工厂名称' + D + ': ' + D + '厂A' + D + ', ' + D + '物料A编码' + D + ': ' + D + 'A1' + D + ', ' + D + '物料A名称' + D + ': ' + D + 'A1名' + D + ',')
a('                 ' + D + '物料B编码' + D + ': ' + D + 'B1' + D + ', ' + D + '物料B名称' + D + ': ' + D + 'B1名' + D + '}]')
a('        current = []')
a('        result = import_alt_pairs_from_excel(data, current, overwrite=False)')
a('        assert len(result) == 1')
a('        assert result[0][' + D + 'alt_material_code' + D + '] == ' + D + 'B1' + D)
a('')
a('    def test_alt_import_dedup(self):')
a('        data = [{' + D + '工厂名称' + D + ': ' + D + '厂A' + D + ', ' + D + '物料A编码' + D + ': ' + D + 'A1' + D + ', ' + D + '物料A名称' + D + ': ' + D + 'A1名' + D + ',')
a('                 ' + D + '物料B编码' + D + ': ' + D + 'B1' + D + ', ' + D + '物料B名称' + D + ': ' + D + 'B1名' + D + '}]')
a('        current = []')
a('        result = import_alt_pairs_from_excel(data, current, overwrite=False)')
a('        result2 = import_alt_pairs_from_excel(data, result, overwrite=False)')
a('        assert len(result2) >= 1')
a('')
a('')
a('if __name__ == ' + D + '__main__' + D + ':')
a('    pytest.main([__file__, ' + D + '-v' + D + '])')
a('')

with open(out, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print('Done: ' + out)
