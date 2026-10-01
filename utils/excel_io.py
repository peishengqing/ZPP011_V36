# -*- coding: utf-8 -*-
"""Excel 读取加速：优先 calamine 引擎，不可用/失败时自动退回 openpyxl。

背景：pandas 默认 openpyxl 引擎逐格解析 xlsx，大文件（5 万行）实测 6s+，
是「选文件 → 分析」链路的主要耗时。calamine（python-calamine，Rust 实现）
同文件实测 1.3s（约 4.8x，文件越大优势越明显，且两引擎读出的值一致）。

- 开发机已装 python-calamine 时自动启用；
- 未安装（含打包 exe 未带入时）静默退回 openpyxl，行为与旧版完全一致；
- calamine 读取个别文件失败时同样退回 openpyxl，绝不因引擎问题阻断分析。
"""
import pandas as pd

try:
    import python_calamine  # noqa: F401
    HAS_CALAMINE = True
except ImportError:
    HAS_CALAMINE = False


def available_engine() -> str:
    """当前实际生效的读表引擎名（供 UI/日志显示）。"""
    return "calamine" if HAS_CALAMINE else "openpyxl"


def open_excel_book(path):
    """打开 Excel 工作簿（惰性，不解析数据）：优先 calamine。

    返回 pd.ExcelFile；调用方用 book.parse(sheet) / book.sheet_names，
    比多次 pd.read_excel(path) 少重复解析整个文件。
    """
    if HAS_CALAMINE:
        try:
            return pd.ExcelFile(path, engine="calamine")
        except Exception:
            # 个别文件 calamine 解析失败 → 退回 openpyxl（与旧版行为一致）
            pass
    return pd.ExcelFile(path)


def read_sheet(path, sheet_name=0):
    """读单张表：calamine 优先，整体兜底 openpyxl。"""
    if HAS_CALAMINE:
        try:
            return pd.read_excel(path, sheet_name=sheet_name, engine="calamine")
        except Exception:
            pass
    return pd.read_excel(path, sheet_name=sheet_name)
