# -*- coding: utf-8 -*-
"""
读取状态服务
负责：已读状态恢复、已读已审记录变更检测、变动历史记录
"""

import pandas as pd
import numpy as np
import hashlib
from PySide6.QtCore import QObject, Signal

from core.read_status import (
    load_read_status,
    record_deviation_change,
    record_deviation_change_batch,
    save_snapshot_batch,
)
from .utils import find_real_qty_col, find_remark_col, find_yield_col, norm_note, safe_qty


class ReadStatusService(QObject):
    """读取状态和变更检测服务"""

    log_signal = Signal(str, str)  # (msg, level)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_audit_changes = []  # 审核后变更详情

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def _compute_fingerprint(self, df_row):
        """计算行指纹（只包含可能变动的关键列）"""
        # 提取关键数据
        parts = []
        for col in ['实际', '备注', '备注原因', '产量', 'yield']:
            if col in df_row.index:
                val = df_row[col]
                parts.append(str(safe_qty(val)))
        # 组合成指纹
        return hashlib.md5('|'.join(parts).encode()).hexdigest()[:16]

    def restore_read_status(self, df: pd.DataFrame) -> pd.DataFrame:
        """恢复已读状态 + 审核后变更检测（增量优化版）

        基线策略：
        - 历史记录有 snapshot_qty / snapshot_note / snapshot_yield → 与当前比对；
        - 历史记录无基线（旧记录/基线未初始化）→ 用当前值静默建立基线，不报警；
        - 实际数量 或 备注原因 或 产量 被改动 → 回退未读 + 行红标 + deviation_history 留痕 + 弹变动提醒。

        增量优化：
        - 先计算当前行指纹，只比对指纹变化的行，大幅减少计算量
        """
        try:
            data_ids = df['data_id'].tolist()
            status_map = load_read_status(data_ids)
        except Exception as e:
            self.log(f"加载历史状态失败: {e}", "error")
            import traceback
            traceback.print_exc()
            status_map = {}

        real_col = self._find_real_qty_col(df)
        remark_col = self._find_remark_col(df)
        yield_col = self._find_yield_col(df)
        self.last_audit_changes = []

        if not status_map:
            df['_read'] = 0
            df['_read_source'] = ''
            df['_post_audit_changed'] = 0
            return df

        # 历史状态对齐
        status_df = pd.DataFrame.from_dict(
            status_map, orient='index',
            columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note', '_hist_yield', '_hist_source']
        )
        df = df.join(status_df, on='data_id')

        has_status = df['_hist_read'].notna()
        missing_baseline = has_status & (df['_hist_snap'].isna() | df['_hist_note'].isna() | df['_hist_yield'].isna())
        has_baseline = has_status & ~missing_baseline

        # 当前值
        if real_col:
            cur_qty = pd.to_numeric(df[real_col], errors='coerce')
        else:
            cur_qty = pd.Series([np.nan] * len(df), index=df.index)
        if remark_col:
            cur_note = df[remark_col].apply(self._norm_note)
        else:
            cur_note = pd.Series([''] * len(df), index=df.index)
        if yield_col:
            cur_yield = pd.to_numeric(df[yield_col], errors='coerce')
        else:
            cur_yield = pd.Series([np.nan] * len(df), index=df.index)

        # 旧记录无基线 → 静默建立基线
        if missing_baseline.any():
            init_records = list(zip(
                df.loc[missing_baseline, 'data_id'],
                cur_qty[missing_baseline],
                cur_note[missing_baseline],
                cur_yield[missing_baseline],
            ))
            save_snapshot_batch(init_records)

        # 增量优化：计算行指纹
        df['_cur_fp'] = df.apply(self._compute_fingerprint, axis=1)

        # 只比对指纹或没有指纹的历史记录
        has_fp = df['_hist_fp'].notna() & (df['_hist_fp'] != '')
        # 指纹变化或无指纹需要详细比对
        need_detailed = has_fp & (df['_hist_fp'] != df['_cur_fp']) | ~has_fp

        # 向量化比对（仅对需要详细比对的行）
        # 历史值（可能不在需要比对的索引上，需要过滤）
        hist_snap = pd.to_numeric(df['_hist_snap'], errors='coerce')
        hist_note = df['_hist_note'].apply(self._norm_note)
        hist_yield = pd.to_numeric(df['_hist_yield'], errors='coerce')
        # 对需要详细比对的行进行比对
        detailed_indices = df.index[need_detailed]
        qty_changed = pd.Series(False, index=df.index)
        note_changed = pd.Series(False, index=df.index)
        yield_changed = pd.Series(False, index=df.index)
        
        if len(detailed_indices) > 0:
            # 子集的向量化比对
            sub_df = df.loc[detailed_indices]
            sub_snap = pd.to_numeric(sub_df['_hist_snap'], errors='coerce')
            sub_note = sub_df['_hist_note'].apply(self._norm_note)
            sub_yield = pd.to_numeric(sub_df['_hist_yield'], errors='coerce')
            sub_cur_qty = pd.to_numeric(sub_df[real_col], errors='coerce') if real_col else pd.Series([np.nan]*len(sub_df), index=sub_df.index)
            sub_cur_note = sub_df[remark_col].apply(self._norm_note) if remark_col else pd.Series(['']*len(sub_df), index=sub_df.index)
            sub_cur_yield = pd.to_numeric(sub_df[yield_col], errors='coerce') if yield_col else pd.Series([np.nan]*len(sub_df), index=sub_df.index)
            
            # 详细比对子集
            has_full_sub = sub_snap.notna() & sub_note.notna() & sub_yield.notna()
            qty_changed.loc[detailed_indices] = has_full_sub & sub_cur_qty.notna() & (abs(sub_snap - sub_cur_qty) >= 1e-6)
            note_changed.loc[detailed_indices] = has_full_sub & (sub_note != sub_cur_note)
            yield_changed.loc[detailed_indices] = has_full_sub & sub_cur_yield.notna() & (abs(sub_yield - sub_cur_yield) >= 1e-6)

        # 合并所有检测结果
        changed = qty_changed | note_changed | yield_changed


        # 组装状态
        hist_read_int = df['_hist_read'].fillna(0).astype(int)
        df['_read'] = np.where(changed, 0, np.where(has_status, hist_read_int, 0))
        df['_post_audit_changed'] = changed.astype(int)

        # 已读来源
        src = df['_hist_source'].fillna('').astype(str) if '_hist_source' in df.columns else pd.Series('', index=df.index)
        still_read = df['_read'] == 1
        df['_read_source'] = np.where(
            still_read & (src == ''), 'manual',
            np.where(still_read, src, '')
        )

        # 批量记录变动历史
        if changed.any():
            changes_records = []
            for idx in df.index[qty_changed]:
                changes_records.append((
                    df.at[idx, 'data_id'], '实际数量',
                    df.at[idx, '_hist_snap'], cur_qty.at[idx]
                ))
                self.last_audit_changes.append({
                    'data_id': df.at[idx, 'data_id'], 'field': '实际数量',
                    'workshop': df.at[idx, '车间'] if '车间' in df.columns else None,
                    'material_name': df.at[idx, '物料名称'] if '物料名称' in df.columns else (
                        df.at[idx, '物料描述'] if '物料描述' in df.columns else ''),
                    'old_value': float(df.at[idx, '_hist_snap']) if pd.notna(df.at[idx, '_hist_snap']) else None,
                    'new_value': cur_qty.at[idx],
                })
            for idx in df.index[note_changed]:
                changes_records.append((
                    df.at[idx, 'data_id'], '备注原因',
                    df.at[idx, '_hist_note'], cur_note.at[idx]
                ))
                self.last_audit_changes.append({
                    'data_id': df.at[idx, 'data_id'], 'field': '备注原因',
                    'workshop': df.at[idx, '车间'] if '车间' in df.columns else None,
                    'material_name': df.at[idx, '物料名称'] if '物料名称' in df.columns else (
                        df.at[idx, '物料描述'] if '物料描述' in df.columns else ''),
                    'old_value': self._norm_note(df.at[idx, '_hist_note']),
                    'new_value': cur_note.at[idx],
                })
            for idx in df.index[yield_changed]:
                changes_records.append((
                    df.at[idx, 'data_id'], '产量',
                    df.at[idx, '_hist_yield'], cur_yield.at[idx]
                ))
                self.last_audit_changes.append({
                    'data_id': df.at[idx, 'data_id'], 'field': '产量',
                    'workshop': df.at[idx, '车间'] if '车间' in df.columns else None,
                    'material_name': df.at[idx, '物料名称'] if '物料名称' in df.columns else (
                        df.at[idx, '物料描述'] if '物料描述' in df.columns else ''),
                    'old_value': float(df.at[idx, '_hist_yield']) if pd.notna(df.at[idx, '_hist_yield']) else None,
                    'new_value': cur_yield.at[idx],
                })
            record_deviation_change_batch(changes_records)
            changed_count = int(changed.sum())
            self.log(f"⚠️ 发现 {changed_count} 条已审核记录的实际数量/备注原因/产量被修改，已强制设为未读并留痕", "warning")
            self.log_signal.emit(f"变动提醒|{changed_count}", "alert")

        # 清理临时历史列
        df = df.drop(columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note', '_hist_yield', '_hist_source'], errors='ignore')
        return df

    def _find_real_qty_col(self, df):
        return find_real_qty_col(df)

    def _find_remark_col(self, df):
        return find_remark_col(df)

    def _find_yield_col(self, df):
        return find_yield_col(df)

    def _norm_note(self, v):
        return norm_note(v)

    def _safe_qty(self, v):
        return safe_qty(v)

    def get_audit_changes(self, df: pd.DataFrame) -> list:
        """变动提醒看板单一数据源：与主表 _post_audit_changed 列完全一致。"""
        if df is None or getattr(df, 'empty', True) or '_post_audit_changed' not in df.columns:
            return []
        mask = pd.to_numeric(df['_post_audit_changed'], errors='coerce').fillna(0).astype(int) == 1
        if '_read' in df.columns:
            mask = mask & (pd.to_numeric(df['_read'], errors='coerce').fillna(0).astype(int) == 0)
        if not mask.any():
            return []
        sub = df[mask].copy()
        sub['data_id'] = sub['data_id'].astype(str)
        data_ids = [str(d) for d in sub['data_id'].tolist()]
        real_col = self._find_real_qty_col(sub)
        remark_col = self._find_remark_col(sub)
        yield_col = self._find_yield_col(sub)

        cur_qty = pd.to_numeric(sub[real_col], errors='coerce') if real_col else pd.Series([np.nan] * len(sub), index=sub.index)
        cur_note = sub[remark_col].apply(self._norm_note) if remark_col else pd.Series([''] * len(sub), index=sub.index)
        cur_yield = pd.to_numeric(sub[yield_col], errors='coerce') if yield_col else pd.Series([np.nan] * len(sub), index=sub.index)

        # 拉基线快照
        try:
            status_map = load_read_status(data_ids)
        except Exception:
            status_map = {}
        if status_map:
            status_df = pd.DataFrame.from_dict(
                status_map, orient='index',
                columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note', '_hist_yield', '_hist_source'])
            _overlap = [c for c in status_df.columns if c in sub.columns]
            if _overlap:
                sub = sub.drop(columns=_overlap)
            sub = sub.join(status_df, on='data_id')
        if '_hist_snap' not in sub.columns:
            sub['_hist_snap'] = np.nan
        if '_hist_note' not in sub.columns:
            sub['_hist_note'] = np.nan
        if '_hist_yield' not in sub.columns:
            sub['_hist_yield'] = np.nan
        hist_yield = pd.to_numeric(sub['_hist_yield'], errors='coerce')
        hist_snap = pd.to_numeric(sub['_hist_snap'], errors='coerce')
        hist_note = sub['_hist_note'].apply(self._norm_note)

        changes = []
        for idx in sub.index:
            did = str(sub.at[idx, 'data_id'])
            hs_qty = hist_snap.at[idx]
            hs_note = hist_note.at[idx]
            cur_q = cur_qty.at[idx]
            cur_n = cur_note.at[idx]
            hs_yield = hist_yield.at[idx]
            cur_y = cur_yield.at[idx]

            qty_diff = (not pd.isna(hs_qty)) and (not pd.isna(cur_q)) and (abs(float(hs_qty) - float(cur_q)) >= 1e-6)
            note_diff = (hs_note not in ('', None)) and (cur_n != hs_note)
            yield_diff = (not pd.isna(hs_yield)) and (not pd.isna(cur_y)) and (abs(float(hs_yield) - float(cur_y)) >= 1e-6)

            if qty_diff:
                field = '实际数量'
                ov = float(hs_qty)
                nv = cur_q
            elif note_diff:
                field = '备注原因'
                ov = hs_note
                nv = cur_n
            elif yield_diff:
                field = '产量'
                ov = float(hs_yield)
                nv = cur_y
            else:
                field = '实际数量'
                ov = None
                nv = cur_q if not pd.isna(cur_q) else None

            changes.append({
                'data_id': did,
                'field': field,
                'workshop': sub.at[idx, '车间'] if '车间' in sub.columns else None,
                'material_name': sub.at[idx, '物料名称'] if '物料名称' in sub.columns else (
                    sub.at[idx, '物料描述'] if '物料描述' in sub.columns else ''),
                'old_value': ov,
                'new_value': nv,
            })
        return changes

    def detect_and_notify_changes(self, old_df: pd.DataFrame, new_df: pd.DataFrame):
        """同会话重新分析时，检测已审核记录的变动并通知（方案A）"""
        old_qty = {}
        old_note = {}
        try:
            real_col_old = self._find_real_qty_col(old_df)
            remark_col_old = self._find_remark_col(old_df)
            for _, row in old_df.iterrows():
                if self._is_record_audited(row):
                    did = row['data_id']
                    old_qty[did] = self._safe_qty(row.get(real_col_old))
                    old_note[did] = self._norm_note(row.get(remark_col_old)) if remark_col_old else ''
        except Exception as e:
            self.log(f"构建旧快照失败: {e}", "error")

        real_col_new = self._find_real_qty_col(new_df)
        remark_col_new = self._find_remark_col(new_df)
        new_wk = {}  # did -> 车间
        new_name = {}  # did -> 物料名称
        changes = []  # (did, old_val, new_val, field)
        self.last_audit_changes = []  # 重置
        try:
            for _, row in new_df.iterrows():
                if self._is_record_audited(row):
                    did = row['data_id']
                    new_wk[did] = row.get('车间')
                    new_name[did] = row.get('物料名称') or row.get('物料描述') or ''
                    if did in old_qty:
                        old_q = old_qty[did]
                        new_q = self._safe_qty(row.get(real_col_new))
                        if old_q is not None and new_q is not None and abs(old_q - new_q) >= 1e-6:
                            changes.append((did, old_q, new_q, '实际数量'))
                    if did in old_note:
                        new_n = self._norm_note(row.get(remark_col_new)) if remark_col_new else ''
                        if old_note[did] != new_n:
                            changes.append((did, old_note[did], new_n, '备注原因'))
        except Exception as e:
            self.log(f"检测变动失败: {e}", "error")

        if changes:
            try:
                for did, old_v, new_v, field in changes:
                    from core.read_status import record_deviation_change
                    record_deviation_change(did, field, old_v, new_v, "重新分析数据变动")
            except Exception as e:
                self.log(f"记录变动失败: {e}", "error")
            self.log(f"发现 {len(changes)} 条已审核记录的实际数量/备注原因发生变动，已强制设为'未读'", "warning")
            for did, old_v, new_v, field in changes:
                self.last_audit_changes.append({
                    'data_id': did, 'field': field,
                    'workshop': new_wk.get(did),
                    'material_name': new_name.get(did) or '',
                    'old_value': old_v, 'new_value': new_v})
            self.log_signal.emit(f"变动提醒|{len(changes)}", "alert")

    def _is_record_audited(self, row):
        try:
            if '审核状态' in row and row['审核状态'] == '已审核':
                return True
            if '备注来源' in row and row['备注来源'] not in ('', 'AI审核', None):
                return True
        except Exception:
            pass
        return False

    def mark_changes_as_read(self, changes: list, df: pd.DataFrame):
        """把本次弹窗里的变动记录一次性标记为已读，并用当前主表最新值重建 snapshot 基线。"""
        if not changes:
            return 0
        try:
            from core.read_status import mark_read_batch
            qty_col = self._find_real_qty_col(df)
            note_col = self._find_remark_col(df)
            yield_col = self._find_yield_col(df)
            dids = set()
            snapshot_map = {}
            for c in changes:
                did = str(c.get('data_id', ''))
                if not did or did in dids:
                    continue
                dids.add(did)
                rows = df[df['data_id'].astype(str) == did]
                if rows.empty:
                    snap_qty = None
                    snap_note = ''
                    snap_yield = None
                else:
                    row = rows.iloc[0]
                    snap_qty = row.get(qty_col) if qty_col else None
                    snap_note = self._norm_note(row.get(note_col)) if note_col else ''
                    snap_yield = row.get(yield_col) if yield_col else None
                snapshot_map[did] = (snap_qty, snap_note, snap_yield)
            mark_read_batch(list(dids), snapshot_map, read_source='manual')
            self.last_audit_changes = []
            return len(dids), dids
        except Exception as e:
            self.log(f"批量标记已读失败: {e}", "error")
            return 0, set()
