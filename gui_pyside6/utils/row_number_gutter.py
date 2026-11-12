# -*- coding: utf-8 -*-
"""看板最左行号栏 —— v43.366「看板里能不能显示序号」

裴哥要的是「这一屏第几行」：筛完从 1 重排、点列头排序后也还是 1、2、3 连着，
方便口头定位（「看板第 7 行那条」）。原先只有隔离区试过把「序号」做成一个**数据列**，
那条路有两个坑，所以这次不这么走：

① 会被排序打乱。看板排序走 ``DataFrameModel.sort()``（整块 DataFrame 就地重排），
   数据列「序号」跟着数值一起跑，排完序 1 号可能跑到第 40 行；
② 挤在首列里只有 20 多 px，三位数就省略号，等于没有。

改用最左那条**垂直表头**（Qt 的行号道）：它本来就是给行号留的，主表的「勾选道 +
行号」是同一块地方，只是这里不需要勾选框。文本由模型给（``DataFrameModel.headerData``
垂直分支返回 ``section + 1``），道宽和样式在这里统一收口。

⚠️ 一个容易踩的点：垂直表头的 ``setDefaultSectionSize()`` 管的是**行高**，不是道宽
   （各看板本来就靠它设 28/36 的行高，一个都不要动）。道宽只能走 ``setFixedWidth``。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

from gui_pyside6.themes.tokens import SIZE_PX


def enable_row_numbers(view, width=None):
    """点亮视图最左边的行号栏，返回该垂直表头（便于链式/断言）。

    幂等：重复调用只会把同一组属性再设一遍，可安全放在每次重建模型的地方。
    """
    vh = view.verticalHeader()
    vh.setVisible(True)
    vh.setFixedWidth(SIZE_PX["rowNumberLane"] if width is None else width)
    # 数字右对齐：个/十/百位上下成列，比居中好扫读
    vh.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
    vh.setSectionResizeMode(QHeaderView.Fixed)
    # 点行号不给整节区刷蓝色高亮——行号是刻度，不是按钮
    vh.setHighlightSections(False)
    return vh
