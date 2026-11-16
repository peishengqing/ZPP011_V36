# -*- coding: utf-8 -*-
"""未读概览弹窗第 5 行「翻箱守恒异常」取数函数测试（v43.381）。

钉死三件事：
1. 口径同源：flip_anomaly_stats 判「疑似漏记」必须与翻箱守恒看板一致
   （复用 analysis_extra_flip._check_order / check_drink_order）；
2. 「未读」语义：异常单在主表还有 _read==0 的组件行才算未读，
   全部标已读后未读数归零（弹窗才能全清零自动关闭）；
3. 兜底：缺列 / 空表 / 无 ZPFX 一律返回 (0, 0)，绝不抛异常连累弹窗刷新。
"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.controllers.dashboard_controller import (  # noqa: E402
    flip_anomaly_stats,
)


def _row(order, fac, mtype, mname, actual, pdesc, yield_qty,
         order_type="ZPFX", unit="件", note="", read=0):
    """构造一行翻箱组件记录（列结构与主表 dev_df 对齐）。"""
    return {
        "订单类型": order_type, "流程订单": order, "工厂名称": fac,
        "产品物料描述": pdesc, "产量": yield_qty,
        "组件物料类型": mtype, "物料名称": mname, "单位": unit,
        "实际": actual, "备注": note, "_read": read,
    }


def _food_anomaly(order="F001", read=0):
    """食品疑似漏记：产出 10×1KG=10KG，投入 Z007 4×1KG=4KG，差 6KG>0。"""
    return _row(order, "云南达利-食品厂", "Z007", "500gx2包", 4,
                "500gx2包", 10, read=read)


def _food_normal(order="F002", read=1):
    """食品守恒/正常：产出 4×1KG=4KG，投入 4×1KG=4KG，差 0。"""
    return _row(order, "云南达利-食品厂", "Z007", "500gx2包", 4,
                "500gx2包", 4, read=read)


def _drink_anomaly(order="D001", read=0):
    """饮料疑似漏记：产出 10×24=240 容器，投入 2×24=48 容器，差 192>0。"""
    return _row(order, "云南达利-饮料厂", "Z008", "250mlx24瓶", 2,
                "250mlx24瓶", 10, read=read)


def _df(rows):
    return pd.DataFrame(rows)


def test_food_and_drink_anomaly_counted():
    """食+饮各一单疑似漏记；守恒单与待人工确认单不计入。"""
    rows = [
        _food_anomaly(),          # 疑似漏记，未读
        _food_normal(),           # 守恒/正常 → 不计
        _drink_anomaly(),         # 疑似漏记，未读
        # 待人工确认（产出规格解析不出）→ 不计
        _row("F003", "云南达利-食品厂", "Z007", "500gx2包", 4,
             "规格不明产品", 10),
        # 非 ZPFX 行 → 直接无视
        _row("F004", "云南达利-食品厂", "Z007", "500gx2包", 0,
             "500gx2包", 10, order_type="ZPPO"),
    ]
    unread, total = flip_anomaly_stats(_df(rows))
    assert total == 2, "只有食/饮各 1 单疑似漏记"
    assert unread == 2, "两条异常单都未读"


def test_unread_follows_read_status():
    """异常单全部组件行标已读后，unread 归零但 total 不变。"""
    rows = [_food_anomaly(read=1), _drink_anomaly(read=1)]
    unread, total = flip_anomaly_stats(_df(rows))
    assert total == 2
    assert unread == 0, "全部组件行已读 → 未读异常单数应为 0"


def test_partial_read_still_counts_unread():
    """异常单只有部分组件行被标读，仍算未读（还有没核对过的行）。"""
    rows = [
        _food_anomaly(read=1),
        # 同单第二行仍未读
        _row("F001", "云南达利-食品厂", "Z002", "白内袋", 10,
             "500gx2包", 10, unit="个", read=0),
    ]
    unread, total = flip_anomaly_stats(_df(rows))
    assert total == 1
    assert unread == 1


def test_missing_read_column_treats_all_unread():
    """主表没有 _read 列时，异常单全部按未读算（保守不漏报）。"""
    rows = [_food_anomaly(), _drink_anomaly()]
    df = _df(rows).drop(columns=["_read"])
    unread, total = flip_anomaly_stats(df)
    assert (unread, total) == (2, 2)


def test_missing_required_column_returns_zero():
    """缺守恒必要列（如「产量」）→ (0, 0)，不抛异常。"""
    df = _df([_food_anomaly()]).drop(columns=["产量"])
    assert flip_anomaly_stats(df) == (0, 0)


def test_empty_and_non_zpfx_returns_zero():
    """空表 / 全是非翻箱单 → (0, 0)。"""
    assert flip_anomaly_stats(pd.DataFrame()) == (0, 0)
    assert flip_anomaly_stats(None) == (0, 0)
    rows = [_row("F001", "云南达利-食品厂", "Z007", "500gx2包", 4,
                 "500gx2包", 10, order_type="ZPPO")]
    assert flip_anomaly_stats(_df(rows)) == (0, 0)
