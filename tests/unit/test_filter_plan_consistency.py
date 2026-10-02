# -*- coding: utf-8 -*-
"""筛选计划（plan）一致性回归：新预计算实现必须与旧逐行实现逐行结果完全一致。

参照实现 ref_accepts() 为改动前 filterAcceptsRow 的逐行逻辑独立复刻（pandas iloc），
对 200 行合成数据 × 多组随机筛选字典逐行比对。
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import math
import random

import pytest
pytest.importorskip("PySide6")
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel


def _make_df(n=200):
    rng = random.Random(42)
    cols = {
        "工厂": [rng.choice(["上海", "广州"]) for _ in range(n)],
        "车间": [rng.choice(["一车间", "二车间"]) for _ in range(n)],
        "是否替代料": [rng.choice(["是", "否"]) for _ in range(n)],
        "订单类型": [rng.choice(["Z007", "Z002"]) for _ in range(n)],
        "流程订单": [f"SO{i:04d}" for i in range(n)],
        "产品物料号码": [rng.choice(["50001183", "60002244"]) for _ in range(n)],
        "组件物料号": [f"10{i:06d}" for i in range(n)],
        "物料描述": [rng.choice(["95g纸箱", "PE内袋", "标签"]) for _ in range(n)],
        "数量-定额": [float(rng.randint(0, 100)) for _ in range(n)],
        "数量-实际": [float(rng.randint(0, 100)) for _ in range(n)],
        "偏差数量": [float(rng.randint(-50, 50)) for _ in range(n)],
        "偏差率(%)": [None if rng.random() < 0.1 else round(rng.uniform(-30, 30), 3) for _ in range(n)],
        "备注原因": [rng.choice(["", "缺货", "客户指定", None]) for _ in range(n)],
        "订单开始日期": [f"2026-09-{rng.randint(1, 30):02d}" for _ in range(n)],
        "_read": [rng.choice([0, 1]) for _ in range(n)],
        "_read_source": [rng.choice(["", "auto", "manual"]) for _ in range(n)],
        "_quarantined": [rng.choice([0, 1]) for _ in range(n)],
        "半成品重分类": [rng.choice(["", "食品成品半成品", "饮料成品半成品", "X类"]) for _ in range(n)],
    }
    df = pd.DataFrame(cols)
    # 个别列的 NaN 注入（偏差率 已有 None）
    return df


def ref_accepts(row, df, cf, threshold=10.0):
    """改动前 filterAcceptsRow 逐行逻辑的独立复刻（参考实现）。"""
    row_data = df.iloc[row]

    def _to_float_safe(v):
        try:
            f = float(v)
            return f if not pd.isna(f) else 0.0
        except (ValueError, TypeError):
            return 0.0

    # 1. 精确列筛选
    for col_name, value in cf.items():
        if col_name.startswith("_"):
            continue
        if col_name not in df.columns:
            continue
        row_val = str(row_data.get(col_name, "")).strip()
        if row_val != str(value).strip():
            return False

    # 1.4 产品物料号码
    if "_product_code" in cf:
        prod_cols = [c for c in df.columns if c in ("产品物料号码", "产品物料号", "产品编码", "成品编码")]
        if prod_cols:
            raw_query = str(cf["_product_code"]).lower()
            queries = [q.strip() for q in raw_query.split(",") if q.strip()]
            matched = False
            for q in queries:
                for col in prod_cols:
                    row_val = str(row_data.get(col, "")).lower()
                    if q in row_val:
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                return False

    # 1.5 物料编码
    if "_material_code" in cf:
        code_cols = [c for c in df.columns if c in ("物料号", "物料编码", "code", "组件物料号")]
        if code_cols:
            raw_query = str(cf["_material_code"]).lower()
            queries = [q.strip() for q in raw_query.split(",") if q.strip()]
            matched = False
            for q in queries:
                for col in code_cols:
                    row_val = str(row_data.get(col, "")).lower()
                    if q in row_val:
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                return False

    # 1.6 流程订单
    if "_process_order" in cf:
        raw = str(cf["_process_order"])
        queries = [q.strip().lower() for q in raw.split(",") if q.strip()]
        if queries:
            matched = False
            for col_name in ["流程订单", "process_order"]:
                if col_name in df.columns:
                    row_val = str(row_data.get(col_name, "")).lower()
                    if any(q in row_val for q in queries):
                        matched = True
                        break
            if not matched:
                return False

    # 1.7 物料名称
    if "_material_names" in cf:
        raw = cf["_material_names"]
        if raw:
            if isinstance(raw, str):
                queries = [q.strip().lower() for q in raw.split(",") if q.strip()]
            else:
                queries = [str(q).lower() for q in raw]
            if queries:
                name_col = next((c for c in ("物料描述", "物料名称", "物料") if c in df.columns), None)
                if name_col:
                    row_name = str(row_data.get(name_col, "")).lower()
                    if not any(q in row_name for q in queries):
                        return False

    # 2. 偏差率
    if "_dev_rate_abs_ge_10" in cf:
        rate_col = next((c for c in ("偏差率(%)", "偏差率") if c in df.columns), None)
        if rate_col:
            rate_raw = row_data.get(rate_col, 0)
            try:
                rate = float(rate_raw.replace("%", "")) if isinstance(rate_raw, str) else float(rate_raw)
            except (ValueError, TypeError):
                rate = 0
            if abs(rate) < threshold:
                return False

    if "_dev_rate_range" in cf:
        rate_col = next((c for c in ("偏差率(%)", "偏差率") if c in df.columns), None)
        if rate_col:
            rate_raw = row_data.get(rate_col, 0)
            range_str = cf["_dev_rate_range"]
            try:
                rate = float(rate_raw.replace("%", "")) if isinstance(rate_raw, str) else float(rate_raw)
            except (ValueError, TypeError):
                rate = 0
            abs_rate = abs(rate)
            if range_str == "绝对值>=10%":
                ok = abs_rate >= 10
            elif range_str == ">10%":
                ok = abs_rate > 10
            elif range_str == ">20%":
                ok = abs_rate > 20
            elif range_str == ">30%":
                ok = abs_rate > 30
            elif range_str == "<-10%":
                ok = rate < -10
            elif range_str == "<-20%":
                ok = rate < -20
            elif range_str == "<-30%":
                ok = rate < -30
            else:
                ok = True
            if not ok:
                return False

    # 3. 已读 / 来源 / 隔离
    if "_read_status" in cf:
        status = cf["_read_status"]
        read_val = row_data.get("_read", 0)
        if status == "已读" and read_val != 1:
            return False
        if status == "未读" and read_val != 0:
            return False
    if "_read_source" in cf:
        want = cf["_read_source"]
        src = row_data.get("_read_source", "")
        if want == "auto" and src != "auto":
            return False
        if want == "manual" and src != "manual":
            return False
    if "_quarantined_is" in cf:
        want = cf["_quarantined_is"]
        is_quar = row_data.get("_quarantined", 0) == 1
        if want == "是" and not is_quar:
            return False
        if want == "否" and is_quar:
            return False

    # 3.5 颜色标记
    color_keys = [k for k in cf if k in (
        "_changed_only", "_quarantined_only", "_substitute_only", "_unused_only", "_alert_only", "_plain_only")]
    if color_keys:
        # 复刻 classify_row_color_keys（与生产实现同语义）
        def _tf(v):
            try:
                f = float(v)
                return f if not pd.isna(f) else 0.0
            except (ValueError, TypeError):
                return 0.0
        is_changed = row_data.get("_post_audit_changed", 0) == 1
        is_quarantined = row_data.get("_quarantined", 0) == 1
        is_substitute = (str(row_data.get("是否替代料", "")).strip() == "是") if "是否替代料" in df.columns else False
        a_val = 0.0
        q_val = 0.0
        for c in ["数量-实际", "实际"]:
            if c in df.columns:
                a_val = _tf(row_data.get(c, 0))
                break
        for c in ["数量-定额", "定额"]:
            if c in df.columns:
                q_val = _tf(row_data.get(c, 0))
                break
        no_input = (abs(a_val) <= 0.001) and (q_val > 0.001)
        is_unused = no_input and not is_substitute
        is_alert = False
        alert_rate_col = next((c for c in ["偏差率(%)", "偏差率"] if c in df.columns), None)
        if alert_rate_col:
            rv_raw = row_data.get(alert_rate_col, 0)
            try:
                rv = float(str(rv_raw).replace("%", "").strip())
            except (ValueError, TypeError):
                rv = 0.0
            if abs(rv) >= threshold and not no_input and not (is_changed or is_quarantined):
                is_alert = True
        is_plain = not (is_changed or is_quarantined or is_substitute or is_unused or is_alert)
        keys = set()
        if is_changed: keys.add("_changed_only")
        if is_quarantined: keys.add("_quarantined_only")
        if is_substitute: keys.add("_substitute_only")
        if is_unused: keys.add("_unused_only")
        if is_alert: keys.add("_alert_only")
        if is_plain: keys.add("_plain_only")
        if not any(k in keys for k in color_keys):
            return False

    # 3.6 单位（合成数据无单位列 → 原实现无约束；保持对称）
    if "_units" in cf:
        _unit_col, _units_set = cf["_units"]
        if _unit_col and _unit_col in df.columns:
            rv = str(row_data.get(_unit_col, "")).strip()
            if rv not in _units_set:
                return False

    # 4 备注为空 / 关键词 / 排除
    if "_remark_empty" in cf:
        remark_col = next((c for c in ("备注原因", "备注") if c in df.columns), None)
        if remark_col:
            remark = row_data.get(remark_col, "")
            is_empty = (pd.isna(remark) or str(remark).strip() == "")
            if cf["_remark_empty"] != is_empty:
                return False
    for key in ("_remark_search", "_remark_not"):
        if key in cf:
            raw = cf[key]
            if raw:
                if isinstance(raw, str):
                    queries = [q.strip().lower() for q in raw.split(",") if q.strip()]
                else:
                    queries = [str(q).lower() for q in raw]
                if queries:
                    remark_col = next((c for c in ("备注原因", "备注") if c in df.columns), None)
                    if remark_col:
                        row_remark = str(row_data.get(remark_col, "")).lower()
                        matched = any(q in row_remark for q in queries)
                        if key == "_remark_search" and not matched:
                            return False
                        if key == "_remark_not" and matched:
                            return False

    # 4.5 零值 / 偏差数量符号
    if "_zero_qty" in cf:
        zero_mode = cf["_zero_qty"]
        qty_col = next((c for c in ["数量-定额", "定额"] if c in df.columns), None)
        actual_col = next((c for c in ["数量-实际", "实际"] if c in df.columns), None)
        def _tf(v):
            try:
                f = float(v)
                return f if not pd.isna(f) else 0.0
            except (ValueError, TypeError):
                return 0.0
        if zero_mode == "定额为0":
            if qty_col:
                if abs(_tf(row_data.get(qty_col, 0))) > 0.001:
                    return False
            else:
                return False
        elif zero_mode == "实际为0":
            if actual_col:
                if abs(_tf(row_data.get(actual_col, 0))) > 0.001:
                    return False
            else:
                return False
        elif zero_mode == "定额/实际为0":
            qty_val = _tf(row_data.get(qty_col, 0)) if qty_col else 0.0
            actual_val = _tf(row_data.get(actual_col, 0)) if actual_col else 0.0
            if abs(qty_val) > 0.001 or abs(actual_val) > 0.001:
                return False
        elif zero_mode == "定额/实际非0":
            qty_val = _tf(row_data.get(qty_col, 0)) if qty_col else 0.0
            actual_val = _tf(row_data.get(actual_col, 0)) if actual_col else 0.0
            if abs(qty_val) <= 0.001 or abs(actual_val) <= 0.001:
                return False
    if "_dev_qty_sign" in cf and "偏差数量" in df.columns:
        sign = cf["_dev_qty_sign"]
        def _tf(v):
            try:
                f = float(v)
                return f if not pd.isna(f) else 0.0
            except (ValueError, TypeError):
                return 0.0
        dq = _tf(row_data.get("偏差数量", 0))
        if sign == "gt0" and dq <= 0.001:
            return False
        if sign == "eq0" and abs(dq) > 0.001:
            return False
        if sign == "lt0" and dq >= -0.001:
            return False

    # 4.x 半成品
    if "_semi_class_set" in cf:
        sset = cf["_semi_class_set"]
        if sset:
            semi_col = "半成品重分类"
            if semi_col in df.columns:
                row_val = str(row_data.get(semi_col, "")).strip()
                factory = str(row_data.get("工厂", "")).strip()
                matched = False
                for m in sset:
                    if m == "食品成品半成品":
                        if ((row_val == m) or row_val == "") and "食品" in factory:
                            matched = True
                    elif m == "饮料成品半成品":
                        if ((row_val == m) or row_val == "") and "饮料" in factory:
                            matched = True
                    else:
                        if row_val == m:
                            matched = True
                if not matched:
                    return False

    # 4 日期
    if "_date_start" in cf or "_date_end" in cf:
        date_col = next((c for c in ("订单日期", "订单开始日期", "日期") if c in df.columns), None)
        if date_col:
            row_date = row_data.get(date_col)
            try:
                row_date = pd.to_datetime(row_date).date()
                start = cf.get("_date_start")
                if start:
                    start_date = pd.Timestamp(start).date()
                    if row_date < start_date:
                        return False
                end = cf.get("_date_end")
                if end:
                    end_date = pd.Timestamp(end).date()
                    if row_date > end_date:
                        return False
            except Exception:
                pass
    return True


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _random_filter_dicts():
    """覆盖所有筛选键的随机组合（确定性种子）。"""
    rng = random.Random(7)
    choices = [
        {"工厂": "上海"}, {"车间": "二车间", "是否替代料": "是"},
        {"_product_code": "50001183"}, {"_material_code": "10000001"},
        {"_material_code": "10000002,10000003"}, {"_process_order": "so0001"},
        {"_material_names": "纸箱"}, {"_dev_rate_abs_ge_10": True},
        {"_dev_rate_range": ">20%"}, {"_dev_rate_range": "绝对值>=10%"},
        {"_read_status": "已读"}, {"_read_status": "未读"}, {"_read_source": "auto"},
        {"_quarantined_is": "是"}, {"_changed_only": True},
        {"_alert_only": True}, {"_plain_only": True}, {"_unused_only": True, "_alert_only": True},
        {"_remark_empty": True}, {"_remark_empty": False},
        {"_remark_search": "缺货"}, {"_remark_not": "客户"},
        {"_zero_qty": "定额为0"}, {"_zero_qty": "实际为0"},
        {"_zero_qty": "定额/实际为0"}, {"_zero_qty": "定额/实际非0"},
        {"_dev_qty_sign": "gt0"}, {"_dev_qty_sign": "eq0"}, {"_dev_qty_sign": "lt0"},
        {"_semi_class_set": {"X类"}}, {"_semi_class_set": {"食品成品半成品"}},
        {"_date_start": "2026-09-05"}, {"_date_end": "2026-09-15"},
        {"_date_start": "2026-09-10", "_date_end": "2026-09-12"},
        {},
        # 组合
        {"工厂": "上海", "_material_code": "10000001", "_read_status": "未读"},
        {"_zero_qty": "实际为0", "_dev_qty_sign": "eq0", "_semi_class_set": {"饮料成品半成品"}},
    ]
    for _ in range(30):
        d = {}
        for c in choices:
            if rng.random() < 0.25:
                d.update(c)
        yield d
    yield from choices


def test_plan_matches_reference_impl(qapp):
    """新 plan 实现 × 旧逐行参照实现：全部随机筛选组合、逐行结果必须完全一致。"""
    df = _make_df(200)
    sm = DataFrameModel()
    sm.setDataFrame(df)
    proxy = AuditProxyModel()
    proxy.setSourceModel(sm)

    for cf in _random_filter_dicts():
        proxy.setCustomFilters(dict(cf))
        for row in range(len(df)):
            new_ok = proxy.filterAcceptsRow(row, None)
            ref_ok = ref_accepts(row, df, dict(cf))
            if new_ok != ref_ok:
                pytest.fail(
                    f"不一致: filters={cf} row={row} new={new_ok} ref={ref_ok}\n"
                    f"row_values={dict(df.iloc[row])}"
                )


def test_plan_invalidated_on_source_reset(qapp):
    """源数据整表重置后，旧计划必须失效并按新数据重算（行数变化场景）。"""
    sm = DataFrameModel()
    sm.setDataFrame(_make_df(100))
    proxy = AuditProxyModel()
    proxy.setSourceModel(sm)
    proxy.setCustomFilters({"_material_code": "10000001"})
    old_plan = proxy._plan
    assert old_plan is not None and old_plan.get("n") == 100
    # 合法的 begin/换数据/end 序列（与 setDataFrame 内部同构）：
    # beginReset 发 modelAboutToBeReset → 计划失效；endReset 发 modelReset → 基类重筛 → 惰性重建
    new_df = _make_df(200)
    sm.beginResetModel()
    assert proxy._plan_stale
    sm._data = new_df
    sm.endResetModel()
    # 重建是惰性的：下一次 filterAcceptsRow（新筛选 pass 的第一行）按新数据重建计划
    for row in range(len(new_df)):
        assert proxy.filterAcceptsRow(row, None) == ref_accepts(row, new_df, {"_material_code": "10000001"})
    assert proxy._plan.get("n") == 200  # 已按新数据重建


def test_set_custom_filters_same_dict_skips_refilter(qapp):
    """同一筛选字典重复下发：不应重复 invalidateFilter（面板信号抖动防护）。"""
    sm = DataFrameModel()
    sm.setDataFrame(_make_df(50))
    proxy = AuditProxyModel()
    proxy.setSourceModel(sm)
    cf = {"_material_code": "10000001"}
    proxy.setCustomFilters(cf)
    invalidated = []
    orig = proxy.invalidateFilter
    proxy.invalidateFilter = lambda: invalidated.append(1) or orig()
    proxy.setCustomFilters(dict(cf))  # 同一内容 → 跳过
    assert invalidated == []
    proxy.setCustomFilters({"_material_code": "10000002"})  # 不同 → 重筛
    assert invalidated == [1]


def test_clear_header_filters_keeps_custom(qapp):
    """clearHeaderFilters：清列头取值过滤但保留 _custom_filters（重置路径省一遍重筛）。"""
    sm = DataFrameModel()
    sm.setDataFrame(_make_df(50))
    proxy = AuditProxyModel()
    proxy.setSourceModel(sm)
    proxy.setCustomFilters({"_read_status": "未读"})
    proxy.setValueFilter("工厂", {"上海"})
    assert proxy._value_filters
    proxy.clearHeaderFilters()
    assert not proxy._value_filters and not proxy._value_keys
    assert proxy._custom_filters == {"_read_status": "未读"}
