# -*- coding: utf-8 -*-
"""
单元测试：domain.alt_material.alt_manager

alt_manager 函数使用内部 _get_config_path()，无路径参数。
使用 unittest.mock.patch 注入临时路径。
"""

import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.alt_material.alt_manager import (
    load_alt_pairs, save_alt_pairs,
    build_code_name_map, get_display_name,
    _get_config_path,
)


def test_build_code_name_map():
    """纯函数，无 IO，直接测试"""
    import pandas as pd
    df = pd.DataFrame([
        {'组件物料号': 'MAT001', '组件物料描述': 'Description A'},
        {'组件物料号': 'MAT002', '组件物料描述': 'Description B'},
        {'组件物料号': 'MAT003', '组件物料描述': 'Description C'},
    ])
    result = build_code_name_map(df)
    assert result == {
        'MAT001': 'Description A',
        'MAT002': 'Description B',
        'MAT003': 'Description C',
    }
    # None / empty DataFrame
    assert build_code_name_map(None) == {}
    assert build_code_name_map(pd.DataFrame()) == {}
    print('[OK] test_build_code_name_map')


def test_get_display_name():
    """纯函数，无 IO"""
    assert get_display_name('MAT001', 'Description A') == 'MAT001（Description A）'
    assert get_display_name('', 'Description A') == 'Description A'
    assert get_display_name('MAT001', '') == 'MAT001'
    assert get_display_name('', '') == '未知'
    assert get_display_name(None, None) == '未知'
    assert get_display_name('MAT001', 'MAT001') == 'MAT001'  # same code/name
    print('[OK] test_get_display_name')


def test_save_and_load():
    """patch _get_config_path 到临时目录后测试读写"""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, 'alt_pairs.json')

        # Patch _get_config_path and _get_config_dir to use temp path
        with patch('domain.alt_material.alt_manager._get_config_path', return_value=tmp_path):
            with patch('domain.alt_material.alt_manager._get_config_dir', return_value=tmpdir):
                # Test: load empty (no file yet) -> returns default
                pairs = load_alt_pairs()
                assert isinstance(pairs, list), 'load should return list'

                # Test: save and reload
                test_pairs = [
                    {'original': 'MAT001', 'alternative': 'MAT002', 'remark': '替代'},
                    {'original': 'MAT003', 'alternative': 'MAT004', 'remark': ''},
                ]
                save_alt_pairs(test_pairs)

                # Verify file written
                assert os.path.exists(tmp_path), f'File not created at {tmp_path}'

                # Reload
                loaded = load_alt_pairs()
                assert len(loaded) == 2, f'Expected 2, got {len(loaded)}'
                assert loaded[0]['original'] == 'MAT001'
                assert loaded[0]['alternative'] == 'MAT002'
                assert loaded[0]['remark'] == '替代'
                print('[OK] test_save_and_load')


if __name__ == '__main__':
    test_build_code_name_map()
    test_get_display_name()
    test_save_and_load()
    print('\n[ALL PASS] alt_manager unit tests passed!')
