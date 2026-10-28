# -*- coding: utf-8 -*-
"""驾驶舱升级断言（规格 §3 + v43.284 按工厂分块）：
食品/饮料各自 Top5车间/Top10物料、排序正确、双线周趋势、绿页签。"""
import os
import sys
from openpyxl import Workbook

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from analysis.excel_builder.post_process import _upgrade_dashboard


def _mk_wb():
    """明细含 工厂/车间/物料/金额/备注/日期，两厂各 3 车间若干行。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "汇总统计"
    ws.append(["序号", "工厂", "车间", "物料分类", "总条数", "总偏差金额(含税)", "备注覆盖率"])
    ws.append([1, "1101", "A线", "包材", 10, -500.0, 0.5])
    ws2 = wb.create_sheet("完整偏差明细")
    ws2.append(["订单日期", "工厂", "车间", "物料编码", "物料名称", "偏差金额", "备注"])
    # 食品厂：湿法一线 -1200（最痛）、灌装线 900、辅材 -500
    # 饮料厂：无菌线 -800、热灌线 600、PET -100
    data = [
        ("2026-10-05", "云南达利-食品厂", "24000无菌湿法线-1线", "M001", "芝士酱", -1200.0, ""),
        ("2026-10-06", "云南达利-食品厂", "24000无菌湿法线-1线", "M002", "香精", -300.0, "已填"),
        ("2026-10-08", "云南达利-食品厂", "灌装线", "M003", "瓶盖", 900.0, ""),
        ("2026-10-09", "云南达利-食品厂", "辅材组", "M004", "胶带", -500.0, "已填"),
        ("2026-10-12", "云南达利-饮料厂", "无菌冷灌装线", "M005", "PET粒子", -800.0, ""),
        ("2026-10-15", "云南达利-饮料厂", "热灌装线", "M006", "白糖", 600.0, "已填"),
        ("2026-10-19", "云南达利-饮料厂", "PET胚组", "M007", "胚管", -100.0, ""),
    ]
    for row in data:
        ws2.append(list(row))
    # 周趋势第二周（W42）食品再来一笔，验证周次聚合
    ws2.append(["2026-10-15", "云南达利-食品厂", "灌装线", "M003", "瓶盖", -200.0, ""])
    # _upgrade_dashboard 对不存在页短路；测试先建空页模拟「已建页后升级」
    wb.create_sheet("📊 驾驶舱")
    return wb


def _texts(ws):
    return [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]


def test_per_factory_blocks():
    wb = _mk_wb()
    _upgrade_dashboard(wb)
    dash = wb["📊 驾驶舱"]
    text = _texts(dash)
    assert any(t.startswith("食品厂 · Top 5 车间") for t in text), "缺食品厂车间块"
    assert any(t.startswith("饮料厂 · Top 5 车间") for t in text), "缺饮料厂车间块"
    assert any(t.startswith("食品厂 · Top 10 物料") for t in text), "缺食品厂物料块"
    assert any(t.startswith("饮料厂 · Top 10 物料") for t in text), "缺饮料厂物料块"
    assert dash.sheet_properties.tabColor is not None


def test_within_factory_ordering():
    """各厂块内按 |金额| 降序：食品=湿法线(-1200)先于辅材(-500)先于灌装(900-200=700?)。
    食品灌装线合计 900-200=700 → |700|<|1200| 但 >|500| → 序=湿法,灌装,辅材。"""
    wb = _mk_wb()
    _upgrade_dashboard(wb)
    vals = [c.value for row in wb["📊 驾驶舱"].iter_rows() for c in row]
    assert vals.index("24000无菌湿法线-1线") < vals.index("灌装线") < vals.index("辅材组")
    # 饮料：无菌线(-800) 先于 热灌线(600) 先于 PET(-100)
    assert vals.index("无菌冷灌装线") < vals.index("热灌装线") < vals.index("PET胚组")
    # 车间不跨厂混排：食品块内不出现饮料车间（顺序上饮料车间在食品三车间之后）
    assert vals.index("PET胚组") > vals.index("辅材组")


def test_weekly_chart_two_series():
    """双线周趋势图存在（食品/饮料两系列），数据源=明细订单日期。"""
    wb = _mk_wb()
    _upgrade_dashboard(wb)
    dash = wb["📊 驾驶舱"]
    line = [c for c in dash._charts if type(c).__name__ == "LineChart"]
    assert len(line) == 1, "缺周趋势线图（原从趋势页取金额列失败的老 bug 应已修）"
    assert len(line[0].series) == 2, "应为食品/饮料两条线"
    text = _texts(dash)
    assert any(t.startswith("2026-W") for t in text), "缺周次数据列"


def test_upgrade_dashboard_idempotent():
    """重复调用不叠加（幂等：固定区域先清后写）。"""
    wb = _mk_wb()
    _upgrade_dashboard(wb)
    _upgrade_dashboard(wb)
    n = sum(1 for t in _texts(wb["📊 驾驶舱"]) if t.startswith("食品厂 · Top 5 车间"))
    assert n == 1, n


def test_fallback_no_factory_column():
    """明细无工厂列 → 退回单块「全厂」，不崩溃。"""
    wb = Workbook()
    ws2 = wb.create_sheet("完整偏差明细")
    ws2.append(["订单日期", "车间", "物料编码", "物料名称", "偏差金额", "备注"])
    ws2.append(["2026-10-05", "A线", "M1", "料1", -100.0, ""])
    wb.create_sheet("📊 驾驶舱")
    _upgrade_dashboard(wb)
    text = _texts(wb["📊 驾驶舱"])
    assert any(t.startswith("全厂 · Top 5 车间") for t in text)
