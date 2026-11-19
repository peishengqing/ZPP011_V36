# -*- coding: utf-8 -*-
"""v44.05：切工厂 = 换视图，不重跑自动已读 / 自动隔离。

用户口径：「默认进去按全部规则自动运行，再点到分工厂就不用再重新跑自动隔离区和
自动已读」。

成立的三个条件，逐个钉住：
1. 分析阶段只跑一次规则（整份 df），切厂只是切切片。
2. 切片本身已经带 `_read`（在 preprocess 之后分组），所以切厂走复用分支。
3. 切厂函数里不出现任何规则计算调用——否则「点一下」就会变成又一次全量匹配。
"""
import inspect
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.controllers.data_controller import DataController  # noqa: E402


def test_switch_factory_has_no_rule_reevaluation():
    src = inspect.getsource(DataController._on_factory_changed)
    for forbidden in ("compute_auto_read_mask", "compute_auto_quarantine_ids",
                      "_auto_read_by_rules", "_auto_move_to_quarantine"):
        assert forbidden not in src, f"切工厂不应调用 {forbidden}"


def test_switch_factory_reuses_preprocessed_slice():
    src = inspect.getsource(DataController._on_factory_changed)
    # 有 _read 就直接复用；只有拿不到预处理结果时才在主线程补一次 preprocess
    assert "'_read' in df.columns" in src
    assert "preprocess_audit_data" in src


def test_analysis_finished_runs_rules_once_on_whole_df():
    from gui_pyside6.view_manager import ViewManager

    src = inspect.getsource(ViewManager.run_ui_finished)
    # 规则作用在整份 processed_df 上（不是逐厂），且发生在分析收尾
    assert "_auto_read_by_rules(processed_df)" in src
    assert src.count("_auto_read_by_rules") == 1


def test_factory_slices_carry_read_column():
    """preprocess 之后才分组——所以每个厂切片天然带 _read，切厂无需重算。"""
    from gui_pyside6.services.data_grouping import get_combined_factory_data

    df = pd.DataFrame({
        "工厂": ["1101"] * 2 + ["1102"] * 2,
        "物料编码": ["A", "B", "C", "D"],
        "_read": [1, 0, 1, 0],
    })
    factories, _all = get_combined_factory_data(df, "工厂")
    assert set(factories) == {"1101", "1102"}
    for name, part in factories.items():
        assert "_read" in part.columns, name
