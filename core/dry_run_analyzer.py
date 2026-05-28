# -*- coding: utf-8 -*-
"""
DryRunAnalyzer — 独立 dry-run 模块（完全避开冷冻区）

不修改 analyzer.py / do_analysis_v2。
仅读取 Excel → 预处理 → 统计，不保存任何文件。
"""
import pandas as pd
from pathlib import Path
from datetime import datetime


class DryRunAnalyzer:
    """
    对输入 Excel 做轻量分析（不写入任何文件）。

    返回统计信息字典，供健康检查面板展示。
    """

    # 候选列名（与 analyzer.py 保持一致，但不依赖它）
    _DATE_COLS   = ["订单日期", "订单开始日期", "工单日期", "日期"]
    _MAT_COLS   = ["组件物料号", "物料编码", "物料号", "零件号", "组件号"]
    _REMARK_COLS = ["备注原因", "备注", "审核备注", "偏差备注"]
    _DEV_RATE_COL = "偏差率(%)"   # 主候选

    # ── 公共 API ─────────────────────────────────────────────────

    @staticmethod
    def analyze(
        input_excel_path: str,
        start_date=None,
        end_date=None,
        material_search=None,
    ) -> dict:
        """
        仅读取 Excel 并返回统计信息，不保存任何文件。
        完全不依赖 analyzer.py，避免触碰冷冻区。
        """
        input_path = Path(input_excel_path)
        if not input_path.exists():
            return {"error": f"文件不存在：{input_excel_path}"}

        # 1. 读取 Excel（只取 Data sheet）
        try:
            df = pd.read_excel(input_path, sheet_name="Data")
        except Exception as e:
            return {"error": f"读取 Excel 失败：{e}"}

        # 2. 列名标准化（dry-run 自己处理，不依赖 analyzer）
        df = DryRunAnalyzer._normalize_columns(df)

        total = len(df)

        # 3. 日期筛选
        date_col = DryRunAnalyzer._find_col(df, DryRunAnalyzer._DATE_COLS)
        if start_date and end_date and date_col:
            try:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
                mask = (df[date_col] >= pd.to_datetime(start_date)) & \
                       (df[date_col] <= pd.to_datetime(end_date))
                df = df[mask]
            except Exception:
                pass

        # 4. 物料搜索
        if material_search:
            search_lower = material_search.lower()
            mat_col = DryRunAnalyzer._find_col(df, DryRunAnalyzer._MAT_COLS)
            desc_col = next((c for c in ["物料描述", "组件物料描述", "材料描述"]
                                 if c in df.columns), None)
            mask = pd.Series(False, index=df.index)
            if mat_col:
                mask |= df[mat_col].astype(str).str.lower().str.contains(search_lower, na=False)
            if desc_col:
                mask |= df[desc_col].astype(str).str.lower().str.contains(search_lower, na=False)
            df = df[mask]

        # 5. 统计
        high_dev_count = 0
        dev_col = DryRunAnalyzer._find_col(df, [DryRunAnalyzer._DEV_RATE_COL, "偏差率%"])
        if dev_col:
            try:
                vals = pd.to_numeric(df[dev_col], errors="coerce").abs()
                high_dev_count = int((vals >= 10).sum())
            except Exception:
                pass

        need_note_count = 0
        remark_col = DryRunAnalyzer._find_col(df, DryRunAnalyzer._REMARK_COLS)
        if remark_col:
            need_note_count = int(
                df[remark_col].isna().sum()
                + (df[remark_col].astype(str).str.strip() == "").sum()
            )

        # 6. 模拟耗时（按行数估算）
        filtered_total = len(df)
        estimated_seconds = max(1, int(filtered_total / 5000))

        return {
            "total_rows":       total,
            "filtered_rows":    filtered_total,
            "high_dev_count":   high_dev_count,
            "need_note_count":  need_note_count,
            "estimated_time_sec": estimated_seconds,
            "preview": df.head(10).to_dict("records") if filtered_total > 0 else [],
        }

    # ── 内部工具方法 ─────────────────────────────────────────────

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        列名标准化：去除空格、换行、全角符号，便于后续匹配。
        """
        norm_map = {}
        for col in df.columns:
            key = str(col).strip().replace("\n", "").replace("\r", "")
            # 全角转半角
            key = key.replace("（", "(").replace("）", ")")
            norm_map[col] = key
        df = df.rename(columns=norm_map)
        return df

    @staticmethod
    def _find_col(df: pd.DataFrame, candidates: list) -> str or None:
        """
        从候选列名列表中找到第一个存在于 DataFrame 的列。
        """
        cols_set = set(df.columns)
        for c in candidates:
            if c in cols_set:
                return c
        return None
