# -*- coding: utf-8 -*-
"""看板最左行号栏回归（v43.366「看板里能不能显示序号」）。

裴哥要的是「这一屏第几行」：筛完从 1 重排、点列头排序后也还是 1、2、3 连着。
原先只有隔离区把「序号」做成一个数据列，而看板排序走 ``DataFrameModel.sort()``
（整块 DataFrame 就地重排），数据列会跟着数值一起跑，排完序 1 号能跑到第 40 行；
且挤在首列只有 20 多 px，三位数就打省略号。现在统一改用 Qt 的垂直表头行号道。

三处真源分别钉住：
① ``DataFrameModel.headerData`` 的垂直分支返回 ``section + 1``（视图序号）；
② ``utils/row_number_gutter.enable_row_numbers`` 把道点亮成 44px 右对齐；
③ 各看板确实调了它（源文件层面逐个点名，防止「加了 helper 没人接」）。
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QTableView  # noqa: E402

from gui_pyside6.models.data_frame_model import DataFrameModel  # noqa: E402
from gui_pyside6.themes.tokens import SIZE_PX  # noqa: E402
from gui_pyside6.utils.row_number_gutter import enable_row_numbers  # noqa: E402


def _model():
    """行标签故意打乱（7/3/90）：老写法会把这三个数当行号显示出来。"""
    df = pd.DataFrame(
        {"物料编码": ["A", "B", "C"], "偏差率(%)": [1.0, 9.0, 5.0]},
        index=[7, 3, 90])
    m = DataFrameModel()
    m.setDataFrame(df)
    return m


def _labels(m):
    return [str(m.headerData(r, Qt.Vertical, Qt.DisplayRole)) for r in range(m.rowCount())]


# ---------- 1. 模型侧：行号 = 视图序号 ----------

def test_labels_are_view_order_not_df_index():
    assert _labels(_model()) == ["1", "2", "3"]


def test_labels_stay_sequential_after_sort():
    """点列头排序后仍然 1、2、3 连着——这条正是「序号做成数据列」办不到的。"""
    m = _model()
    # setDataFrame 会把 _read/_read_source 挪到最前两列，列号要按真名列取
    rate_col = list(m.getDataFrame().columns).index("偏差率(%)")
    m.sort(rate_col, Qt.DescendingOrder)
    assert _labels(m) == ["1", "2", "3"]
    # 反证：排序真的生效了（否则这条测试是空的）
    assert m.getDataFrame()["物料编码"].tolist() == ["B", "C", "A"]


# ---------- 2. 视图侧：道点亮 ----------

def test_enable_row_numbers_shows_and_sizes_lane(qapp):
    view = QTableView()
    view.setModel(_model())
    vh = enable_row_numbers(view)
    # 父窗口未 show 时 isVisible() 恒为 False，只能断言「没被主动隐藏」
    assert not vh.isHidden()
    assert vh.width() == SIZE_PX["rowNumberLane"]
    assert vh.defaultAlignment() & Qt.AlignRight
    assert vh.highlightSections() is False


def test_enable_row_numbers_is_idempotent(qapp):
    view = QTableView()
    view.setModel(_model())
    enable_row_numbers(view)
    enable_row_numbers(view)
    assert view.verticalHeader().width() == SIZE_PX["rowNumberLane"]


def test_gutter_never_touches_row_height(qapp):
    """垂直表头的 defaultSectionSize 是行高，helper 一个字节都不该动它。"""
    view = QTableView()
    view.verticalHeader().setDefaultSectionSize(36)
    enable_row_numbers(view)
    assert view.verticalHeader().defaultSectionSize() == 36


# ---------- 3. 接线：九块看板都要有点名 ----------

_WIRED = {
    "gui_pyside6/dialogs/alert_dialog.py": "table_view",
    "gui_pyside6/dialogs/deviation_warning_dialog.py": "table_view",
    "gui_pyside6/dialogs/quarantine_dialog.py": "table_view",
    "gui_pyside6/dialogs/flip_check_dashboard_dialog.py": "_make_table",
    "gui_pyside6/dialogs/data_stability_dialog.py": "_tbl_freq",
    "gui_pyside6/dialogs/alt_chain_dialog.py": "_tbl",
    "gui_pyside6/widgets/neg_loss_content.py": "table_view",
    "gui_pyside6/widgets/pos_loss_content.py": "table_view",
    "gui_pyside6/widgets/semi_content.py": "table_view",
    "gui_pyside6/components/dashboard_shell.py": "table_view",
}


@pytest.mark.parametrize("rel", sorted(_WIRED))
def test_board_files_call_the_helper(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        src = f.read()
    assert "enable_row_numbers(" in src, f"{rel} 没接行号栏"
    assert "verticalHeader().setVisible(False)" not in src, (
        f"{rel} 还把垂直表头关掉，行号栏点了也看不见")


def test_quarantine_no_longer_injects_serial_column():
    """「序号」数据列删掉：它会被排序打乱，且和行号栏重复。"""
    rel = "gui_pyside6/dialogs/quarantine_dialog.py"
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        src = f.read()
    assert "df.insert(0, '序号'" not in src


def test_quarantine_hides_its_duplicate_text_columns(qapp):
    """「两个已读来源」的真根因与修法。

    真根因不在 pandas：DataFrameModel 自己就把第0列渲染成已读图标（读 _read）、第1列
    渲染成「手动/自动」（读 _read_source），表头文字也是它硬写的「状态 / 已读来源」；
    而 setDataFrame 会把这两列挪到最前，所以隔离区另加的那对文本列既重复、又会因为
    「按输入 df 的列号去隐藏」而错位。修法 = 隐藏列号改按模型列序算 + 把那两列藏掉。
    """
    rel = "gui_pyside6/dialogs/quarantine_dialog.py"
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        src = f.read()
    assert "_VIEW_DUP_COLS = ['状态', '已读来源']" in src
    seg = src[src.index("def _render_table"):src.index("def _load_expired_from_main")]
    assert "model_df = self.source_model.getDataFrame()" in seg, (
        "隐藏列号必须取自模型（setDataFrame 会把 _read/_read_source 提到最前）")
    assert "for col in _HIDDEN_INTERNAL + _VIEW_DUP_COLS" in seg


def test_model_moves_internal_read_cols_to_front():
    """上条测试的前提：setDataFrame 会把 _read/_read_source 挪到第 0/1 列，
    列序与传进来的 df 不再一致——所以任何按输入 df 取的列号都会错位。"""
    df = pd.DataFrame({"data_id": ["D1", "D2"], "_read": [0, 1], "备注": ["a", "b"]})
    m = DataFrameModel()
    m.setDataFrame(df)
    cols = list(m.getDataFrame().columns)
    assert cols[:2] == ["_read", "_read_source"]
    assert m.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "已读来源"


def test_dashboard_qss_and_app_qss_carry_the_lane_rule():
    """行号栏样式：外壳级 dashboard QSS（看板实际生效的那份）与 app QSS 都要有。"""
    from gui_pyside6.themes.tokens import build_board_qss, build_dashboard_qss
    for theme in ("light", "dark"):
        for text in (build_dashboard_qss(theme), build_board_qss(theme),
                     open(os.path.join(ROOT, "gui_pyside6/%s_theme.qss" % theme),
                          encoding="utf-8").read()):
            assert "section:vertical" in text, f"{theme} 缺行号栏样式"
