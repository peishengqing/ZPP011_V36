# -*- coding: utf-8 -*-
"""
库存流水账适配模块
提供库存快照读取、入库明细合并等功能
"""

import pandas as pd
from datetime import datetime


def load_inventory_snapshot(filepath: str, sheet_name: str = "过期提醒") -> pd.DataFrame:
    """
    读取库存快照表格，返回包含物料编码、物料名称、现存量、生产日期、保质期的DataFrame。
    自动按列名匹配，兼容列顺序变化及多余列的情况。
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name)

    # 目标列映射（标准名 → 实际可能出现的列名列表）
    column_aliases = {
        "物料编码": ["物料编码", "物料号", "料号", "产品编码"],
        "物料名称": ["物料名称", "品名", "产品名称", "物料描述"],
        "现存量": ["现存量", "库存数量", "库存", "结存数量"],
        "生产日期": ["生产日期", "生产日", "制造日期"],
        "保质期": ["保质期", "到期日期", "失效日期", "有效期至"]
    }

    result = {}
    for standard_name, aliases in column_aliases.items():
        for col in df.columns:
            if col.strip() in aliases:
                result[standard_name] = df[col]
                break

    # 检查是否缺失关键列
    missing = [k for k in column_aliases if k not in result]
    if missing:
        raise KeyError(f"表格缺少关键列: {', '.join(missing)}")

    output = pd.DataFrame(result)

    # 清理：去掉物料编码为空的行
    output = output.dropna(subset=["物料编码"])

    # 日期转换
    output["生产日期"] = pd.to_datetime(output["生产日期"], errors="coerce")
    output["保质期"] = pd.to_datetime(output["保质期"], errors="coerce")

    # 现存量转数值
    output["现存量"] = pd.to_numeric(output["现存量"], errors="coerce")

    return output.reset_index(drop=True)


def merge_inventory_records(filepath: str) -> pd.DataFrame:
    """
    合并"采购入库"和"其他入库"两个工作表，返回统一的入库流水。
    自动统一列名，并添加"入库类型"列区分来源。
    """
    # 读取两个工作表
    df_purchase = pd.read_excel(filepath, sheet_name="采购入库")
    df_other = pd.read_excel(filepath, sheet_name="其他入库")

    # 采购入库的列映射（根据实际表格结构调整）
    purchase_mapping = {
        "物料编码": "物料编码",
        "物料名称": "物料名称",
        "数量": "数量",
        "单位": "单位",
        "单价": "单价",
        "合计": "金额",
        "入库日期": "入库日期"
    }
    # 其他入库的列映射
    other_mapping = {
        "物料编码": "物料编码",
        "物料名称": "物料名称",
        "数量": "数量",
        "单位": "单位",
        "单价": "单价",
        "金额": "金额",
        "入库日期": "入库日期"
    }

    # 统一列名
    df_purchase = df_purchase.rename(columns=purchase_mapping)
    df_other = df_other.rename(columns=other_mapping)

    # 确保两表有相同的列
    common_cols = ["物料编码", "物料名称", "数量", "单位", "单价", "金额", "入库日期"]
    df_purchase = df_purchase[common_cols]
    df_other = df_other[common_cols]

    # 打标签
    df_purchase["入库类型"] = "采购入库"
    df_other["入库类型"] = "其他入库"

    # 合并
    df_merged = pd.concat([df_purchase, df_other], ignore_index=True)

    # 日期转换
    df_merged["入库日期"] = pd.to_datetime(df_merged["入库日期"], errors="coerce")
    # 数值转换
    df_merged["数量"] = pd.to_numeric(df_merged["数量"], errors="coerce")
    df_merged["单价"] = pd.to_numeric(df_merged["单价"], errors="coerce")
    df_merged["金额"] = pd.to_numeric(df_merged["金额"], errors="coerce")

    return df_merged


def calc_expiry_warning(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算剩余有效天数，并添加'过期状态'列。
    返回的DataFrame会增加两列：
    - 剩余天数：距离保质期的天数（过期时为负数）
    - 过期状态：'已过期' / '即将过期(30天内)' / '正常'
    """
    today = datetime.now().date()
    # 去掉时间部分，仅保留日期
    df["保质期_date"] = pd.to_datetime(df["保质期"]).dt.date
    df["剩余天数"] = (df["保质期_date"] - today).apply(lambda x: x.days)

    def label(days):
        if days <= 0:
            return "已过期"
        elif days <= 30:
            return "即将过期(30天内)"
        else:
            return "正常"

    df["过期状态"] = df["剩余天数"].apply(label)
    # 删除辅助列
    df = df.drop(columns=["保质期_date"])
    return df
