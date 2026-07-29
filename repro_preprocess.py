# -*- coding: utf-8 -*-
"""
不依赖 Qt 的纯 Python 计时脚本：定位 preprocess_audit_data 真实慢点
inline 复制 data_service 的各方法，逐步计时
"""
import time
import glob
import os
import sys
import traceback
import numpy as np
import pandas as pd

sys.path.insert(0, 'E:/zpp011_v2')

from analysis.analyzer import do_analysis_v2
from core.read_status import (
    load_read_status, load_audit_results,
    record_deviation_change, record_deviation_change_batch,
    get_deviation_history, save_snapshot_batch,
)
from core.quarantine_manager import get_quarantined_ids


# ====== 复制 data_service 的方法（仅去除 self）======

def _clean_columns(df):
    if '替代料组' in df.columns and '_替代料组' in df.columns:
        df = df.drop(columns=['替代料组'])
    if '净偏差' in df.columns and '净偏差金额' in df.columns:
        df = df.drop(columns=['净偏差'])
    if '偏差率' in df.columns and '偏差率(%)' in df.columns:
        df = df.drop(columns=['偏差率'])
    dup_cols = df.columns[df.columns.duplicated()].unique()
    if len(dup_cols) > 0:
        df = df.loc[:, ~df.columns.duplicated(keep='first')]
    return df


def _normalize_alt_flag(df):
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


def _add_data_id_and_fingerprint(df):
    try:
        df['data_id'] = (df['订单日期'].astype(str) + '|' +
                         df['流程订单'].astype(str) + '|' +
                         df['物料编码'].astype(str))
    except Exception as e:
        df['data_id'] = df.index.astype(str)

    try:
        amount_col = '偏差金额(含税)' if '偏差金额(含税)' in df.columns else '偏差金额'
        amount = pd.to_numeric(df[amount_col], errors='coerce').fillna(0.0) if amount_col in df.columns else pd.Series(0.0, index=df.index)
        rate = pd.to_numeric(df['偏差率(%)'], errors='coerce').fillna(0.0) if '偏差率(%)' in df.columns else pd.Series(0.0, index=df.index)
        df['fingerprint'] = amount.round(2).astype(str) + '|' + rate.round(1).astype(str)
    except Exception as e:
        df['fingerprint'] = "0.00|0.0"
    return df


def _find_real_qty_col(df):
    candidates = ['数量-实际', '实际', '实际数量', '数量 - 实际', 'actual',
                  '实际收货数量', '已收货数量', '收货数量', '实际领用数量', '实收数量']
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        s = str(c)
        if '实际' in s and '数量' in s:
            return c
    return None


def _find_remark_col(df):
    for c in ['备注原因', '备注', '审核备注', '偏差备注', 'remark']:
        if c in df.columns:
            return c
    return None


def _norm_note(v):
    if v is None:
        return ''
    if isinstance(v, float) and pd.isna(v):
        return ''
    s = str(v).strip()
    if s.lower() in ('nan', 'none', 'nat', ''):
        return ''
    return s


