# -*- coding: utf-8 -*-
"""
审核结果服务
负责：从数据库恢复审核结果（审核结果、备注来源、归因、建议动作、候选建议），支持向量化和备选逻辑
"""

import pandas as pd
import numpy as np
from PySide6.QtCore import QObject, Signal

from core.read_status import load_audit_results
from core.audit_evidence import load_suggestions_batch


class AuditResultService(QObject):
    """审核结果恢复服务"""

    log_signal = Signal(str, str)  # (msg, level)

    def __init__(self, parent=None):
        super().__init__(parent)

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def restore_audit_results(self, df: pd.DataFrame) -> pd.DataFrame:
        """从 DB 恢复审核结果（审核结果、备注来源），使用向量化赋值替代逐行 iloc。

        目标：
        - 恢复 '审核结果' 和 '备注来源' 两列
        - 使用 merge 向量化操作，性能优化（2026-07-29）：1 次 merge + 2 次 fillna → 0.5-1s
        - AI建议功能已停用（2026-10-01）：不再恢复该列；如旧数据带此列，强制清空
        """
        try:
            data_ids = df['data_id'].tolist()
            audit_map = load_audit_results(data_ids)
        except Exception as e:
            self.log(f"加载审核结果失败: {e}", "error")
            data_ids = df['data_id'].tolist() if 'data_id' in df.columns else []
            audit_map = {}

        # --- 物化 AI 审核 3 列：归因 / 建议动作 / 候选建议（独立于 audit_map） ---
        try:
            sugg_map = load_suggestions_batch(data_ids)
            if sugg_map:
                for col_name in ('归因', '建议动作', '候选建议'):
                    if col_name in df.columns:
                        df.drop(columns=[col_name], inplace=True)
                    df[col_name] = ''
                    mapped = df['data_id'].map(
                        lambda did, c=col_name: sugg_map.get(str(did), {}).get(c, ''))
                    df[col_name] = mapped
                self.log(f"物化了 {len(sugg_map)} 条 AI 审核建议（归因/建议动作/候选建议）", "info")
            else:
                for col_name in ('归因', '建议动作', '候选建议'):
                    if col_name not in df.columns:
                        df[col_name] = ''
        except Exception as e:
            self.log(f"加载 AI 审核建议列失败: {e}", "warning")

        if not audit_map:
            # 无 DB 审核记录时也要保证「审核结果 / 备注来源」两列存在（与归因等一致，
            # 否则主表看不到这两列、却看得到归因——列缺失而非列空）
            for col in ('审核结果', '备注来源'):
                if col not in df.columns:
                    df[col] = ''
            return df

        # AI建议功能已停用：强制清空
        if 'AI建议' in df.columns:
            df['AI建议'] = ''

        # 向量化恢复：先转 DataFrame，merge 到 df
        try:
            audit_df = pd.DataFrame.from_dict(audit_map, orient='index')
            audit_df.index.name = 'data_id'
            audit_df = audit_df.add_suffix('__db')
            df = df.merge(audit_df, how='left', left_on='data_id', right_index=True)
        except Exception as e:
            self.log(f"向量化恢复审核结果失败（merge），回退旧逻辑: {e}", "warning")
            audit_df = None

        restored = 0
        if audit_df is not None:
            for col, key in [('审核结果', 'audit_result'), ('备注来源', 'note_source')]:
                db_col = f'{key}__db'
                if db_col not in df.columns:
                    if col not in df.columns:
                        df[col] = ''
                    continue
                if col not in df.columns:
                    df[col] = ''

                cur = df[col]
                if cur.dtype != object:
                    cur_str = cur.astype('object').where(cur.notna(), '').astype(str).str.strip()
                else:
                    cur_str = cur.where(cur.notna(), '').astype(str).str.strip()
                is_empty = df[col].isna() | cur_str.isin(['', 'nan', 'None'])

                if is_empty.any():
                    db_vals = df[db_col].fillna('')
                    df.loc[is_empty, col] = db_vals[is_empty]
                    if key == 'audit_result':
                        restored += int((is_empty & (db_vals != '')).sum())

                df.drop(columns=[db_col], inplace=True)
        else:
            # 兜底：旧 map(lambda) 逻辑（仅在 merge 异常时走）
            for col, key in [('审核结果', 'audit_result'), ('备注来源', 'note_source')]:
                if col not in df.columns:
                    df[col] = ''
                mapped = df['data_id'].map(lambda did: audit_map.get(did, {}).get(key, ''))
                current = df[col].astype(str).replace('nan', '').replace('None', '')
                is_empty = df[col].isna() | (current.str.strip() == '')
                if is_empty.any():
                    df.loc[is_empty, col] = mapped[is_empty]
                    if key == 'audit_result':
                        restored += int((is_empty & (mapped != '')).sum())

        if restored > 0:
            self.log(f"从数据库恢复了 {restored} 条审核结果", "info")

        return df
