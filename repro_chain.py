"""
repro_chain.py —— 忠实复刻主表真实加载链，逐步计时，定位 8 分钟卡顿真因
用法（在能跑 PySide6 的环境）:
    python repro_chain.py
它会用真实 13327 行数据 + 真实 DataFrameModel/AuditProxyModel/FilterPanel/StatsCardsWidget，
打印每一步耗时（秒级），不用再等 8 分钟全量分析。
窗口会打开，关闭即退出。
"""
import sys
import time
import traceback

sys.path.insert(0, r"E:\zpp011_v2")

from PySide6.QtWidgets import QApplication, QTableView, QHeaderView
from PySide6.QtCore import Qt

import pandas as pd

from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
from gui_pyside6.widgets.filter_panel import FilterPanel
from gui_pyside6.widgets.stats_cards import StatsCardsWidget
from gui_pyside6.services.data_service import DataService
from analysis.analyzer import do_analysis_v2
from domain.alt_material.alt_manager import load_alt_pairs


def load_real_df():
    src = r"E:\ZPP011导出文件原数据\ZPP011_20260701-20260728.xlsx"
    pairs = load_alt_pairs()
    df = do_analysis_v2(src, None, pairs, return_dataframe=True)
    ds = DataService()
    processed = ds.preprocess_audit_data(df)
    return processed


def make_fake_df(n):
    import numpy as np
    rng = np.random.default_rng(1)
    data = {"data_id": [f"2026-07-{i%28+1:02d}|100278312|20000389|{i}" for i in range(n)]}
    for i in range(1, 31):
        if i % 3 == 0:
            data[f"文本列{i}"] = [f"物料{rng.integers(1000,9999)}" for _ in range(n)]
        else:
            data[f"数值列{i}"] = (rng.random(n) * 1000).round(2)
    return pd.DataFrame(data)


def tprint(label, dt):
    print(f"[计时] {label}: {dt:.3f}s", flush=True)


def main():
    use_real = "--fake" not in sys.argv
    app = QApplication(sys.argv)

    # ---- 真实接线（与 main_window.py:1961-1978 一致）----
    source_model = DataFrameModel()
    proxy = AuditProxyModel()
    proxy.setSourceModel(source_model)
    view = QTableView()
    view.setAlternatingRowColors(True)
    view.setSortingEnabled(False)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    view.verticalHeader().setDefaultSectionSize(24)
    view.setModel(proxy)

    # _update_summary 已挂在 dataChanged/layoutChanged（真实也这样）
    summary_calls = {"n": 0}
    def fake_update_summary(*a, **k):
        summary_calls["n"] += 1
    source_model.dataChanged.connect(fake_update_summary)
    proxy.layoutChanged.connect(fake_update_summary)
    source_model.modelReset.connect(lambda *a, **k: None)

    filter_panel = FilterPanel()
    stats_cards = StatsCardsWidget()

    # ---- 加载数据 ----
    if use_real:
        print("加载真实数据（分析 + 预处理）...", flush=True)
        t0 = time.perf_counter()
        processed = load_real_df()
        tprint("分析+预处理(do_analysis_v2+preprocess)", time.perf_counter() - t0)
        print(f"  行数={len(processed)} 列数={len(processed.columns)}", flush=True)
    else:
        processed = make_fake_df(13327)
        print("使用假数据 13327 行", flush=True)

    # ---- 逐步计时（忠实复刻 _on_analysis_finished_ui）----
    # 1) setDataFrame（含 endResetModel → 代理首次重过滤；dataChanged → 代理二次重过滤）
    t0 = time.perf_counter()
    source_model.setDataFrame(processed)
    tprint("1) source_model.setDataFrame(含代理重过滤)", time.perf_counter() - t0)

    # 2) filterAcceptsRow 单独压测（代理全量重过滤一次的成本）
    t0 = time.perf_counter()
    n = source_model.rowCount()
    acc = 0
    for r in range(n):
        acc += 1 if proxy.filterAcceptsRow(r, proxy.index(r, 0).parent()) else 0
    tprint(f"2) filterAcceptsRow × {n}（代理全量重过滤）", time.perf_counter() - t0)

    # 3) filter_panel.update_options（真实复刻）
    t0 = time.perf_counter()
    try:
        filter_panel.update_options(processed)
        tprint("3) filter_panel.update_options", time.perf_counter() - t0)
    except Exception as e:
        tprint("3) filter_panel.update_options [异常]", time.perf_counter() - t0)
        traceback.print_exc()

    # 4) stats_cards.refresh（真实复刻）
    t0 = time.perf_counter()
    try:
        stats_cards.refresh(processed)
        tprint("4) stats_cards.refresh", time.perf_counter() - t0)
    except Exception as e:
        tprint("4) stats_cards.refresh [异常]", time.perf_counter() - t0)
        traceback.print_exc()

    # 5) 非空颜色筛选压测（验证 filterAcceptsRow 在 _custom_filters 非空时是否爆炸）
    for mode, flt in [("空筛选 {}", {}),
                       ("偏差率预警", {"_alert_only": True}),
                       ("替代料", {"_substitute_only": True}),
                       ("未投料", {"_unused_only": True})]:
        t0 = time.perf_counter()
        proxy.setCustomFilters(flt)
        tprint(f"5) proxy.setCustomFilters({mode})", time.perf_counter() - t0)
    proxy.setCustomFilters({})  # 复位

    # 6) 首屏绘制（真实：view 显示后 processEvents，经代理渲染全部可见行）
    view.resize(1200, 800)
    view.show()
    t0 = time.perf_counter()
    app.processEvents()
    tprint("6) 首屏 processEvents（经代理渲染）", time.perf_counter() - t0)

    # 7) data() 全量压测（经代理取所有单元格 DisplayRole，模拟滚动渲染）
    t0 = time.perf_counter()
    acc = 0
    for r in range(n):
        for c in range(proxy.columnCount()):
            idx = proxy.index(r, c)
            v = proxy.data(idx, Qt.DisplayRole)
            if v is not None:
                acc += 1
    tprint(f"7) proxy.data(DisplayRole) 全量 {n}×{proxy.columnCount()}", time.perf_counter() - t0)

    print(f"\n_summary 被触发次数: {summary_calls['n']}", flush=True)
    print("窗口已打开，可手动验证；关闭即退出。", flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
