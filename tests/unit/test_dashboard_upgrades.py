# -*- coding: utf-8 -*-
"""管理看板 A+B+C+D 回归：图表翻新、结论置顶、分组折叠、到主表芯片与桥。"""
import os
import re
import sys
from urllib.parse import quote

import pytest
from pytest import MonkeyPatch
import shutil

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


def _synthetic_dev(n=300, seed=11):
    """合成 dev_df（含 12 图所需全部列，数值确定性）。"""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "工厂": ["云南达利-食品厂"] * n,
        "订单日期": pd.to_datetime("2026-08-01") + pd.to_timedelta(rng.integers(0, 60, n), unit="D"),
        "车间": [f"车间{i % 5 + 1}" for i in range(n)],
        "物料类型": rng.choice(["原料", "包材", "辅料"], n),
        "物料名称": [f"物料{chr(65 + i % 12)}" for i in range(n)],
        "产品物料描述": [f"成品线{i % 4}" for i in range(n)],
        "数量-定额": rng.uniform(100, 3000, n).round(1),
        "偏差数量": rng.normal(0, 200, n).round(1),
        "偏差金额": np.where(np.arange(n) % 5 == 0, 9000.0, rng.normal(0, 800, n)).round(2),
        "偏差率(%)": rng.normal(0, 8, n).round(2),
        "是否替代料": rng.choice(["是", "否"], n, p=[0.2, 0.8]),
        "净偏差金额": rng.normal(0, 500, n).round(2),
        "备注": rng.choice(["", "损耗", "短缺"], n, p=[0.4, 0.4, 0.2]),
    })
    df["偏差区间"] = np.where(df["偏差金额"] > 0, "正偏差", np.where(df["偏差金额"] < 0, "负偏差", "持平"))
    return df


def _build_html():
    import matplotlib
    matplotlib.use("Agg", force=True)
    import analysis.dashboard_html as dh
    df = _synthetic_dev()
    blocks = {"云南达利-食品厂": (dh.compute_metrics(df), df)}
    meta = {"start": "2026-08-01", "end": "2026-09-30", "src": "test", "gen": "now"}
    return dh.build_html(blocks, meta), df


def test_details_folding_key_risk_open():
    """C：4 组 details 折叠，仅「重点风险」默认展开。"""
    html, _ = _build_html()
    assert html.count("<details class=\"group\"") == 4
    assert "<details class=\"group\" open><summary class=\"grp\">重点风险" in html
    for grp in ("偏差规模与分布", "结构拆解", "趋势与归因"):
        assert f'<details class="group"><summary class="grp">{grp}' in html, grp


def test_conclusion_first_and_cards():
    """B：小结置顶（在任意图表组之前）；指标卡含净偏差/平均偏差率。"""
    html, _ = _build_html()
    i_summary = html.index('class="summary-card top"')
    i_first_group = html.index("<details")
    assert i_summary < i_first_group, "小结卡应置顶于图表组之前"
    for kw in ("净偏差金额", "平均偏差率", "重点盯什么"):
        assert kw in html, "指标卡/小结缺 %s" % kw


def test_chips_carry_expected_targets():
    """D-HTML：芯片值 = 数据算出的最严重车间 / 最大物料。"""
    html, df = _build_html()
    worst = df.groupby("车间")["偏差金额"].sum()
    worst = worst.reindex(worst.abs().sort_values(ascending=False).index).index[0]
    pat = re.compile(r'href="zpp011:link\?type=worst_workshop&v=([^"&]+)')
    vals = set(pat.findall(html))
    assert quote(str(worst)) in vals, "芯片车间值应为 %r, 实际 %s" % (worst, vals)
    assert "zpp011:link?type=top_material" in html
    assert "zpp011:link?type=top_product" in html
    # 无链接类型的卡（如每日趋势）不挂芯片
    trend_cell = html[html.index("每日偏差金额趋势"):][:600]
    assert "zpp011:link" not in trend_cell


def test_link_values_safe_on_missing_cols():
    """_link_values 缺列/空数据不崩（真实文件可能缺 物料名称 等）。"""
    import analysis.dashboard_html as dh

    df = pd.DataFrame({"订单日期": ["2026-08-01"], "偏差金额": [1.0], "备注": [""]})
    out = dh._link_values(df)
    assert isinstance(out, dict)
    assert dh._link_values(pd.DataFrame()) == {}


@pytest.fixture(scope="module")
def main_window(qapp, tmp_path_factory):
    """离屏构造真实 MainWindow，副作用全部指向临时目录（同 test_toolbar_reorg）。"""
    import core.read_status as rs
    import gui_pyside6.main_window as mw
    from core.alert_monitor import AlertMonitor
    from core.config_manager import ConfigManager as _CM

    db_tmp = tmp_path_factory.mktemp("audit_db_preset")
    real_db = rs.DB_PATH
    if os.path.exists(real_db):
        shutil.copy2(real_db, str(db_tmp / "audit.db"))
    rs.DB_PATH = str(db_tmp / "audit.db")

    cfg_tmp = tmp_path_factory.mktemp("cfg_preset") / "cm.json"

    def _mk_cm(*a, **k):
        return _CM(config_path=cfg_tmp)

    mp = MonkeyPatch()
    mw.MainWindow._seed_monitor_baseline = lambda self: None
    mw.MainWindow._scan_monitor_dir = lambda self, *a, **k: None
    AlertMonitor.start = lambda self: None
    AlertMonitor.stop = lambda self, *a, **k: None
    mp.setattr(mw, "ConfigManager", _mk_cm)

    w = mw.MainWindow()
    w.show()
    yield w
    rs.DB_PATH = real_db
    mp.undo()


def test_board_focus_applies_filters(main_window):
    """D-Qt：zpp011 URL → 主表叠加车间/工厂筛选 + 联动横幅；清除可还原。"""
    from gui_pyside6.models.data_frame_model import AuditProxyModel

    w = main_window
    proxy = AuditProxyModel()
    w.proxy_model = proxy
    w._link_snapshot = None

    url = "zpp011://link?type=worst_workshop&v=%s&fac=%s" % (quote("车间4"), quote("食品厂"))
    w._apply_board_focus(url)
    cf = proxy.getCustomFilters()
    assert cf.get("车间") == "车间4" and cf.get("工厂") == "食品厂"
    assert w.main_table.link_banner.isVisible()
    assert "管理看板" in w.main_table.link_banner_label.text()

    # 物料型芯片走 _material_names（模糊匹配）
    w._clear_link_drilldown()
    url2 = "zpp011://link?type=top_material&v=%s&fac=" % quote("不锈钢桶")
    w._apply_board_focus(url2)
    assert proxy.getCustomFilters().get("_material_names") == "不锈钢桶"
    assert "工厂" not in proxy.getCustomFilters(), "fac 为空时不应加工厂筛选"

    # 未知 type / 空 URL：安全忽略
    w._clear_link_drilldown()
    w._apply_board_focus("zpp011://link?type=nope&v=x")
    w._apply_board_focus("")
    assert not w.main_table.link_banner.isVisible()
