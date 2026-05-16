"""
stock_parser.py
ZMM062 Excel 解析器
"""

import pandas as pd
import re
from datetime import datetime

def parse_zmm062_excel(file_path):
    """解析 ZMM062 Excel 文件，返回标准化 DataFrame"""
    try:
        food_df = pd.read_excel(file_path, sheet_name='食品', header=0)
        drink_df = pd.read_excel(file_path, sheet_name='饮料', header=0)
        df = pd.concat([food_df, drink_df], ignore_index=True)
    except Exception as e:
        raise ValueError(f"读取 Excel 失败：{e}")

    # 列名映射（根据实际 Excel 列名调整）
    column_mapping = {
        '公司代码': 'company_code',
        '工厂': 'plant_code',
        '工厂描述': 'plant_name',
        '库存地点': 'storage_location',
        '库存地点描述': 'storage_desc',
        '物料组描述': 'material_group',
        '物料号': 'material_code',
        '物料描述': 'material_desc',
        '规格描述': 'spec_desc',
        '单位': 'unit',
        '开始数量': 'opening_qty',
        '开始单价(含税)': 'unit_price',
        '开始金额(含税)': 'opening_amount',
        '入库总数量': 'inbound_qty',
        '入库总金额(含税)': 'inbound_amount',
        '出库总数量': 'outbound_qty',
        '出库总金额(含税)': 'outbound_amount',
        '结束数量': 'closing_qty',
        '结束金额(含税)': 'closing_amount',
        '周转天': 'turnover_days',
        '周转率': 'turnover_rate',
        '集团仓库分类': 'group_warehouse_category'
    }
    # 只保留存在的列
    existing_cols = [c for c in column_mapping.keys() if c in df.columns]
    df = df[existing_cols].rename(columns=column_mapping)

    # 提取报表月份（从文件名中匹配 YYYYMM）
    match = re.search(r'(\d{6})', file_path)
    if match:
        yymm = match.group(1)
        report_month = f"20{yymm[:2]}-{yymm[2:4]}"
    else:
        report_month = datetime.now().strftime("%Y-%m")
    df['report_month'] = report_month

    # 清洗数值列
    numeric_cols = ['opening_qty', 'opening_amount', 'inbound_qty', 'inbound_amount',
                    'outbound_qty', 'outbound_amount', 'closing_qty', 'closing_amount',
                    'unit_price', 'turnover_days', 'turnover_rate']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 处理集团仓库分类：缺失则填充“未知分类”
    if 'group_warehouse_category' in df.columns:
        df['group_warehouse_category'] = df['group_warehouse_category'].fillna('未知分类').astype(str)
    else:
        df['group_warehouse_category'] = '未知分类'

    # 确保出库数量/金额为负数（如果 SAP 导出已经是负数则保留，否则取负）
    if 'outbound_qty' in df.columns:
        df['outbound_qty'] = df['outbound_qty'].apply(lambda x: -abs(x) if x > 0 else x)
    if 'outbound_amount' in df.columns:
        df['outbound_amount'] = df['outbound_amount'].apply(lambda x: -abs(x) if x > 0 else x)

    # 删除全空列
    df = df.dropna(axis=1, how='all')

    return df