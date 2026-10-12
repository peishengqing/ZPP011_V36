# -*- coding: utf-8 -*-
"""一次性历史回填：扫描源数据目录所有 xlsx，把「编码→名称」灌进 audit.db 的 material_names 表。

背景（v43.186）：
    audit.db 的 deviation_history / read_status / quarantine_records 三表均无物料名称列，
    名称只能从源数据拿。稳定性看板流水跨月，而主表只含本期物料，导致历史月份物料名称留空。
    本脚本把历史源文件里的编码→名称一次性沉淀进持久缓存，立刻补齐全部历史物料名；
    之后每次分析都会自动 upsert，本脚本只需在「换机器 / 新库 / 源目录变动」时重跑。

用法：
    python tools/backfill_material_names.py [源目录]
    默认源目录 = E:\ZPP011导出文件原数据
"""
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # 仅本工具依赖，不污染 core 模块
from core.read_status import upsert_material_names

DEFAULT_BASE = "E:\\ZPP011导出文件原数据"


def collect(base):
    files = sorted(set(
        glob.glob(os.path.join(base, "*.xlsx")) +
        glob.glob(os.path.join(base, "**", "*.xlsx"), recursive=True)
    ))
    files = [f for f in files if not os.path.basename(f).startswith("~$")]
    mapping = {}
    skipped = 0
    for f in files:
        try:
            df = pd.read_excel(f, sheet_name="Data", dtype=str,
                               usecols=["组件物料号", "组件物料描述"])
        except Exception:
            skipped += 1
            continue
        df.columns = [str(c).strip() for c in df.columns]
        if "组件物料号" not in df.columns or "组件物料描述" not in df.columns:
            skipped += 1
            continue
        for code, nm in zip(df["组件物料号"], df["组件物料描述"]):
            c = str(code).strip()
            n = str(nm).strip()
            if c and c.lower() != "nan" and n and n.lower() != "nan":
                mapping[c] = n
    return files, skipped, mapping


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    if not os.path.isdir(base):
        print("源目录不存在: %s" % base)
        sys.exit(1)
    files, skipped, mapping = collect(base)
    n = upsert_material_names(mapping)
    print("扫描 %d 个 xlsx（跳过 %d 个无目标列的文件），灌入 %d 条 编码→名称。"
          % (len(files), skipped, n))


if __name__ == "__main__":
    main()
