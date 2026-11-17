# -*- coding: utf-8 -*-
"""v43.391：GUI 导出 Excel 列宽自适应工具（excel_autofit）单测。"""
import os
import sys

import pandas as pd
import pytest
from openpyxl import load_workbook

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from gui_pyside6.utils.excel_autofit import to_excel_autofit, display_width  # noqa: E402


def _widths(path, sheet=0):
    wb = load_workbook(path)
    ws = wb.worksheets[sheet]
    out = {}
    for i in range(1, ws.max_column + 1):
        from openpyxl.utils import get_column_letter
        letter = get_column_letter(i)
        dim = ws.column_dimensions.get(letter)
        out[letter] = None if dim is None else dim.width
    return out


def test_display_width_cjk_multiline_none():
    assert display_width('abc') == 3
    assert display_width('中文') == 4            # 全角按 2
    assert display_width('a\nbbbb') == 4         # 多行取最长行
    assert display_width('') == 0
    assert display_width(None) == 0


def test_autofit_basic_cap_and_min(tmp_path):
    df = pd.DataFrame({
        '数量': [1, 2, 3],
        '长文本列': ['云南达利食品有限公司生产偏差分析报表内容很长很长' * 4] * 3,
        '普通列': ['ab', 'c', 'def'],
    })
    p = str(tmp_path / 'out.xlsx')
    to_excel_autofit(df, p)
    w = _widths(p)
    assert w['A'] == 8.0                          # 窄列被下限托底
    assert w['B'] == 60.0                         # 超长文本被上限夹住
    assert 8.0 <= w['C'] <= 60.0 and w['C'] > len('普通列') + 2 - 1
    # 数据内容不受影响
    back = pd.read_excel(p)
    assert list(back.columns) == ['数量', '长文本列', '普通列']
    assert len(back) == 3


def test_autofit_empty_df_header_only(tmp_path):
    df = pd.DataFrame(columns=['物料编码', '物料名称', '备注'])
    p = str(tmp_path / 'empty.xlsx')
    to_excel_autofit(df, p)
    w = _widths(p)
    assert len(w) == 3
    assert all(8.0 <= v <= 60.0 for v in w.values())
    assert w['A'] >= len('物料编码') * 2 + 2 - 1   # 中文表头按全角估宽


def test_autofit_index_true_covers_index_col(tmp_path):
    df = pd.DataFrame({'值': [10, 20]},
                      index=pd.Index(['云南达利-食品厂', '云南达利-饮料厂'], name='工厂'))
    p = str(tmp_path / 'idx.xlsx')
    to_excel_autofit(df, p, index=True)
    w = _widths(p)
    assert len(w) == 2
    assert w['A'] >= len('云南达利-食品厂') * 2    # 索引列也自适应


def test_autofit_nan_and_custom_sheet(tmp_path):
    df = pd.DataFrame({'A': [None, '只有一个比较长的内容值', None],
                       'B': [1.5, float('nan'), 2.5]})
    p = str(tmp_path / 's.xlsx')
    to_excel_autofit(df, p, sheet_name='我的表')
    wb = load_workbook(p)
    assert wb.sheetnames == ['我的表']
    w = _widths(p)
    assert w['A'] >= len('只有一个比较长的内容值') * 2
    assert 8.0 <= w['B'] <= 60.0


def test_autofit_multiline_cell_uses_longest_line(tmp_path):
    df = pd.DataFrame({'备注': ['第一行\n这一行明显更长一些', 'x']})
    p = str(tmp_path / 'ml.xlsx')
    to_excel_autofit(df, p)
    w = _widths(p)
    assert w['A'] >= len('这一行明显更长一些') * 2  # 按最长行而不是全串


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
