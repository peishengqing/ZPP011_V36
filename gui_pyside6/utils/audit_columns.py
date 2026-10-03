# -*- coding: utf-8 -*-
"""审核相关列名与取值的单一事实来源。

背景（2026-10-03修复）：
`gui_pyside6/services/data_service.py:68-77` 在预处理阶段会把英文列统一重命名为
`审核结果`（两列都存在时删中文列、英文列改名；只有英文列时直接改名）。因此主表
实际只有 `审核结果` 一列，而历史上三处代码按 `['审核状态','audit_status']` 查找，
恒为 None →「批量改状态」一点就弹「未找到状态列」。

概念区分（重要，不要把两者合并）：
- `审核状态` / `audit_status`：**工作流二值状态**，取值 `未审核` / `已审核`。
  该列仅由 `core/auto_closer.py:44-45` 创建（自动结案流程），正常从 Excel 加载
  主表时并不存在。
- `审核结果` / `audit_result`：**业务判定结论**，取值 `合格` / `需关注` /
  `需改进` / `需补备注`（`gui_pyside6/models/workers.py:174-190` 写入），
  另有`自动结案`（`core/auto_closer.py:88-89` 写入）。这才是主表可见、可筛选的列。

`core/auto_closer.py:86-89` 同一行同时写两列且值不同
（`审核状态='已审核'` / `审核结果='自动结案'`），可见二者语义独立。
本模块据此提供「按优先级取第一个真实存在的列」的工具，而不是把两个概念合并。
"""

# 审核结论列（业务判定）。放在最前：它是主表实际存在、且用户可见/可筛选的那一列，
# 保证批量改的就是用户在主表里能筛出来的值。
RESULT_COL_CANDIDATES = ['审核结果', 'audit_result']

# 工作流状态列（仅自动结案后存在）
STATUS_COL_CANDIDATES = ['审核状态', 'audit_status']

# 统一候选顺序：结论列优先，状态列次之
AUDIT_COL_CANDIDATES = RESULT_COL_CANDIDATES + STATUS_COL_CANDIDATES

# `审核结果` 的合法取值。
# 必须与 workers.py:174-190 实际写入的值、filter_panel.py:224 的筛选值保持一致，
# 否则用户批量改完的值在主表筛不出来（这正是修复前的症状）。
# 未审核态用空串表示（见 workers.py:147-149 建列时填空），故不在此列表中。
AUDIT_RESULT_VALUES = ['合格', '需关注', '需改进', '需补备注']

# `审核状态` 的合法取值（工作流二值态，与上面的结论词表是两回事）
AUDIT_STATUS_VALUES = ['未审核', '已审核']

# `auto_closer.py:88-89` 会写入的自动结案结论。批量改状态时提供该值，
# 避免用户覆盖掉自动结案的痕迹；因主表筛选器尚未提供该值，故不并入
# AUDIT_RESULT_VALUES（否则筛选器会新增一个没有历史数据支撑的筛选项）。
AUTO_CLOSED_VALUES = ['自动结案']

# 视为「未填写」的等价空值（pandas 读Excel 空单元格会得到这些）
_EMPTY_AUDIT_VALUES = ('', 'nan', 'None', None)


def find_audit_column(columns, candidates=None, default=None):
    """从列集合中取第一个真实存在的候选列。

    参数
    ----
    columns : 容器
        DataFrame.columns 或任何支持 `in` 的列名集合。
    candidates : list[str], 可选
        候选列名，按优先级排列；默认 :data:`AUDIT_COL_CANDIDATES`。
    default :任意
        全部候选都不存在时返回的默认值（默认 None）。

    返回
    ----
    命中的列名，或 default。
    """
    for col in (candidates if candidates is not None else AUDIT_COL_CANDIDATES):
        if col in columns:
            return col
    return default


def find_result_column(columns, default=None):
    """只找审核结论列（`审核结果` / `audit_result`）。"""
    return find_audit_column(columns, RESULT_COL_CANDIDATES, default)


def find_status_column(columns, default=None):
    """只找工作流状态列（`审核状态` / `audit_status`）。"""
    return find_audit_column(columns, STATUS_COL_CANDIDATES, default)


def is_audited_value(value):
    """判断一个审核结论值是否代表「已审核」。

    `自动结案` 也是已审核（由 auto_closer 写入）；空串/NaN/None 视为未审核。
    """
    return value not in _EMPTY_AUDIT_VALUES
