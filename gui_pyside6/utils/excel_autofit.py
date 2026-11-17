# -*- coding: utf-8 -*-
"""GUI 侧 Excel 导出的列宽自适应工具（v43.391）。

背景：GUI 各处导出用的是裸 ``df.to_excel(path, index=False)``，pandas/openpyxl
默认列宽很窄，长中文文本（物料名称/备注/偏差原因等）在 Excel 里挤成一条。
本模块提供 ``to_excel_autofit``：写完表后按「表头 + 采样行」估算每列显示宽度，
再写回 ``ws.column_dimensions[letter].width``。

宽度口径：
- 字符显示宽度：ASCII/窄字符按 1，全角/宽字符（中日韩、全角标点）按 2；
- 单元格内含换行时按最长一行计；
- 每列宽度 = max(表头宽, 采样行最大内容宽) + 2 余量；
- 夹在 [min_width, max_width]（默认 8~60），防止超长文本把列撑爆。

只服务 GUI 侧单表导出；完整分析报告（12 sheet）的列宽由
``analysis/excel_builder/post_process._apply_layout`` 负责，互不影响。
"""

import unicodedata

import pandas as pd
from openpyxl.utils import get_column_letter

__all__ = ["to_excel_autofit", "display_width"]


def display_width(text) -> int:
    """字符串的 Excel 显示宽度：全角/宽字符按 2，其余按 1；多行取最长行。"""
    if text is None:
        return 0
    s = str(text)
    best = 0
    for line in s.split("\n"):
        w = 0
        for ch in line:
            w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if w > best:
            best = w
    return best


def to_excel_autofit(df, path, *, index=False, sheet_name="Sheet1",
                     min_width=8.0, max_width=60.0, sample_rows=500):
    """把 df 写成 xlsx 并按内容自适应列宽。

    与 ``df.to_excel(path, index=index)`` 等价（engine 固定 openpyxl），
    只是写完后多一步列宽自适应。返回写入路径。
    """
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=index)
        ws = writer.sheets.get(sheet_name)
        if ws is None or df is None:
            return path

        # 表头宽（index=True 时第 1 列是索引列）
        headers = []
        if index:
            headers.append("" if df.index.name is None else str(df.index.name))
        headers.extend(str(c) for c in df.columns)
        widths = [display_width(h) + 2 for h in headers]

        # 采样行内容宽（只看前 sample_rows 行，口径与主链路 _apply_layout 一致）
        sample = df.head(sample_rows)

        def _cell_width(values):
            w = 0
            for v in values:
                if v is None or v is pd.NA or v is pd.NaT:
                    continue
                if isinstance(v, float) and v != v:  # NaN
                    continue
                w = max(w, display_width(v))
            return w

        if index and widths:
            # 索引列也是真实内容列，同样参与估宽
            widths[0] = max(widths[0], _cell_width(sample.index) + 2)
        for j, col in enumerate(df.columns):
            w = _cell_width(sample[col])
            pos = j + (1 if index else 0)
            if pos < len(widths):
                widths[pos] = max(widths[pos], w + 2)

        for i, w in enumerate(widths[: ws.max_column], start=1):
            ws.column_dimensions[get_column_letter(i)].width = max(
                min_width, min(max_width, float(w)))
    return path
