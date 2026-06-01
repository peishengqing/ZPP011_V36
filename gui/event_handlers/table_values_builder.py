"""
table_values_builder.py
根据 audit_cols_config 自动构建 Treeview insert 的 values 元组，
彻底避免 cols / values 顺序不一致导致的列错位。
"""

import pandas as pd
from config.audit_cols_config import AUDIT_COLS_CONFIG


def build_audit_values(row, i, ctx):
    """
    按 AUDIT_COLS_CONFIG 的顺序构建 values 元组。
    row: pandas Series（一行数据）
    i:   行号（从1开始）
    ctx:  额外上下文 dict，包含：
         mat_category, mat_desc, dev_rate, is_alt, status,
         remark, batch_remark, audit_result_val,
         audit_status_val, audit_source_val
    """
    vals = []
    for key, heading, width, anchor in AUDIT_COLS_CONFIG:
        v = _extract_value(key, row, i, ctx)
        vals.append(v)
    return tuple(vals)


def _extract_value(key, row, i, ctx):
    """根据 key 从 row / ctx 中取值"""

    # ── 索引列（ctx 传入）──
    if key == "idx":
        return i

    if key == "excel_row":
        raw = row.get("原表行号", row.get("excel_row", 0))
        return int(raw) if pd.notna(raw) else ""

    # ── 普通列：优先 row，其次 ctx ──
    if key == "factory":
        return str(row.get("工厂", row.get("工厂名称", "")))

    if key == "admin":
        return str(row.get("车间", row.get("生产管理员描述", "")))

    if key == "order_date":
        raw = row.get("订单日期", "")
        if pd.notna(raw):
            return str(raw)[:10]
        return ""

    if key == "order_type":
        v = str(row.get("订单类型", "")).strip()
        return v if v not in ("", "nan", "NaN", "None") else ""

    if key == "order_no":
        for col in ("流程订单", "订单号", "订单编号"):
            if col in row.index and pd.notna(row.get(col)):
                return str(row.get(col))
        return ""

    if key == "material_category":
        return ctx.get("material_category", "")

    if key == "code":
        return str(row.get("物料编码", row.get("组件物料号", "")))

    if key == "name":
        return ctx.get("mat_desc", "")[:30]

    if key == "unit":
        return str(row.get("组件单位", row.get("单位", "")))

    if key == "quota":
        return f"{row.get('定额', row.get('数量-定额', 0)):.3f}"

    if key == "actual":
        return f"{row.get('实际', row.get('数量-实际', 0)):.3f}"

    if key == "dev_rate":
        return f"{ctx.get('dev_rate', 0):.2f}%"

    if key == "is_alt":
        return ctx.get("is_alt", "")

    if key == "status":
        return ctx.get("status", "")

    if key == "remark":
        return ctx.get("remark", "")

    if key == "batch_remark":
        v = ctx.get("batch_remark", "")
        return v[:30] if v else ""

    if key == "audit_result":
        return ctx.get("audit_result_val", "")

    if key == "AI建议":
        v = str(row.get("AI建议", ""))
        return v[:50] if v else ""

    if key == "audit_status":
        return ctx.get("audit_status_val", "")

    if key == "audit_source":
        return ctx.get("audit_source_val", "")

    if key == "deviation_amount":
        return f"{row.get('偏差金额', 0):,.2f}"

    if key == "remark_check_status":
        return str(row.get("remark_check_status", ""))

    if key == "remark_check_msg":
        return str(row.get("remark_check_msg", ""))

    # 兜底
    if key in row.index:
        v = row.get(key)
        return v if pd.notna(v) else ""

    return ""
