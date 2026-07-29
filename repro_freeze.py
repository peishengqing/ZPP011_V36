"""
repro_freeze.py —— 最小复现脚本（用于诊断主表首屏是否卡顿）
用法（在能跑 PySide6 的环境）:
    python repro_freeze.py            # 默认 13327 行，开斑马纹
    python repro_freeze.py --n 20000  # 自定义行数
    python repro_freeze.py --no-alt   # 关斑马纹，验证是否更慢/更快
只给「首次绘制」单独计时，几秒出结果，不会等 8 分钟全量分析。
窗口会打开，可手动验证是否流畅，关闭即退出。
"""
import sys
import time
import argparse

sys.path.insert(0, r"E:\zpp011_v2")

from PySide6.QtWidgets import QApplication, QTableView, QHeaderView
from PySide6.QtCore import Qt
import pandas as pd
import numpy as np

from gui_pyside6.models.data_frame_model import DataFrameModel


def make_fake(n, ncols):
    rng = np.random.default_rng(42)
    # 1 个 key 列 + (ncols-1) 个数值/文本列，模拟生产 31 列
    data = {}
    data["data_id"] = [f"2026-07-{i % 28 + 1:02d}|100278312|20000389|{i}" for i in range(n)]
    for i in range(1, ncols):
        if i % 3 == 0:
            data[f"文本列{i}"] = [f"物料{rng.integers(1000, 9999)}" for _ in range(n)]
        else:
            data[f"数值列{i}"] = (rng.random(n) * 1000).round(2)
    return pd.DataFrame(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=13327, help="行数")
    ap.add_argument("--no-alt", action="store_true", help="关闭斑马纹")
    args = ap.parse_args()

    n, ncols = args.n, 31
    print(f"生成假数据：{n} 行 × {ncols} 列", flush=True)

    df = make_fake(n, ncols)

    app = QApplication(sys.argv)
    view = QTableView()
    view.setWindowTitle("repro_freeze（最小复现）")

    # —— 复刻生产主表的关键配置 ——
    view.setAlternatingRowColors(not args.no_alt)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    view.verticalHeader().setDefaultSectionSize(24)
    view.verticalHeader().setVisible(True)
    # 生产样式（暗色 + 自动换行 + 表头居中）精简版
    view.setStyleSheet(
        "QTableView { gridline-color: #ddd; font-size: 12px; }"
        "QHeaderView::section { background: #f0f0f0; padding: 3px; "
        "border: 1px solid #ccc; text-align: center; }"
    )
    view.setWordWrap(True)

    model = DataFrameModel()
    model.setDataFrame(df)
    view.setModel(model)

    view.resize(1100, 700)
    view.show()

    # 首次绘制计时：强制处理一次事件循环，测 paint 耗时
    t0 = time.perf_counter()
    app.processEvents()
    dt = time.perf_counter() - t0
    alt = "False" if args.no_alt else "True"
    print(f"[结果] 首次绘制(setAlternatingRowColors={alt}) 耗时: {dt:.3f}s  (行数={n})", flush=True)
    print("窗口已打开，可手动验证是否流畅；关闭窗口即退出。", flush=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
