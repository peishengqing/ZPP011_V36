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

        # 0. Stat 卡片筛选（大偏差/无备注/已审核）
        stat = filters.get('stat')
        if stat == 'big_dev':
            rc = next((c for c in ['偏差率(%)', '偏差率'] if c in df.columns), None)
            if rc:
                df = df[pd.to_numeric(df[rc], errors='coerce').abs() > 10]
        elif stat == 'no_note':
            rc = next((c for c in ['备注原因', '备注'] if c in df.columns), None)
            if rc:
                df = df[df[rc].isna() | (df[rc].astype(str).str.strip() == '')]
        elif stat == 'approved':
            rc = next((c for c in ['备注原因', '备注'] if c in df.columns), None)
            if rc:
                df = df[df[rc].notna() & (df[rc].astype(str).str.strip() != '')]

        # 1. 工厂筛选
        factory = filters.get('factory')
        if factory and factory != '全部':
            factory_col = next(
                (c for c in ['工厂', '工厂名称'] if c in df.columns), None
            )
            if factory_col:
                df = df[df[factory_col] == factory]

        # 2. 车间筛选
        workshop = filters.get('workshop')
        if workshop and workshop != '全部':
            workshop_col = next(
                (c for c in ['车间', '生产管理员描述'] if c in df.columns), None
            )
            if workshop_col:
                df = df[df[workshop_col] == workshop]
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
            elif dev_rate == '绝对值≥10%':
                df = df[df['偏差率(%)'].abs() >= 10]

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

        # 8. 审核来源（兼容 UI 显示值和存储值）
        audit_source = filters.get('audit_source')
        if audit_source and audit_source != '全部':
            src_col = next(
                (c for c in ['audit_source', '审核来源'] if c in df.columns), None
            )
            if src_col:
                df = df[df[src_col] == audit_source]

        # 9. 审核状态
        audit_status = filters.get('audit_status')
        if audit_status and audit_status != '全部' and 'audit_status' in df.columns:
            df = df[df['audit_status'] == audit_status]

        # 10. 校验提示（映射业务含义）
        remark_check = filters.get('remark_check_status')
        if remark_check and remark_check != '全部' and 'remark_check_status' in df.columns:
            if remark_check == '红色':
                df = df[df['remark_check_status'] == 'red']
            elif remark_check == '黄色':
                df = df[df['remark_check_status'] == 'yellow']
            elif remark_check == '正常':
                df = df[df['remark_check_status'] == 'none']

        # 11. 颜色筛选（优先级标签）——同时兼容侧边栏 priority_color 和顶部栏 _color
        color = filters.get('priority_color') or filters.get('_color')
        if color and color != '全部' and '_priority_label' in df.columns:
            cmap = {'红': '红', '橙': '橙', '黄': '黄', '绿': '绿'}
            df = df[df['_priority_label'] == cmap.get(color, color)]

        # 12. 物料大类筛选（兼容 material_category 和 物料类型 两种列名）
        material_category = filters.get('material_category')
        if material_category and material_category != '全部':
            cat_col = None
            for col in ['material_category', '物料类型', '物料大类']:
                if col in df.columns:
                    cat_col = col
                    break
            if cat_col:
                print(f'[DEBUG] 物料大类筛选: 选={material_category}, 使用列={cat_col}, 列值分布={df[cat_col].value_counts().to_dict()}')
                df = df[df[cat_col] == material_category]
                print(f'[DEBUG] 筛选后行数: {len(df)}')
            else:
                print(f'[DEBUG] 物料大类筛选: 未找到物料类型列, filters={filters}')

        # 13. 日期范围筛选
        date_start = filters.get('date_start')
        date_end = filters.get('date_end')
        if (date_start or date_end) and '订单日期' in df.columns:
            df['订单日期'] = pd.to_datetime(df['订单日期'], errors='coerce')
            if date_start:
                start_dt = pd.to_datetime(date_start)
                df = df[df['订单日期'] >= start_dt]
            if date_end:
                end_dt = pd.to_datetime(date_end)
                df = df[df['订单日期'] <= end_dt]

        # 14. 关键词搜索（全文匹配）
        search = filters.get('search', '').strip()
        if search:
            mask = pd.Series(False, index=df.index)
            for col in df.columns:
                mask |= df[col].astype(str).str.contains(search, case=False, na=False)
            df = df[mask]

        # 15. 备注筛选
        remark = filters.get('remark')
        if remark and remark != '全部':
            remark_col = next(
                (c for c in ['备注原因', '备注', 'remark'] if c in df.columns), None
            )
            if remark_col:
                temp = df[remark_col].fillna('').astype(str).str.strip().replace('nan', '')
                if remark == '为空':
                    df = df[temp == '']
                elif remark == '不为空':
                    df = df[temp != '']
                else:
                    df = df[temp == remark]

        # 15. AI审核结果筛选
        ai_result = filters.get('ai_result')
        if ai_result and ai_result != '全部':
            src_col = next(
                (c for c in ['审核来源', 'audit_source'] if c in df.columns), None
            )
            if src_col:
                if ai_result == '合格':
                    df = df[df[src_col] == '审核合格']
                elif ai_result == '需改进':
                    df = df[df[src_col] == '审核待改进']
                elif ai_result == 'AI建议':
                    df = df[df[src_col].str.startswith('AI建议', na=False)]
                elif ai_result == '未处理':
                    ai_sources = {'审核合格', '审核待改进', 'AI建议', 'AI建议（小偏差）'}
                    df = df[~(df[src_col].isin(ai_sources) | df[src_col].isna())]

        return df