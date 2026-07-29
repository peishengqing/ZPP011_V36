# -*- coding: utf-8 -*-
"""
repro_preprocess.py —— 单独计时 preprocess_audit_data 的每个子步骤（不依赖主窗口）。
用法（在能跑 PySide6 的环境）:
    python repro_preprocess.py
它会用真实 13327 行数据，打印每个子步骤耗时（秒级），定位 preprocess 的慢点。
"""
import sys
import time
import functools

sys.path.insert(0, r"E:\zpp011_v2")

from gui_pyside6.services.data_service import DataService
from analysis.analyzer import do_analysis_v2
from domain.alt_material.alt_manager import load_alt_pairs
import core.read_status as rs


def wrap_ds(name):
    orig = getattr(DataService, name)
    @functools.wraps(orig)
    def w(self, *a, **k):
        t0 = time.perf_counter()
        r = orig(self, *a, **k)
        print(f"[PREP] {name}: {time.perf_counter()-t0:.3f}s", flush=True)
        return r
    setattr(DataService, name, w)


for m in ['_clean_columns', '_normalize_alt_flag', '_add_data_id_and_fingerprint',
          '_restore_read_status', '_restore_quarantine_status', '_restore_audit_results',
          '_compute_net_deviation_rate', '_reorder_columns']:
    wrap_ds(m)


def wrap_rs(name):
    orig = getattr(rs, name)
    @functools.wraps(orig)
    def w(*a, **k):
        t0 = time.perf_counter()
        r = orig(*a, **k)
        print(f"[SQL ] {name}: {time.perf_counter()-t0:.3f}s", flush=True)
        return r
    setattr(rs, name, w)


for m in ['load_read_status', 'load_audit_results', 'get_quarantined_ids',
          'save_snapshot_batch', 'record_deviation_change_batch', 'get_deviation_history_batch']:
    if hasattr(rs, m):
        wrap_rs(m)


def main():
    src = r"E:\ZPP011导出文件原数据\ZPP011_20260701-20260728.xlsx"
    pairs = load_alt_pairs()
    t0 = time.perf_counter()
    df = do_analysis_v2(src, None, pairs, return_dataframe=True)
    print(f"[PREP] do_analysis_v2: {time.perf_counter()-t0:.3f}s", flush=True)

    ds = DataService()
    t0 = time.perf_counter()
    proc = ds.preprocess_audit_data(df)
    print(f"[PREP] preprocess TOTAL: {time.perf_counter()-t0:.3f}s", flush=True)
    print(f"  结果行数={len(proc)} 列数={len(proc.columns)}", flush=True)


if __name__ == "__main__":
    main()
