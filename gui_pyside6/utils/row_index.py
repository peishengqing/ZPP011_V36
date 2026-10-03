# -*- coding: utf-8 -*-
"""看板表格「序号」列（v43.132 新增）。

背景
----
各看板此前都没有行号列，审核时想回头指认「刚才那条是哪一条」只能靠
数行位置或横向滚动找「原表行号」，很慢。裴哥要求看板加序号。

为什么放在共用工具里
------------------
四个看板（替代料/偏差率预警/负损/变动提醒）都需要它，且都是
「拿到筛选后的 df → 交给自有 DataFrameModel 显示」这一种形态，
重复四遍会漂移成四份实现。放 utils 供统一调用。

为什么不改 DataFrameModel
----------------------
主表与看板共用 DataFrameModel，若在模型里统一加序号，
主表也会多出一列 —— 那会改变主表的 `_display_columns`、
影响列头筛选浮层的列名映射与 Excel 导出（index=False 不会去掉它）。
所以序号只在「看板自己的 df」上产生，不进主表。

⚠️ 已知的取舍（裴哥确认要「真加一列」）
------------------------------------
* 列头筛选浮层里会多出一个可筛选的「序号」项；
* 各看板右键「导出」走 ``df.to_excel(..., index=False)``，
  导出的 Excel 里会**多带一列序号** —— 这是要真列的必然结果。
"""
import pandas as pd

# 序号列名（用中文，便于在列头筛选里辨认）
SEQ_COL = '序号'


def with_row_index(df, col_name: str = SEQ_COL, start: int = 1):
    """在 DataFrame 最左侧插入 1,2,3… 序号列。

    参数
    ----
    df       : 待显示的 DataFrame
    col_name : 序号列名，默认「序号」
    start    : 起始值，默认 1

    返回
    ----
    新的 DataFrame（原 df 不被修改）；若 df 为空则原样返回空表，
    但仍补上带序号的空列，避免「空结果时列结构缺失」导致的下游 KeyError。

    说明
    ----
    * 用 ``insert(0, ...)`` 放最左，保证看板第一眼就能看到行号。
    * 序号是**当前视图下的行号**：看板重新筛选后序号会重排。
      这是有意的——行号应当对应「你现在看到的第几行」，
      否则筛选后会指向不存在的行，反而更容易看错。
    * 不使用 ``df.reset_index()`` 复用原索引：原索引来自源 Excel 的行位置，
      在筛选后是稀疏的大数（可能 3、17、482…），当序号没有意义。
    """
    if df is None:
        return df
    if col_name in df.columns:
        # 已有序号列则覆盖重排，避免重复添加
        df = df.drop(columns=[col_name])
    if df.empty:
        out = df.copy()
        out.insert(0, col_name, pd.Series([], dtype='int64'))
        return out
    out = df.copy()
    out.insert(0, col_name, pd.Series(range(start, start + len(out)), index=out.index))
    return out
