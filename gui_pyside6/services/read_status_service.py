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
    backfill_net_baseline,
)
from core.threshold_config import substitute_mask  # v44.06：替代料行判定与看板/KPI 同源
from .utils import find_real_qty_col, find_remark_col, find_yield_col, norm_note, safe_qty

# 净偏差数量基线列名（v43.380 变动提醒展示修改前/后净偏差数量）
NET_QTY_COL = '净偏差数量'


def _net_series(df: pd.DataFrame) -> pd.Series:
    """取净偏差数量数值列；缺列/非法值 → NaN，保持与 df 对齐的索引。"""
    if NET_QTY_COL in df.columns:
        return pd.to_numeric(df[NET_QTY_COL], errors='coerce')
    return pd.Series([np.nan] * len(df), index=df.index)


def _net_lookup(df: pd.DataFrame) -> dict:
    """{data_id(str): float|None} 净偏差数量查找表（向量化构建，避免逐行 df.loc）。"""
    if df is None or NET_QTY_COL not in df.columns or 'data_id' not in df.columns:
        return {}
    s = pd.to_numeric(df[NET_QTY_COL], errors='coerce')
    return {str(k): (None if pd.isna(v) else float(v)) for k, v in zip(df['data_id'], s)}


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
            columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note', '_hist_yield', '_hist_source', '_hist_net']
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
        cur_net = _net_series(df)

        # 旧记录无基线 → 静默建立基线
        if missing_baseline.any():
            init_records = list(zip(
                df.loc[missing_baseline, 'data_id'],
                cur_qty[missing_baseline],
                cur_note[missing_baseline],
                cur_yield[missing_baseline],
                cur_net[missing_baseline],
            ))
            save_snapshot_batch(init_records)

        # v43.380：老记录基线缺净偏差数量 → 静默补写（只补 net 列，不动其他基线），
        # 使后续净偏差数量变动可被检测、变动提醒可展示修改前/后净偏差数量。
        net_backfill_mask = has_baseline & df['_hist_net'].isna()
        if net_backfill_mask.any():
            backfill_net_baseline(list(zip(
                df.loc[net_backfill_mask, 'data_id'],
                cur_net[net_backfill_mask],
            )))

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
        hist_net = pd.to_numeric(df['_hist_net'], errors='coerce')
        # 对需要详细比对的行进行比对
        detailed_indices = df.index[need_detailed]
        qty_changed = pd.Series(False, index=df.index)
        note_changed = pd.Series(False, index=df.index)
        yield_changed = pd.Series(False, index=df.index)
        net_changed = pd.Series(False, index=df.index)

        if len(detailed_indices) > 0:
            # 子集的向量化比对
            sub_df = df.loc[detailed_indices]
            sub_snap = pd.to_numeric(sub_df['_hist_snap'], errors='coerce')
            sub_note = sub_df['_hist_note'].apply(self._norm_note)
            sub_yield = pd.to_numeric(sub_df['_hist_yield'], errors='coerce')
            sub_net = pd.to_numeric(sub_df['_hist_net'], errors='coerce')
            sub_cur_qty = pd.to_numeric(sub_df[real_col], errors='coerce') if real_col else pd.Series([np.nan]*len(sub_df), index=sub_df.index)
            sub_cur_note = sub_df[remark_col].apply(self._norm_note) if remark_col else pd.Series(['']*len(sub_df), index=sub_df.index)
            sub_cur_yield = pd.to_numeric(sub_df[yield_col], errors='coerce') if yield_col else pd.Series([np.nan]*len(sub_df), index=sub_df.index)
            sub_cur_net = _net_series(sub_df)

            # 详细比对子集
            has_full_sub = sub_snap.notna() & sub_note.notna() & sub_yield.notna()
            qty_changed.loc[detailed_indices] = has_full_sub & sub_cur_qty.notna() & (abs(sub_snap - sub_cur_qty) >= 1e-6)
            note_changed.loc[detailed_indices] = has_full_sub & (sub_note != sub_cur_note)
            yield_changed.loc[detailed_indices] = has_full_sub & sub_cur_yield.notna() & (abs(sub_yield - sub_cur_yield) >= 1e-6)
            # v43.380：净偏差数量基线比对（替代料抵扣变化会导致净偏差数量单独变动）
            net_changed.loc[detailed_indices] = sub_net.notna() & sub_cur_net.notna() & (abs(sub_net - sub_cur_net) >= 1e-6)

        # 合并所有检测结果
        changed = qty_changed | note_changed | yield_changed | net_changed


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
            def _net_pair(_idx, qty_delta=0.0):
                """该行净偏差数量 (修改前基线, 修改后当前值)，缺基线时修改前为 None（v43.380）。

                v43.398：净偏差数量由偏差数量派生（非替代行净偏差=偏差数量，
                替代行按组内偏差和）。SAP 重导时实际数量变了，而源表「偏差数量」
                列未跟着变，导致变动提醒「净偏差数量(前/后)」永远相等。对实际
                数量变动的行，把变动量补给净偏差后值：净偏差后 = 导入净值 +
                (新实际−旧实际)，等价于按新实际修正偏差数量。非替代料行精确；
                替代料行在抵扣额不变时同样精确。qty_delta=0 时退化为原行为。
                """
                _old = hist_net.at[_idx] if '_hist_net' in df.columns else np.nan
                _old = float(_old) if pd.notna(_old) else None
                _new = cur_net.at[_idx]
                if pd.notna(_new) and abs(qty_delta) >= 1e-9:
                    # v43.402：round(2) 与净偏差列口径一致，去掉浮点长尾
                    _new = round(float(_new) + float(qty_delta), 2)
                _new = float(_new) if pd.notna(_new) else None
                return _old, _new

            changes_records = []
            for idx in df.index[qty_changed]:
                # v43.398：实际数量变动量 = 新实际 − 基线快照（基线即「修改前」值）
                _delta = 0.0
                try:
                    _old_qty = hist_snap.at[idx] if '_hist_snap' in df.columns else np.nan
                    _new_qty = cur_qty.at[idx]
                    if pd.notna(_old_qty) and pd.notna(_new_qty):
                        _delta = float(_new_qty) - float(_old_qty)
                except Exception:
                    import traceback
                    traceback.print_exc()
                net_old, net_new = _net_pair(idx, qty_delta=_delta)
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
                    'net_old': net_old, 'net_new': net_new,
                })
            for idx in df.index[note_changed]:
                net_old, net_new = _net_pair(idx)
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
                    'net_old': net_old, 'net_new': net_new,
                })
            for idx in df.index[yield_changed]:
                net_old, net_new = _net_pair(idx)
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
                    'net_old': net_old, 'net_new': net_new,
                })
            # v43.380：净偏差数量变动单独留痕（如替代料抵扣变化导致净偏差数量变动而实际数量未变）
            for idx in df.index[net_changed]:
                net_old, net_new = _net_pair(idx)
                changes_records.append((
                    df.at[idx, 'data_id'], '净偏差数量',
                    df.at[idx, '_hist_net'], cur_net.at[idx]
                ))
                self.last_audit_changes.append({
                    'data_id': df.at[idx, 'data_id'], 'field': '净偏差数量',
                    'workshop': df.at[idx, '车间'] if '车间' in df.columns else None,
                    'material_name': df.at[idx, '物料名称'] if '物料名称' in df.columns else (
                        df.at[idx, '物料描述'] if '物料描述' in df.columns else ''),
                    'old_value': net_old,
                    'new_value': net_new,
                    'net_old': net_old, 'net_new': net_new,
                })
            record_deviation_change_batch(changes_records)
            changed_count = int(changed.sum())
            self.log(f"⚠️ 发现 {changed_count} 条已审核记录的实际数量/备注原因/产量/净偏差数量被修改，已强制设为未读并留痕", "warning")
            self.log_signal.emit(f"变动提醒|{changed_count}", "alert")

        # 清理临时历史列
        df = df.drop(columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note', '_hist_yield', '_hist_source', '_hist_net'], errors='ignore')
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
        """变动提醒看板单一数据源（v44.06 口径）。

        基础判据：_post_audit_changed==1 且未读（_read==0）。
        v44.06 起默认排除两类行（裴哥 2026-11-20）：
        - 已在隔离区（_quarantined==1）：走隔离区流程，不进变动提醒；
        - 替代料行（core.threshold_config.substitute_mask 命中）：走替代料看板流程。
        例：纸箱原本无负损，改产量后净偏差转负 → 应进隔离区，不应留在变动提醒被误审核。
        注意：结果与主表 _post_audit_changed 列不再完全一致；
        KPI「审核后变更」（stats_cards）仍按 _post_audit_changed 原口径统计，不受影响。
        """
        if df is None or getattr(df, 'empty', True) or '_post_audit_changed' not in df.columns:
            return []
        mask = pd.to_numeric(df['_post_audit_changed'], errors='coerce').fillna(0).astype(int) == 1
        if '_read' in df.columns:
            mask = mask & (pd.to_numeric(df['_read'], errors='coerce').fillna(0).astype(int) == 0)
        # v44.06：已在隔离区的行走隔离区流程，不进变动提醒
        if '_quarantined' in df.columns:
            _quar = pd.to_numeric(df['_quarantined'], errors='coerce').fillna(0).astype(int) == 1
            mask = mask & ~_quar
        # v44.06：替代料行走替代料流程，不进变动提醒（与看板/异常判定同一真源）
        _alt = substitute_mask(df)
        if _alt is not None:
            mask = mask & ~_alt.astype(bool)
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
                columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note', '_hist_yield', '_hist_source', '_hist_net'])
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
        if '_hist_net' not in sub.columns:
            sub['_hist_net'] = np.nan
        hist_yield = pd.to_numeric(sub['_hist_yield'], errors='coerce')
        hist_snap = pd.to_numeric(sub['_hist_snap'], errors='coerce')
        hist_note = sub['_hist_note'].apply(self._norm_note)
        hist_net = pd.to_numeric(sub['_hist_net'], errors='coerce')
        cur_net = _net_series(sub)

        changes = []
        for idx in sub.index:
            did = str(sub.at[idx, 'data_id'])
            hs_qty = hist_snap.at[idx]
            hs_note = hist_note.at[idx]
            cur_q = cur_qty.at[idx]
            cur_n = cur_note.at[idx]
            hs_yield = hist_yield.at[idx]
            cur_y = cur_yield.at[idx]
            hs_net = hist_net.at[idx]
            cur_nq = cur_net.at[idx]

            qty_diff = (not pd.isna(hs_qty)) and (not pd.isna(cur_q)) and (abs(float(hs_qty) - float(cur_q)) >= 1e-6)
            note_diff = (hs_note not in ('', None)) and (cur_n != hs_note)
            yield_diff = (not pd.isna(hs_yield)) and (not pd.isna(cur_y)) and (abs(float(hs_yield) - float(cur_y)) >= 1e-6)
            net_diff = (not pd.isna(hs_net)) and (not pd.isna(cur_nq)) and (abs(float(hs_net) - float(cur_nq)) >= 1e-6)

            # 净偏差数量修改前/后（v43.380：无论哪个字段变动，都附上净偏差数量前后值）
            # v43.401：本函数是变动提醒弹窗的唯一数据源（main_window:726 调用）。
            # 净偏差由偏差数量派生（非替代行净偏差=偏差数量），SAP 重导时实际变了但
            # 偏差数量源表列没变 → 若直接拿当前净偏差当「后值」，前后必然相等。
            # 对实际数量变动行，把变动量补给后值：后 = 导入净值 + (新实际−旧实际)；
            # 若基线净偏差缺失（老数据无 snapshot_net_qty），前值用「后值−变动量」反推，
            # 保证前后都能显示且反映真实变化。
            net_old = float(hs_net) if not pd.isna(hs_net) else None
            net_new = float(cur_nq) if not pd.isna(cur_nq) else None
            if qty_diff and net_new is not None:
                try:
                    _delta = float(cur_q) - float(hs_qty)
                    # v43.402：与净偏差列本身口径一致（analyzer 写列时 .round(2)），
                    # 浮点相加会留 -40.867000000000006 这种长尾，统一收两位。
                    net_new = round(net_new + _delta, 2)
                    if net_old is None:
                        net_old = round(net_new - _delta, 2)
                except (TypeError, ValueError):
                    pass

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
            elif net_diff:
                field = '净偏差数量'
                ov = net_old
                nv = net_new
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
                'net_old': net_old,
                'net_new': net_new,
            })
        return changes

    def detect_and_notify_changes(self, old_df: pd.DataFrame, new_df: pd.DataFrame):
        """同会话重新分析时，检测已审核记录的变动并通知（方案A）"""
        old_qty = {}
        old_note = {}
        old_net = {}
        try:
            real_col_old = self._find_real_qty_col(old_df)
            remark_col_old = self._find_remark_col(old_df)
            for _, row in old_df.iterrows():
                if self._is_record_audited(row):
                    did = row['data_id']
                    old_qty[did] = self._safe_qty(row.get(real_col_old))
                    old_note[did] = self._norm_note(row.get(remark_col_old)) if remark_col_old else ''
                    old_net[did] = self._safe_qty(row.get(NET_QTY_COL)) if NET_QTY_COL in old_df.columns else None
        except Exception as e:
            self.log(f"构建旧快照失败: {e}", "error")

        real_col_new = self._find_real_qty_col(new_df)
        remark_col_new = self._find_remark_col(new_df)
        new_wk = {}  # did -> 车间
        new_name = {}  # did -> 物料名称
        new_net = {}  # did -> 当前净偏差数量（v43.380）
        changes = []  # (did, old_val, new_val, field)
        self.last_audit_changes = []  # 重置
        try:
            for _, row in new_df.iterrows():
                if self._is_record_audited(row):
                    did = row['data_id']
                    new_wk[did] = row.get('车间')
                    new_name[did] = row.get('物料名称') or row.get('物料描述') or ''
                    new_net[did] = self._safe_qty(row.get(NET_QTY_COL)) if NET_QTY_COL in new_df.columns else None
                    if did in old_qty:
                        old_q = old_qty[did]
                        new_q = self._safe_qty(row.get(real_col_new))
                        if old_q is not None and new_q is not None and abs(old_q - new_q) >= 1e-6:
                            changes.append((did, old_q, new_q, '实际数量'))
                    if did in old_note:
                        new_n = self._norm_note(row.get(remark_col_new)) if remark_col_new else ''
                        if old_note[did] != new_n:
                            changes.append((did, old_note[did], new_n, '备注原因'))
                    if did in old_net:
                        old_nq = old_net[did]
                        new_nq = new_net.get(did)
                        if old_nq is not None and new_nq is not None and abs(old_nq - new_nq) >= 1e-6:
                            changes.append((did, old_nq, new_nq, '净偏差数量'))
        except Exception as e:
            self.log(f"检测变动失败: {e}", "error")

        if changes:
            try:
                for did, old_v, new_v, field in changes:
                    from core.read_status import record_deviation_change
                    record_deviation_change(did, field, old_v, new_v, "重新分析数据变动")
            except Exception as e:
                self.log(f"记录变动失败: {e}", "error")
            self.log(f"发现 {len(changes)} 条已审核记录的实际数量/备注原因/净偏差数量发生变动，已强制设为'未读'", "warning")
            for did, old_v, new_v, field in changes:
                _n_old = old_net.get(did)
                _n_new = new_net.get(did)
                # v43.400：净偏差由偏差数量派生（非替代行净偏差=偏差数量），而 SAP
                # 重导时「实际」变了但「偏差数量」源表列没变 → 变动提醒前后两列相等。
                # 对「实际数量」变动行，把变动量补给 net_new（等价按新实际修正偏差数量）：
                # 净偏差后 = 导入净值 + (新实际−旧实际)。非替代行精确、替代行抵扣不变时同样精确。
                if field == '实际数量' and old_v is not None and new_v is not None \
                        and _n_new is not None:
                    try:
                        _n_new = round(float(_n_new) + (float(new_v) - float(old_v)), 2)  # v43.402：去浮点长尾
                    except (TypeError, ValueError):
                        pass
                self.last_audit_changes.append({
                    'data_id': did, 'field': field,
                    'workshop': new_wk.get(did),
                    'material_name': new_name.get(did) or '',
                    'old_value': old_v, 'new_value': new_v,
                    'net_old': _n_old, 'net_new': _n_new})
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
            net_lookup = _net_lookup(df)  # v43.380：净偏差数量基线一并快照
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
                snapshot_map[did] = (snap_qty, snap_note, snap_yield, net_lookup.get(did))
            mark_read_batch(list(dids), snapshot_map, read_source='manual')
            self.last_audit_changes = []
            return len(dids), dids
        except Exception as e:
            self.log(f"批量标记已读失败: {e}", "error")
            return 0, set()
