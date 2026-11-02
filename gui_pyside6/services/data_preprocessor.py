# -*- coding: utf-8 -*-
"""
数据预处理服务
负责：脏列清理、替代料规范化、DataID + 指纹计算、列重排
"""

import pandas as pd
import numpy as np
from PySide6.QtCore import QObject, Signal

from .utils import find_real_qty_col, find_remark_col, norm_note, safe_qty

# 配置：需要转换为数值类型的列（用于 convert_numeric_cols）
NUMERIC_COLUMN_DEFS = ['定额', '实际', '偏差数量', '偏差金额', '偏差金额(含税)',
                       '净偏差数量', '净偏差金额', '净偏差率(%)']

# 配置：需要清理的冗余列（用于 clean_columns）
REDUNDANT_COL_PAIRS = [
    ('替代料组', '_替代料组'),  # 删除替代料组，保留 _替代料组
    ('净偏差', '净偏差金额'),     # 删除净偏差，保留净偏差金额
    ('净偏差', '净偏差数量'),     # 删除净偏差，保留净偏差数量
    ('偏差率', '偏差率(%)'),      # 删除字符串格式的偏差率，保留偏差率(%)
]



class DataPreprocessor(QObject):
    """数据预处理服务，负责清洗、增强和重组数据"""

    log_signal = Signal(str, str)  # (msg, level)

    def __init__(self, parent=None):
        super().__init__(parent)

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def clean_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理重复列：保留第一个出现的，删除后续同名列"""
        # 1. 去掉冗余列：基于配置
        for remove, keep in REDUNDANT_COL_PAIRS:
            if remove in df.columns and keep in df.columns:
                df = df.drop(columns=[remove])
                self.log(f"已删除冗余列：{remove}（保留 {keep}）", "info")
        # 2. 强制去重（保留第一个）
        dup_cols = df.columns[df.columns.duplicated()].unique()
        if len(dup_cols) > 0:
            df = df.loc[:, ~df.columns.duplicated(keep='first')]
            self.log(f"已清理重复列: {list(dup_cols)}", "warning")
        return df

    def normalize_alt_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        if "是否替代料" in df.columns:
            def _norm_alt(v):
                if pd.isna(v):
                    return "否"
                s = str(v).strip().lower()
                if s in ("是", "true", "1", "yes", "y"):
                    return "是"
                if "替代" in s or "alt" in s:
                    return "是"
                return "否"
            df["是否替代料"] = df["是否替代料"].apply(_norm_alt)
        else:
            df['是否替代料'] = '否'
        return df

    def add_data_id_and_fingerprint(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            if '工厂' in df.columns:
                df['data_id'] = (df['工厂'].astype(str) + '|'
                                 + df['订单日期'].astype(str) + '|'
                                 + df['流程订单'].astype(str) + '|'
                                 + df['物料编码'].astype(str))
            else:
                df['data_id'] = (df['订单日期'].astype(str) + '|'
                                 + df['流程订单'].astype(str) + '|'
                                 + df['物料编码'].astype(str))
        except Exception as e:
            self.log(f"创建data_id失败: {e}", "error")
            import traceback
            traceback.print_exc()
            df['data_id'] = df.index.astype(str)

        try:
            amount_col = '偏差金额(含税)' if '偏差金额(含税)' in df.columns else '偏差金额'
            amount = pd.to_numeric(df[amount_col], errors='coerce').fillna(0.0) if amount_col in df.columns else pd.Series(0.0, index=df.index)
            rate = pd.to_numeric(df['偏差率(%)'], errors='coerce').fillna(0.0) if '偏差率(%)' in df.columns else pd.Series(0.0, index=df.index)
            df['fingerprint'] = amount.round(2).astype(str) + '|' + rate.round(1).astype(str)
        except Exception as e:
            self.log(f"计算指纹失败: {e}", "error")
            df['fingerprint'] = "0.00|0.0"
        return df

    def reorder_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            cols = list(df.columns)
            amt_col = None
            for col in ['偏差金额(含税)', '偏差金额']:
                if col in cols:
                    amt_col = col
                    break
            rate_col = None
            for col in ['偏差率(%)', '偏差率']:
                if col in cols:
                    rate_col = col
                    break
            if amt_col and rate_col:
                cols = [c for c in cols if c != rate_col]
                amt_idx = cols.index(amt_col)
                cols.insert(amt_idx + 1, rate_col)
            # 把「产量」「产量单位」移到「产品物料描述」后面
            if '产品物料描述' in cols:
                yi = cols.index('产品物料描述')
                for extra in ['产量', '产量单位']:
                    if extra in cols:
                        cols.remove(extra)
                        cols.insert(yi + 1, extra)
                        yi += 1
            df = df[cols]
            self.log("已调整列顺序：偏差率移到偏差金额后面，产量移到产品物料描述后面", "info")
        except Exception as e:
            self.log(f"列重排序失败: {e}", "error")
        return df

    def convert_numeric_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """确保关键数值列为数值类型"""
        # 偏差率列统一
        rate_col = None
        for c in ['偏差率(%)', '偏差率']:
            if c in df.columns:
                rate_col = c
                break
        if rate_col:
            if df[rate_col].dtype == object:
                df[rate_col] = df[rate_col].astype(str).str.replace('%', '', regex=False)
            df[rate_col] = pd.to_numeric(df[rate_col], errors='coerce').fillna(0.0)

        # 其他数值列
        for col in NUMERIC_COLUMN_DEFS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # 如果偏差率字符串列为空，从数值列自动生成
        if '偏差率(%)' in df.columns and '偏差率' in df.columns:
            if (df['偏差率'].isna().all() or (df['偏差率'].astype(str).str.strip() == '').all()):
                df['偏差率'] = df['偏差率(%)'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else '')

        return df


# 对外工具函数（供外部模块如 alert_dialog 使用）
# 这些函数从 utils 导入，保持数据预处理边界
def snapshot_qty_for(df: pd.DataFrame, data_id) -> float:
    """取某 data_id 当前实际数量（用于审核时建立变更检测基线）；找不到返回 None"""
    col = find_real_qty_col(df)
    if col is None or 'data_id' not in df.columns:
        return None
    try:
        sel = df.loc[df['data_id'] == data_id, col]
        if len(sel) == 0:
            return None
        v = sel.iloc[0]
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except Exception:
        return None


def snapshot_note_for(df: pd.DataFrame, data_id) -> str:
    """取某 data_id 当前备注原因（用于审核时建立变更检测基线）；找不到返回 ''"""
    col = find_remark_col(df)
    if col is None or 'data_id' not in df.columns:
        return ''
    try:
        sel = df.loc[df['data_id'] == data_id, col]
        if len(sel) == 0:
            return ''
        return norm_note(sel.iloc[0])
    except Exception:
        return ''


def build_data_id(row: dict, df: pd.DataFrame) -> str:
    """data_id 唯一构造（4段/3段自适应）"""
    import datetime

    def _seg(v) -> str:
        if isinstance(v, (pd.Timestamp,)):
            if v.hour == 0 and v.minute == 0 and v.second == 0 and v.microsecond == 0 and v.nanosecond == 0:
                return v.strftime("%Y-%m-%d")
            return str(v)
        if isinstance(v, datetime.datetime):
            if v.hour == 0 and v.minute == 0 and v.second == 0 and v.microsecond == 0:
                return v.strftime("%Y-%m-%d")
            return str(v)
        if isinstance(v, datetime.date):
            return v.strftime("%Y-%m-%d")
        return f"{v}"

    if '工厂' in df.columns:
        return (_seg(row.get('工厂', '')) + '|' + _seg(row.get('订单日期', '')) + '|'
                + _seg(row.get('流程订单', '')) + '|' + _seg(row.get('物料编码', '')))
    return (_seg(row.get('订单日期', '')) + '|' + _seg(row.get('流程订单', '')) + '|'
            + _seg(row.get('物料编码', '')))

