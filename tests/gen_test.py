# -*- coding: utf-8 -*-
import os

Q = chr(34)  # ASCII double quote

lines = []
L = lines.append

L('# -*- coding: utf-8 -*-')
L('"""PySide6 迁移核心模块测试（无需 GUI 窗口）"""')
L('import sys, os')
L("sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))")
L('')
L('import pytest')
L('import pandas as pd')
L('import tempfile')
L('import json')
L('')
L('from PySide6.QtCore import Qt')
L('from PySide6.QtWidgets import QApplication')
L('from gui_pyside6.models.data_frame_model import DataFrameModel')
L('from core.rule_engine import RuleEngine')
L('from core.import_handlers import import_alt_pairs_from_excel')
L('')
L('')
L('# ---------- Qt Application Fixture ----------')
L('@pytest.fixture(scope="session", autouse=True)')
L('def qapp():')
L('    app = QApplication.instance()')
L('    if app is None:')
L('        app = QApplication([])')
L('    return app')
L('')
L('')
L('# ---------- TestDataFrameModel ----------')
L('class TestDataFrameModel:')
L('    def test_row_count(self, qapp):')
L('        df = pd.DataFrame({Q+A+Q+Q+[:]+Q+Q+A+Q+Q+[:]+Q+Q+a+Q+Q+b+Q+Q+}])'.replace('+', "'").replace('[:]', '[1, 2]').replace('Q', Q))
# This is getting too convoluted. Let me just write the file directly with Write tool.
# Actually the Write tool was working fine earlier - the issue is the Bash tool's shell processing.
# Let me just use Write tool directly with the exact content needed.
