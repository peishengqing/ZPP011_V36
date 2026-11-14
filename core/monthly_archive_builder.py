# -*- coding: utf-8 -*-
"""跨月偏差归档回填服务：扫源文件目录 → 聚合 → 落归档表。

裴哥 2026-11-14 · 跨月趋势对比功能地基

职责（纯逻辑 + 存取，无 PyQt，可 offscreen 调用/单测）：
  1. 扫 get_data_dir()（含「前期」子目录）下所有 ZPP011_*.xlsx；
  2. 按文件名起始日归「文件月」，跳过 Excel 锁文件（~$开头）与非标准命名；
  3. 每个文件读一次快照（read_file_snapshot），行内业务月优先于文件月；
  4. aggregate_file_snapshots 聚合成 工厂×物料×业务月 行；
  5. save_archive 落库（upsert 幂等）。

性能：实测 20 文件 / 2.4 万行 ≈ 16s（openpyxl read_only 顺读）。
全量 200+ 文件首次回填约 1~2 分钟，落库后看板查询走 SQLite 索引，秒开。
故回填放后台线程跑（GUI 层负责），不阻塞主线程。

增量优化（本期不做，留口径）：同月已有「月末文件」且其 mtime 未变时可跳过该月，
但峰值需跨全部增量文件，故首版全量重扫最稳，不做半吊子增量。
"""
import glob
import os
import time
from typing import Callable, Dict, List, Optional

from core.monthly_archive import (
    aggregate_file_snapshots,
    biz_month_of_file,
    read_file_snapshot,
)
from core.monthly_archive_store import save_archive

# 数据目录里要递归扫的子目录名（裴哥把 6~10 月旧文件都收在「前期」里）
_SUBDIRS = ["前期"]


def _candidate_files(data_dir: str) -> List[str]:
    """列出数据目录（含「前期」子目录）下所有有效 ZPP011 源文件。

    跳过：Excel 锁文件（~$ 开头）、目录、非 ZPP011_ 命名（如 EXPORT_*/偏差分析_*）。
    返回绝对路径列表（不排序，聚合不依赖顺序）。
    """
    files: List[str] = []
    roots = [data_dir] + [os.path.join(data_dir, s) for s in _SUBDIRS]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for path in glob.glob(os.path.join(root, "ZPP011_*.xlsx")):
            base = os.path.basename(path)
            if base.startswith("~$"):
                continue
            if not os.path.isfile(path):
                continue
            files.append(path)
    return files


def backfill(
    data_dir: str,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> Dict:
    """全量回填归档表。返回统计 {scanned, parsed, skipped_files, rows, seconds}。

    progress(done, total, 当前文件名) 回调可选，GUI 用它刷进度条。
    单文件解析失败只跳过该文件（计入 skipped_files），不中断整体回填。
    """
    t0 = time.time()
    files = _candidate_files(data_dir)
    total = len(files)
    snapshots: List[Dict] = []
    skipped_files = 0
    for i, path in enumerate(files, 1):
        if progress:
            progress(i, total, os.path.basename(path))
        month = biz_month_of_file(path)  # 文件月（行内日期缺失时兜底）
        try:
            snap = read_file_snapshot(path, month=month)
        except Exception:  # noqa: BLE001  坏文件跳过，不拖垮整轮回填
            skipped_files += 1
            continue
        snapshots.append(snap)

    agg = aggregate_file_snapshots(snapshots)
    rows = list(agg.values())
    written = save_archive(rows)
    return {
        "scanned": total,
        "parsed": len(snapshots),
        "skipped_files": skipped_files,
        "rows": written,
        "seconds": round(time.time() - t0, 1),
    }