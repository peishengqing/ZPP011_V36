# -*- coding: utf-8 -*-
"""do_analysis_v2 输入契约测试（测试钉子，不改任何计算逻辑）。

目的
----
`analysis/analyzer.py` 是红区模块，重构前需要知道"坏输入到底会怎样"。
本文件只断言**既有可观测行为**，用来防止重构或后续改动悄悄改变失败语义；
不修正任何计算，也不替代黄金基线（见 tests/test_analyzer_golden.py）。

用例分两类
----------
1. 已确认且合理的行为 —— 正常断言，作为回归护栏；
2. 已确认但**不合理**的行为 —— `xfail(strict=True)` 钉住现状：等哪天修好了，
   严格 xfail 会变成失败，提醒把标记去掉。

已修复（v43.407，红区外科手术，黄金基线 51 点零差异）
----------------------------------------------------
* `input_df` 复用分支 + 缺列：原先 `_sheet` 未定义导致列名丢失，现预置默认值，
  报错信息恢复点名缺哪一列。
* 数量列混入文本：原先崩在 TRACE-1 的 `.sum()`（在强制数值转换之前），
  现先 to_numeric 再求和；脏文本按既有规则 coerce 为 0，不再中断分析。
* 日期过滤解析失败：原先 `except BaseException: pass` 静默跳过，现改为告知。

仍按现状钉住
------------
* 只有表头（0 行）的源文件：静默返回 0 行结果，不报错——是否应提示待定，
  本文件按现状钉住，避免"悄悄变成报错"或"悄悄变成有数据"。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

GOLDEN = os.path.join(ROOT, "tests", "fixtures", "golden", "_drink9_zpp011_wx.xlsx")
REQUIRED = ["订单开始日期", "数量-定额", "数量-实际"]

pytestmark = pytest.mark.skipif(
    not os.path.isfile(GOLDEN), reason="黄金样本缺失，跳过输入契约测试")


@pytest.fixture(scope="module")
def base_df():
    """从黄金样本取前 200 行：schema 真实，跑一次约 0.2s。"""
    import pandas as pd
    return pd.read_excel(GOLDEN, sheet_name="Data").iloc[:200].reset_index(drop=True)


def _write(df, tmp_path, name="case.xlsx"):
    import pandas as pd
    path = tmp_path / name
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Data", index=False)
    return str(path)


def _as_object(df, col, values):
    """整列替换为 object dtype：pandas 2.x 向 float64 列写字符串会抛 LossySetitem。"""
    import pandas as pd
    out = df.copy()
    out[col] = pd.Series(values, index=out.index, dtype=object)
    return out


def _run(path, **kwargs):
    from analysis.analyzer import do_analysis_v2
    return do_analysis_v2(
        input_file=path, output_dir=None, alt_pairs=[],
        return_dataframe=True, **kwargs)


# ------------------------------------------------- 1. 文件级拦截（既有且合理）

def test_nonexistent_file_raises_filenotfound(tmp_path):
    """路径不存在 → FileNotFoundError，且错误信息含路径。"""
    missing = str(tmp_path / "no_such_file.xlsx")
    with pytest.raises(FileNotFoundError) as ei:
        _run(missing)
    assert "文件不存在" in str(ei.value)
    assert "no_such_file.xlsx" in str(ei.value)


def test_excel_lock_file_rejected(tmp_path):
    """~$ 开头的 Excel 锁文件 → PermissionError，不误当数据源解析。"""
    lock = tmp_path / "~$draft.xlsx"
    lock.write_bytes(b"")
    with pytest.raises(PermissionError) as ei:
        _run(str(lock))
    assert "临时锁文件" in str(ei.value)


def test_missing_required_column_is_rejected(base_df, tmp_path):
    """缺任一必需列 → 报错并点名缺哪一列，同时进度回调收到错误步。"""
    events = []
    path = _write(base_df.drop(columns=["订单开始日期"]), tmp_path)
    with pytest.raises(Exception) as ei:
        _run(path, progress_callback=lambda i, n, p: events.append((i, n, p)))

    msg = str(ei.value)
    assert "缺少原始 SAP 数据所需列" in msg
    assert "订单开始日期" in msg
    # 注意：内部 raise ValueError 会被外层 except Exception 包成通用 Exception，
    # 调用方拿不到具体类型（已记录为可诊断性缺口，不在本文件修）。
    assert any("错误" in n for _i, n, _p in events), f"未收到错误进度事件：{events}"


def test_input_df_missing_column_names_the_column(base_df):
    """复用已读 DataFrame 且缺列时，报错信息仍应点名缺哪一列。"""
    with pytest.raises(Exception) as ei:
        _run(GOLDEN, input_df=base_df.drop(columns=["数量-定额"]))
    assert "数量-定额" in str(ei.value)


# ------------------------------------------------- 2. 数据级容错

def test_headers_only_returns_empty_frame(base_df, tmp_path):
    """只有表头（0 行）→ 现状：不报错，返回 0 行结果（按现状钉住）。"""
    out = _run(_write(base_df.iloc[0:0], tmp_path))
    assert len(out) == 0
    assert "偏差率(%)" in out.columns


def test_unparsable_dates_do_not_abort(base_df, tmp_path):
    """订单开始日期无法解析 → 不中断，行数保持。"""
    df = _as_object(base_df, "订单开始日期", ["N/A"] * len(base_df))
    out = _run(_write(df, tmp_path))
    assert len(out) == len(base_df)


def test_zero_quota_produces_no_inf(base_df, tmp_path):
    """定额为 0 → 偏差率无 inf/无崩溃（除零已钳位）。"""
    import pandas as pd
    df = base_df.copy()
    df["数量-定额"] = 0
    out = _run(_write(df, tmp_path))
    rates = pd.to_numeric(out["偏差率(%)"], errors="coerce")
    assert len(out) == len(base_df)
    assert not (rates.abs() == float("inf")).any()


def test_thousand_separator_text_numbers_do_not_change_quantities(base_df, tmp_path):
    """定额写成 '1,234.56' 文本 → 不崩溃；能解析时应与数值口径一致。"""
    import pandas as pd
    df = base_df.copy()
    df["数量-定额"] = df["数量-定额"].map(
        lambda v: f"{v:,.2f}" if pd.notna(v) else v)

    baseline = _run(_write(base_df, tmp_path, "numeric.xlsx"))
    texty = _run(_write(df, tmp_path, "text.xlsx"))

    assert len(texty) == len(base_df)
    base_qty = pd.to_numeric(baseline["偏差数量"], errors="coerce").sum()
    text_qty = pd.to_numeric(texty["偏差数量"], errors="coerce").sum()
    assert text_qty == pytest.approx(base_qty, rel=1e-9, abs=1e-6), (
        f"千分位文本未被解析：数值口径 {base_qty} ≠ 文本口径 {text_qty}")


def test_invalid_date_filter_warns_instead_of_silently_ignoring(base_df, tmp_path):
    """日期过滤条件解析失败 → 不中断分析，但要明确告知过滤已被跳过。"""
    events = []
    out = _run(_write(base_df, tmp_path, "date.xlsx"), start_date="不是日期",
               progress_callback=lambda i, n, p: events.append((i, n, p)))
    assert len(out) == len(base_df), "过滤解析失败时应保持全量数据"
    assert any("无法解析" in n for _i, n, _p in events), f"未收到过滤告警：{events}"


def test_valid_date_filter_still_applies(base_df, tmp_path):
    """合法日期区间 → 仍按区间过滤（date_min 改为复用已解析值后行为不变）。"""
    import pandas as pd
    df = base_df.copy()
    df["订单开始日期"] = pd.to_datetime(df["订单开始日期"], errors="coerce")
    mid = df["订单开始日期"].sort_values().iloc[len(df) // 2]
    expected = int((df["订单开始日期"] >= mid).sum())

    events = []
    out = _run(_write(df, tmp_path, "valid_date.xlsx"),
               start_date=mid.strftime("%Y-%m-%d"),
               progress_callback=lambda i, n, p: events.append((i, n, p)))

    assert len(out) == expected, f"过滤后应为 {expected} 行，实际 {len(out)}"
    assert any("已按开始日期" in n for _i, n, _p in events), f"未收到过滤事件：{events}"


def test_duplicate_rows_are_not_silently_dropped(base_df, tmp_path):
    """重复行照原样参与计算，不做静默去重（源表即真相）。"""
    import pandas as pd
    dup = pd.concat([base_df, base_df.iloc[:5]], ignore_index=True)
    out = _run(_write(dup, tmp_path))
    assert len(out) == len(dup)


def test_non_numeric_text_is_coerced_without_aborting(base_df, tmp_path):
    """数量列混入 'abc' → 按既有规则 coerce 为 0，分析继续，不抛 numpy TypeError。"""
    values = ["abc"] * 5 + [None] * 3 + list(base_df["数量-实际"].iloc[8:])
    out = _run(_write(_as_object(base_df, "数量-实际", values), tmp_path))
    assert len(out) == len(base_df)
    assert "偏差率(%)" in out.columns
