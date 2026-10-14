# -*- coding: utf-8 -*-
"""data_id 构造正版 build_data_id 的测试锚定（ARC-002 方案B）。

三层保护：
1. 合成等价：4段/3段/NaN/缺键/dict-like 的行为逐字符锁定。
2. 正版一致：单行 build_data_id 逐行 == DataService._add_data_id_and_fingerprint
   的向量化公式（保证单行版与 DataFrame 版同源，不再各写一套）。
3. 真实锚定：读真实 SAP 导出 + audit.db，验证 build_data_id 产出与存量键格式一致。
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gui_pyside6.services.data_service import build_data_id  # noqa: E402

REAL_EXPORT = r"E:/ZPP011导出文件原数据/ZPP011_20261001-20261014.xlsx"


def _vec_data_id(df: pd.DataFrame) -> pd.Series:
    """向量化正版公式（复刻 DataService._add_data_id_and_fingerprint:132-144，
    与 data_service.py 源码逐字一致，作为单行版的对照基准）。"""
    if '工厂' in df.columns:
        return (df['工厂'].astype(str) + '|'
                + df['订单日期'].astype(str) + '|'
                + df['流程订单'].astype(str) + '|'
                + df['物料编码'].astype(str))
    return (df['订单日期'].astype(str) + '|'
            + df['流程订单'].astype(str) + '|'
            + df['物料编码'].astype(str))


# ---------- 1. 合成行为 ----------

def test_four_segment_when_factory_present():
    df = pd.DataFrame([{'工厂': '1101', '订单日期': '20260101', '流程订单': 'OF001', '物料编码': 'M1'}])
    row = df.iloc[0]
    assert build_data_id(row, df) == "1101|20260101|OF001|M1"


def test_three_segment_when_no_factory():
    df = pd.DataFrame([{'订单日期': '20260101', '流程订单': 'OF001', '物料编码': 'M1'}])
    row = df.iloc[0]
    assert build_data_id(row, df) == "20260101|OF001|M1"


def test_missing_key_defaults_empty():
    df = pd.DataFrame([{'工厂': '1101', '流程订单': 'OF001', '物料编码': 'M1'}])  # 缺 订单日期
    row = df.iloc[0]
    assert build_data_id(row, df) == "1101||OF001|M1"


def test_nan_renders_as_nan_string_history_behavior():
    # 历史 f-string 行为：NaN 值经 f-string 变 "nan"，必须保持（否则与存量键错位）
    df = pd.DataFrame([{'工厂': np.nan, '订单日期': '20260101', '流程订单': 'OF001', '物料编码': 'M1'}])
    row = df.iloc[0]
    assert build_data_id(row, df) == "nan|20260101|OF001|M1"


def test_datetime_midnight_renders_date_only_like_astype_str():
    """关键修正锁定：datetime 列零点时刻按 astype(str) 语义只出日期，
    与 _add_data_id_and_fingerprint 向量化正版一致（原 f-string 会带 00:00:00，
    触发 fallback 时与 audit.db 存量键错位）。"""
    ts = pd.Timestamp('2026-10-03')
    df = pd.DataFrame([{'工厂': '1101', '订单日期': ts, '流程订单': 'OF001', '物料编码': 'M1'}])
    row = df.iloc[0]
    assert build_data_id(row, df) == "1101|2026-10-03|OF001|M1"
    # 与向量化正版（astype(str)）严格一致
    vec = (df['工厂'].astype(str) + '|' + df['订单日期'].astype(str) + '|'
           + df['流程订单'].astype(str) + '|' + df['物料编码'].astype(str)).iloc[0]
    assert build_data_id(row, df) == vec


def test_datetime_with_time_component_keeps_full():
    ts = pd.Timestamp('2026-10-03 14:30:00')
    df = pd.DataFrame([{'工厂': '1101', '订单日期': ts, '流程订单': 'OF001', '物料编码': 'M1'}])
    row = df.iloc[0]
    vec = (df['工厂'].astype(str) + '|' + df['订单日期'].astype(str) + '|'
           + df['流程订单'].astype(str) + '|' + df['物料编码'].astype(str)).iloc[0]
    assert build_data_id(row, df) == vec == "1101|2026-10-03 14:30:00|OF001|M1"


def test_dict_like_input():
    row = {'工厂': '1102', '订单日期': '20260102', '流程订单': 'OF002', '物料编码': 'M2'}
    df = pd.DataFrame(columns=['工厂', '订单日期', '流程订单', '物料编码'])
    assert build_data_id(row, df) == "1102|20260102|OF002|M2"


# ---------- 2. 正版一致（单行 == 向量化） ----------

@pytest.mark.parametrize("with_factory", [True, False])
def test_rowwise_matches_vectorized(with_factory):
    rng = np.random.RandomState(42)
    n = 50
    data = {
        '订单日期': [f"202601{d:02d}" for d in rng.randint(1, 28, n)],
        '流程订单': [f"OF{rng.randint(1000, 9999)}" for _ in range(n)],
        '物料编码': [f"M{rng.randint(1, 999)}" for _ in range(n)],
    }
    if with_factory:
        data['工厂'] = [f"11{rng.randint(1, 2):02d}" for _ in range(n)]
    df = pd.DataFrame(data)
    vec = _vec_data_id(df)
    for i in range(len(df)):
        assert build_data_id(df.iloc[i], df) == vec.iloc[i], f"row {i} 不一致"


# ---------- 3. 真实锚定 ----------

@pytest.mark.skipif(not os.path.isfile(REAL_EXPORT), reason=f"真实导出不存在: {REAL_EXPORT}")
def test_real_export_rowwise_matches_official_pipeline(tmp_path):
    """真实锚定（最强）：走正版管线全链路——原始导出经 do_analysis_v2
    （订单开始日期→订单日期 改名）再经 DataService.preprocess_audit_data
    （内部 _add_data_id_and_fingerprint 即 data_id 向量化正版），
    逐行验证 build_data_id == 管线产出的 data_id 列。"""
    from analysis.analyzer import do_analysis_v2
    from gui_pyside6.services.data_service import DataService

    dev = do_analysis_v2(
        input_file=REAL_EXPORT,
        output_dir=str(tmp_path),
        alt_pairs=[],
        return_dataframe=True,
    )
    processed = DataService().preprocess_audit_data(dev)
    assert 'data_id' in processed.columns, "正版管线应产出 data_id 列"
    assert '工厂' in processed.columns and '订单日期' in processed.columns
    mismatch = [
        i for i in range(len(processed))
        if build_data_id(processed.iloc[i], processed) != processed.iloc[i]['data_id']
    ]
    assert not mismatch, (
        f"真实数据 {len(mismatch)}/{len(processed)} 行 build_data_id 与正版管线 data_id 不一致，"
        f"前 3 行: {[(i, processed.iloc[i]['data_id']) for i in mismatch[:3]]}"
    )


def test_audit_db_keys_are_four_segment():
    """audit.db 存量 data_id 锚定：≥99% 须为 4 段格式（v42.93 起恢复工厂前缀）。
    存量含极少数历史遗留非 4 段值（2026-10-14 实测 3026 个 distinct 中仅 1 个 'X'），
    故用占比断言而非 100%——若占比跌破阈值，说明格式回归，测试失败报警。"""
    try:
        from core.read_status import DB_PATH
    except Exception as e:  # pragma: no cover
        pytest.skip(f"无法导入 DB_PATH: {e}")
    if not os.path.isfile(DB_PATH):
        pytest.skip(f"audit.db 不存在: {DB_PATH}")
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT DISTINCT data_id FROM deviation_history LIMIT 500"
        ).fetchall()
    except sqlite3.Error:
        pytest.skip("deviation_history 表不可读")
    finally:
        conn.close()
    if not rows:
        pytest.skip("deviation_history 无数据")
    bad = [d for (d,) in rows if str(d).count('|') != 3]
    ratio = 1 - len(bad) / len(rows)
    assert ratio >= 0.99, f"4 段格式占比 {ratio:.2%} 跌破 99%，疑似格式回归；非 4 段样本: {bad[:5]}"
