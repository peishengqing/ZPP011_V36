# -*- coding: utf-8 -*-
"""下拉筛选「动态级联」公共件（v43.171）

## 为什么需要这个模块
ZPP011 有 5 个看板（管理/偏差率预警/负损/替代料/半成品），它们的筛选 mask 链
**函数名与顺序基本一致**（见各看板 `_apply_filter`），但下拉选项刷新机制五花八门：

  · 负损看板 v43.170：`_other_conditions_mask` + `_replace_combo_items`（双向，正确）
  · 半成品看板内联版：用 **已过滤的 filtered** 重算（单向收缩，不可逆）
      且带 `not filtered.empty` 守卫 → 筛到空时整个刷新被跳过、下拉留陈旧选项
  · 偏差率预警：`_refresh_dependent_combo` 同样用 filtered（单向），且**漏了 combo_mtd**
  · 替代料看板：完全没有级联

实测死选项（2026-10-10 数据 ZPP011_20261001-20261008，offscreen 逐选项真点）：
  · 偏差率预警半成品分类 3/6 = 50% 死选项；选饮料厂后物料类型 2/5 = 40% 死
  · 替代料看板半成品分类 3/6 = 50% 死选项（结构性，放开已读仍死）
  · 半成品看板「分类 × 投料状态」交叉 14/35 死格

## 核心口径（三条铁律）
1. **exclude-self（双向）**：重算某下拉的选项时，用「**除自己以外的所有条件**」筛数据，
   而不是用「已过滤结果」。后者会把自己算进去，导致选了 A 之后 B 列表只留 A 的交集，
   用户想换别的必须先选回「全部」——级联变成单向收缩、不可逆。
2. **blockSignals**：重填选项会触发 `currentTextChanged` → 回调 `_apply_filter`
   → 再刷新，无 blockSignals 会无限递归。
3. **空结果要收成只剩「全部」**：不能像半成品看板那样用 `not filtered.empty` 守卫跳过，
   否则筛到 0 行时用户还看到上一次的陈旧选项（那选项在当前条件下必然 0 行）。

另外两个易错点：
  · `setattr(obj, name, v)` 的 name **必须是真实属性名**。曾漏掉前导下划线导致
    setattr 建了个新属性、真筛选状态从不更新，而 **pyflakes 抓不到**（F821 只查读）。
  · 重填的当前值失效时要**直接改状态属性**（信号已被 block，槽不会触发）。
"""
from __future__ import annotations

# 注：不 import pandas —— 本模块只操作调用方传进来的 DataFrame/Series（duck typing），
# 避免给调用方强加 pandas 版本约束，也让这个纯工具模块能被非 pandas 上下文复用。


def replace_combo_items(combo, values, cur_value, attr_name, owner=None):
    """重填 QComboBox 选项并保留「全部」；当前值失效则回退「全部」。

    这是纯函数式的安全实现：**不接收 attr_name 做 setattr**，改由调用方把返回值
    赋回状态变量，避免「setattr 建了幽灵属性、真状态从不更新」这类静默失效
    （pyflakes 抓不到 F809/setattr 字符串参数）。

    参数
    ----
    combo : QComboBox
    values : list[str]  新的有效选项（不含「全部」）
    cur_value : str当前已选值（'all' 或某个具体值）
    attr_name : str仅用于日志/错误提示，便于定位调用点
    owner : object  可选，若提供且确有该属性，则同步把新值写回（防幽灵属性双保险）

    返回
    ----
    (keep_value, changed) —— keep_value 是最终应写入状态的字符串
    （'all' 或具体值），changed 表示选项是否真的变了。
    """
    wanted = ['全部'] + list(values)
    have = [combo.itemText(i) for i in range(combo.count())]
    keep = cur_value if (cur_value and cur_value != 'all' and
                         cur_value in values) else 'all'

    if wanted == have:
        # 选项没变：仅保证状态与显示一致，不做无谓重填（避免焦点跳动）
        if keep != cur_value and owner is not None and hasattr(owner, attr_name):
            setattr(owner, attr_name, keep)
            if combo.currentText() != ('全部' if keep == 'all' else keep):
                combo.blockSignals(True)
                try:
                    combo.setCurrentText('全部' if keep == 'all' else keep)
                finally:
                    combo.blockSignals(False)
        return keep, False

    combo.blockSignals(True)
    try:
        combo.clear()
        combo.addItems(wanted)
        combo.setCurrentText('全部' if keep == 'all' else keep)
    finally:
        combo.blockSignals(False)
    # 直接写状态（信号被 block 了，槽不会触发）
    if owner is not None and hasattr(owner, attr_name):
        setattr(owner, attr_name, keep)
    return keep, True


def cascade_options(df, mask_excl_self, col_name, exclude_values=frozenset()):
    """按「除自己外的条件」重算某列的下拉选项值。

    参数
    ----
    df : DataFrame  原始数据（未过滤）
    mask_excl_self : Series[bool]  由各看板的 `_other_conditions_mask(df, exclude=...)`
                    算出的掩码（已排除该下拉自己那一维）
    col_name : str|None  该下拉对应的数据列名
    exclude_values : set  需永久排除的值（如负损看板的 {'食品成品','饮料成品'}）

    返回
    ----
    sorted(list[str])  非空、去空白、排除 exclude_values 的取值升序列表。
    ⚠ **空结果返回 [] 而非跳过刷新** —— 调用方应据此把下拉收成只剩「全部」
    （不要像半成品看板那样用 `if not filtered.empty` 守卫跳过，那会留陈旧选项）。
    """
    if not col_name or col_name not in df.columns:
        return []
    try:
        sub = df[mask_excl_self]
    except Exception:
        sub = df
    if sub is None or sub.empty:
        return []
    vals = sub[col_name].dropna().astype(str).str.strip().unique()
    return sorted(v for v in vals if v and v not in exclude_values)