#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
筛选引擎（FilterEngine）- 纯业务逻辑，无 GUI 依赖
接收筛选条件字典和 DataFrame，返回过滤后的 DataFrame
"""

import pandas as pd


class FilterEngine:
    """筛选引擎，支持多条件组合过滤"""

    def __init__(self, column_mapping: dict = None):
        """
        column_mapping: UI字段名 -> DataFrame列名的映射（可选）
        """
        self.column_mapping = column_mapping or {}

    def apply(self, filters: dict, data: pd.DataFrame) -> pd.DataFrame:
        """
        应用筛选条件，返回过滤后的 DataFrame
        filters: 从 FilterPanel.get_filters() 返回的字典
        """
        if data is None or data.empty:
            return data


        df = data.copy()

        # 1. 工厂筛选
        factory = filters.get('factory')
        if factory and factory != '全部' and '工厂' in df.columns:
            df = df[df['工厂'] == factory]

        # 2. 车间筛选
        workshop = filters.get('workshop')
        if workshop and workshop != '全部' and '车间' in df.columns:
            df = df[df['车间'] == workshop]

        # 3. 物料描述模糊匹配
        material = filters.get('material', '').strip()
        if material:
            if '物料名称' in df.columns:
                df = df[df['物料名称'].str.contains(material, na=False, case=False)]
            elif '组件物料描述' in df.columns:
                df = df[df['组件物料描述'].str.contains(material, na=False, case=False)]

        # 4. 偏差率
        dev_rate = filters.get('dev_rate')
        if dev_rate and dev_rate != '全部' and '偏差率(%)' in df.columns:
            if dev_rate == '>10%':
                df = df[df['偏差率(%)'] > 10]
            elif dev_rate == '>20%':
                df = df[df['偏差率(%)'] > 20]
            elif dev_rate == '>30%':
                df = df[df['偏差率(%)'] > 30]
            elif dev_rate == '<-10%':
                df = df[df['偏差率(%)'] < -10]
            elif dev_rate == '<-20%':
                df = df[df['偏差率(%)'] < -20]

        # 5. 金额范围
        amount_min = filters.get('amount_min', '').strip()
        amount_max = filters.get('amount_max', '').strip()
        if (amount_min or amount_max) and '偏差金额' in df.columns:
            if amount_min:
                try:
                    min_val = float(amount_min)
                    df = df[df['偏差金额'] >= min_val]
                except ValueError:
                    pass
            if amount_max:
                try:
                    max_val = float(amount_max)
                    df = df[df['偏差金额'] <= max_val]
                except ValueError:
                    pass

        # 6. 审核状态（基于"备注原因"是否为空）
        status = filters.get('status')
        if status and status != '全部' and '备注原因' in df.columns:
            if status == '已备注':
                df = df[df['备注原因'].notna() & (df['备注原因'] != '')]
            elif status == '需补备注':
                df = df[df['备注原因'].isna() | (df['备注原因'] == '')]

        # 7. 替代料筛选（关键）
        is_alt = filters.get('is_alt')
        if is_alt and is_alt != '全部':
            possible_alt_cols = ['_is_alt', '是否替代料', '替代料']
            alt_col = None
            for col in possible_alt_cols:
                if col in df.columns:
                    alt_col = col
                    break
            if alt_col:
                # 调试输出，便于排查（完成后可删除）
                if alt_col == '_is_alt':
                    # 布尔列
                    df = df[df[alt_col] == (is_alt == '是')]
                else:
                    # 字符串列，标准化后比较
                    df = df[df[alt_col].astype(str).str.strip() == ('是' if is_alt == '是' else '否')]
            else:
                pass  # 未找到替代料列，不做筛选

        # 8. 优先级颜色（如果有）
        color = filters.get('priority_color')
        if color and color != '全部' and '_priority_label' in df.columns:
            df = df[df['_priority_label'] == color]

        return df
