# -*- coding: utf-8 -*-
"""驾驶舱升级断言（规格 §3）：Top5车间/Top10物料表存在且排序正确、绿页签。"""
import os
import sys
from openpyxl import Workbook

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from analysis.excel_builder.post_process import _upgrade_dashboard


def _mk_wb():
    wb = Workbook()
    ws = wb.active
    ws.title = "汇总统计"
    ws.append(["序号", "工厂", "车间", "物料分类", "总条数", "总偏差金额(含税)", "备注覆盖率"])
    for i, (wsname, amt) in enumerate([("A线", -500.0), ("B线", 300.0), ("C线", -1200.0),
                                       ("D线", 50.0), ("E线", -70.0), ("F线", 900.0)]):
        ws.append([i + 1, "食品厂", wsname, "包材", 10, amt, 0.5])
    ws2 = wb.create_sheet("完整偏差明细")
    ws2.append(["物料编码", "物料名称", "偏差金额"])
    for j in range(12):
        ws2.append([f"M{j:03d}", f"物料{j}", -(j + 1) * 100.0])
    # _upgrade_dashboard 对不存在页短路；测试先建空页模拟「已建页后升级」
    wb.create_sheet("📊 驾驶舱")
    return wb


def test_upgrade_dashboard_tables():
    wb = _mk_wb()
    _upgrade_dashboard(wb)
    dash = wb["📊 驾驶舱"]
    text = [str(c.value) for row in dash.iter_rows() for c in row if c.value]
    assert any("Top 5 车间" in t for t in text), "缺 Top5 车间表"
    assert any("Top 10 物料" in t for t in text), "缺 Top10 物料表"
    # C线(-1200) 应排在 F线(900) 之前（按 |金额| 降序）
    vals = [c.value for row in dash.iter_rows() for c in row]
    assert vals.index("C线") < vals.index("F线")
    assert dash.sheet_properties.tabColor is not None


def test_upgrade_dashboard_idempotent():
    """重复调用不叠加（幂等：先清 16 行以下再重写）。"""
    wb = _mk_wb()
    _upgrade_dashboard(wb)
    dash = wb["📊 驾驶舱"]
    n1 = sum(1 for row in dash.iter_rows() for c in row if c.value == "Top 5 车间（按 |偏差金额| 降序）")
    _upgrade_dashboard(wb)
    n2 = sum(1 for row in dash.iter_rows() for c in row if c.value == "Top 5 车间（按 |偏差金额| 降序）")
    assert n1 == 1 and n2 == 1, (n1, n2)
