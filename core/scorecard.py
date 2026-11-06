# -*- coding: utf-8 -*-
"""D2 依赖：纯逻辑数据质量评分卡（无 PyQt，可独立单测）。

复用 data_stability_dialog._fill_score 的口径（权重 备注覆盖率50% / 归因漂移率30% / 替代料长链数20%），
改为纯函数，供 core.change_summary / GUI 面板 / D1 历史库回填统一调用，避免重复实现口径漂移。
"""
import os
import json
from collections import defaultdict
from typing import Dict, Optional, Tuple

import pandas as pd

from core.read_status import DB_PATH


def _drift_rate_from_db() -> float:
    """归因漂移率 = deviation_history 中 field='备注原因' 占比（沿用 _fill_score 口径）。"""
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            cnt_note = conn.execute(
                "select count(*) from deviation_history "
                "where data_id<>'X' and data_id is not null and field='备注原因'"
            ).fetchone()[0]
            tot = conn.execute(
                "select count(*) from deviation_history "
                "where data_id<>'X' and data_id is not null"
            ).fetchone()[0]
        finally:
            conn.close()
        return (cnt_note / tot) if tot else 0.0
    except Exception:
        return 0.0


def _alt_chain_count() -> Tuple[int, int]:
    """替代料长链数（出现于 >1 个组的物料编码数）。读 %APPDATA%\\ZPP011\\config\\alt_pairs.json。"""
    cfg = os.path.join(os.environ.get("APPDATA", ""), "ZPP011", "config", "alt_pairs.json")
    try:
        if not os.path.exists(cfg):
            return (0, 0)
        with open(cfg, encoding="utf-8") as f:
            d = json.load(f)
        cnt = defaultdict(int)
        for grp in d:
            if not isinstance(grp, list):
                continue
            for s in grp:
                if not isinstance(s, (list, tuple)) or len(s) < 3:
                    continue
                cnt[str(s[1])] += 1
        chains = [c for c, n in cnt.items() if n > 1]
        return (len(chains), len(cnt))
    except Exception:
        return (0, 0)


def compute_scorecard(main_df: Optional[pd.DataFrame]) -> Dict:
    """计算数据质量评分卡，返回 dict（coverage_rate/drift_rate/long_chain_cnt/score_total/...）。

    权重：备注覆盖率 50% / 归因漂移率 30% / 替代料长链数 20%（写进返回字段便于核对）。
    """
    drift_rate = _drift_rate_from_db()
    chains_count, total_materials = _alt_chain_count()

    coverage = None
    if main_df is not None and len(main_df) and "备注原因" in main_df.columns:
        _has = main_df["备注原因"].notna() & (
            main_df["备注原因"].astype(str).str.strip() != "")
        coverage = float(_has.sum()) / len(main_df)

    coverage_sub = coverage * 100.0 if coverage is not None else None
    drift_sub = 100.0 * (1.0 - min(drift_rate, 1.0))
    chain_ratio = (chains_count / total_materials) if total_materials > 0 else 0.0
    chain_sub = 100.0 * (1.0 - min(chain_ratio, 1.0))

    if coverage_sub is not None:
        final = 0.5 * coverage_sub + 0.3 * drift_sub + 0.2 * chain_sub
    else:
        # 备注覆盖率缺失，按其余两项加权归一（0.3+0.2=0.5）
        final = (0.3 * drift_sub + 0.2 * chain_sub) / 0.5

    concl = []
    if coverage is not None and coverage < 0.5:
        concl.append("备注覆盖率偏低，建议补全偏差备注原因")
    if drift_rate > 0.3:
        concl.append("归因漂移偏高，建议复核 TOP 反复修改物料")
    if chains_count > 10:
        concl.append("替代料长链较多，建议复核替代料配对")
    if not concl:
        concl.append("数据质量良好")
    note_suffix = "" if coverage_sub is not None else "；备注覆盖率缺失，按其余两项加权"

    return {
        "coverage_rate": round(coverage, 4) if coverage is not None else None,
        "drift_rate": round(drift_rate, 4),
        "long_chain_cnt": chains_count,
        "score_total": round(final, 2),
        "coverage_sub": round(coverage_sub, 2) if coverage_sub is not None else None,
        "drift_sub": round(drift_sub, 2),
        "chain_sub": round(chain_sub, 2),
        "conclusion": "；".join(concl) + note_suffix,
    }