def _restore_read_status(df):
    try:
        data_ids = df['data_id'].tolist()
        status_map = load_read_status(data_ids)
    except Exception as e:
        status_map = {}

    real_col = _find_real_qty_col(df)
    remark_col = _find_remark_col(df)
    if not status_map:
        df['_read'] = 0
        df['_post_audit_changed'] = 0
        return df

    status_df = pd.DataFrame.from_dict(
        status_map, orient='index',
        columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note']
    )
    df = df.join(status_df, on='data_id')

    has_status = df['_hist_read'].notna()
    missing_baseline = has_status & (df['_hist_snap'].isna() | df['_hist_note'].isna())
    has_baseline = has_status & ~missing_baseline

    if real_col:
        cur_qty = pd.to_numeric(df[real_col], errors='coerce')
    else:
        cur_qty = pd.Series([np.nan] * len(df), index=df.index)
    if remark_col:
        cur_note = df[remark_col].apply(_norm_note)
    else:
        cur_note = pd.Series([''] * len(df), index=df.index)

    if missing_baseline.any():
        init_records = list(zip(
            df.loc[missing_baseline, 'data_id'],
            cur_qty[missing_baseline],
            cur_note[missing_baseline],
        ))
        save_snapshot_batch(init_records)

    hist_snap = pd.to_numeric(df['_hist_snap'], errors='coerce')
    hist_note = df['_hist_note'].apply(_norm_note)
    qty_changed = has_baseline & cur_qty.notna() & (abs(hist_snap - cur_qty) >= 1e-6)
    note_changed = has_baseline & (hist_note != cur_note)
    changed = qty_changed | note_changed

    hist_read_int = df['_hist_read'].fillna(0).astype(int)
    df['_read'] = np.where(changed, 0, np.where(has_status, hist_read_int, 0))
    df['_post_audit_changed'] = changed.astype(int)

    if changed.any():
        changes_records = []
        for idx in df.index[qty_changed]:
            changes_records.append((
                df.at[idx, 'data_id'], '实际数量',
                df.at[idx, '_hist_snap'], cur_qty.at[idx]
            ))
        for idx in df.index[note_changed]:
            changes_records.append((
                df.at[idx, 'data_id'], '备注原因',
                df.at[idx, '_hist_note'], cur_note.at[idx]
            ))
        record_deviation_change_batch(changes_records)

    df = df.drop(columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note'], errors='ignore')
    return df


def _restore_quarantine_status(df):
    try:
        qids = get_quarantined_ids()
    except Exception as e:
        qids = set()
    df['_quarantined'] = 0
    if qids and 'data_id' in df.columns:
        df.loc[df['data_id'].isin(qids), '_quarantined'] = 1
    return df


def _reorder_columns(df):
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
            df = df[cols]
    except Exception as e:
        pass
    return df


def _restore_audit_results(df):
    try:
        data_ids = df['data_id'].tolist()
        audit_map = load_audit_results(data_ids)
    except Exception as e:
        return df
    if not audit_map:
        return df
    for col, key in [('审核结果', 'audit_result'), ('AI建议', 'ai_suggestion'), ('备注来源', 'note_source')]:
        if col not in df.columns:
            df[col] = ''
        mapped = df['data_id'].map(lambda did: audit_map.get(did, {}).get(key, ''))
        current = df[col].astype(str).replace('nan', '').replace('None', '')
        is_empty = df[col].isna() | (current.str.strip() == '')
        if is_empty.any():
            df.loc[is_empty, col] = mapped[is_empty]
    return df


def _compute_net_deviation_rate(df):
    if '净偏差率(%)' in df.columns and df['净偏差率(%)'].notna().any():
        return df
    # 兜底（实际不会走这里）
    return df


def _time(name, fn, *a, **k):
    t0 = time.perf_counter()
    r = fn(*a, **k)
    print(f"  [计时] {name}: {time.perf_counter()-t0:.3f}s")
    return r


def main():
    files = glob.glob(r'E:\ZPP011导出文件原数据\ZPP011_*.xlsx')
    files = [f for f in files if not os.path.basename(f).startswith('~$')]
    files.sort(key=os.path.getmtime, reverse=True)
    src = files[0]
    print(f'文件: {src}  大小: {os.path.getsize(src)/1024/1024:.1f}MB')

    t0 = time.perf_counter()
    df = do_analysis_v2(input_file=src, output_dir=None, alt_pairs=[],
                        start_date='', end_date='', material_search='',
                        output_path=None, enable_net_offset=True,
                        return_dataframe=True)
    print(f'[计时] do_analysis_v2: {time.perf_counter()-t0:.2f}s, shape={df.shape}')
    print(f'  列: {list(df.columns)}')
    print()

    # 复制 df，逐步计时
    df1 = df.copy()
    df1 = _time('_clean_columns', _clean_columns, df1)
    print(f'  形状: {df1.shape}')

    # pd.to_numeric 8 列
    rate_col = None
    for c in ['偏差率(%)', '偏差率']:
        if c in df1.columns:
            rate_col = c
            break
    t0 = time.perf_counter()
    if rate_col:
        if df1[rate_col].dtype == object:
            df1[rate_col] = df1[rate_col].astype(str).str.replace('%', '', regex=False)
        df1[rate_col] = pd.to_numeric(df1[rate_col], errors='coerce').fillna(0.0)
    for num_col in ['定额', '实际', '偏差数量', '偏差金额', '偏差金额(含税)', '净偏差数量', '净偏差金额', '净偏差率(%)']:
        if num_col in df1.columns:
            df1[num_col] = pd.to_numeric(df1[num_col], errors='coerce').fillna(0.0)
    print(f"  [计时] pd.to_numeric 8 列: {time.perf_counter()-t0:.3f}s")

    df1 = _time('_normalize_alt_flag', _normalize_alt_flag, df1)
    df1 = _time('_add_data_id_and_fingerprint', _add_data_id_and_fingerprint, df1)
    df1 = _time('_restore_read_status', _restore_read_status, df1)
    df1 = _time('_restore_quarantine_status', _restore_quarantine_status, df1)
    df1 = _time('_reorder_columns', _reorder_columns, df1)
    df1 = _time('_restore_audit_results', _restore_audit_results, df1)
    df1 = _time('_compute_net_deviation_rate', _compute_net_deviation_rate, df1)

    print(f'\n最终 shape: {df1.shape}')

    # ============ SQLite 库体检（诊断 6:55 的关键）============
    print('\n==== SQLite 库体检 ====')
    try:
        import sqlite3 as _sql
        _db = os.path.join(os.path.expanduser('~'), '.zpp011_audit', 'audit.db')
        if os.path.exists(_db):
            _c = _sql.connect(_db)
            for _t in ['read_status', 'deviation_history', 'quarantine']:
                try:
                    _n = _c.execute(f'SELECT COUNT(*) FROM {_t}').fetchone()[0]
                    _idx = [r[0] for r in _c.execute(
                        f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{_t}'").fetchall()]
                    print(f'  {_t}: {_n} rows  索引={_idx}')
                except Exception as _e:
                    print(f'  {_t}: 查询失败 {_e}')
            _c.close()
        else:
            print(f'  库不存在: {_db}')
    except Exception as _e:
        print(f'  库体检失败: {_e}')

    # 单测 SQLite 读取
    print('\n==== 单测 SQLite 读取 ====')
    t0 = time.perf_counter()
    sm = load_read_status(df1['data_id'].tolist())
    print(f'  [计时] load_read_status({len(df1)}): {time.perf_counter()-t0:.3f}s, size={len(sm)}')

    t0 = time.perf_counter()
    am = load_audit_results(df1['data_id'].tolist())
    print(f'  [计时] load_audit_results({len(df1)}): {time.perf_counter()-t0:.3f}s, size={len(am)}')

    t0 = time.perf_counter()
    qids = get_quarantined_ids()
    print(f'  [计时] get_quarantined_ids: {time.perf_counter()-t0:.3f}s, size={len(qids)}')

    # 单测：from_dict + df.join
    if sm:
        print('\n==== 单测：from_dict / df.join ====')
        t0 = time.perf_counter()
        status_df = pd.DataFrame.from_dict(sm, orient='index',
                                            columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note'])
        print(f'  [计时] from_dict({len(sm)}): {time.perf_counter()-t0:.3f}s')
        t0 = time.perf_counter()
        df2 = df1.copy()
        joined = df2.join(status_df, on='data_id')
        print(f'  [计时] df.join(status_df, on=data_id) {len(df1)}: {time.perf_counter()-t0:.3f}s')

    # 单测：cur_note.apply（13K 行）
    if '备注原因' in df1.columns or '备注' in df1.columns:
        print('\n==== 单测：cur_note.apply vs 向量化 ====')
        rem_col = '备注原因' if '备注原因' in df1.columns else '备注'
        s = df1[rem_col]
        t0 = time.perf_counter()
        _ = s.apply(_norm_note)
        print(f'  [计时] apply(_norm_note) {len(df1)}: {time.perf_counter()-t0:.3f}s')

        t0 = time.perf_counter()
        # 向量化版
        s2 = s.astype("string").fillna("")
        s2 = s2.str.strip()
        s2 = s2.where(~s2.str.lower().isin(['nan', 'none', 'nat', '']), "")
        s2 = s2.astype(object)
        print(f'  [计时] 向量化 _norm_note {len(df1)}: {time.perf_counter()-t0:.3f}s')

    # ============ 真实 DataService 调用（最权威的 preprocess 耗时）============
    print('\n==== 真实 DataService.preprocess_audit_data 计时 ====')
    try:
        from gui_pyside6.services.data_service import DataService
        ds = DataService()
        # 用本次分析的真 df（未预处理的 dev_df）跑一次完整 preprocess
        t0 = time.perf_counter()
        real_processed = ds.preprocess_audit_data(df, previous_df=None)
        real_cost = time.perf_counter() - t0
        print(f'  [计时] DataService.preprocess_audit_data({len(df)} 行): {real_cost:.3f}s')
        print(f'  返回 shape={real_processed.shape} 带_read列={"_read" in real_processed.columns}')
        # 再次调用（模拟「主线程 fallback 重跑」场景）
        t0 = time.perf_counter()
        ds.preprocess_audit_data(df, previous_df=None)
        print(f'  [计时] 第2次调用（fallback 模拟）: {time.perf_counter()-t0:.3f}s')
    except Exception as _e:
        print(f'  真实调用失败（可能 QObject 依赖）: {_e}')


if __name__ == '__main__':
    main()
