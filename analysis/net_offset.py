# -*- coding: utf-8 -*-
"""
替代料净偏差自动抵消 v2 — 支持一对多/多对多物料组
基于并查集（Union-Find）构建物料连通分量，
在同一「订单日期 + 流程订单」内对组内所有物料偏差求和作为净偏差。
裴哥 | 2026-06-06
"""

import pandas as pd


def apply_net_offset(df: pd.DataFrame, alt_pairs: list, enable: bool = True, group_key: list = None) -> pd.DataFrame:
    """
    支持替代料组净偏差计算（一对多、多对多）
    基于替代料配对构建物料组（并查集），在同一订单内对组内所有物料偏差求和作为净偏差。

    参数:
        df: 必须包含列: 订单日期, 流程订单, 物料编码, 偏差数量, 偏差金额(含税)
        alt_pairs: 替代料配对列表
        enable: 是否启用净偏差抵消
        group_key: 分组键列表 [日期列名, 订单列名]，默认 ['订单日期', '流程订单']
    返回:
        添加了 '净偏差数量' 和 '净偏差金额' 列的 DataFrame
    """
    # 不启用时直接返回原 df
    if not enable:
        if '净偏差数量' not in df.columns:
            df['净偏差数量'] = df.get('偏差数量', 0)
        if '净偏差金额' not in df.columns:
            if '偏差金额(含税)' in df.columns:
                df['净偏差金额'] = df['偏差金额(含税)']
            elif '偏差金额' in df.columns:
                df['净偏差金额'] = df['偏差金额']
            else:
                df['净偏差金额'] = 0
        return df

    if df.empty or not alt_pairs:
        df['净偏差数量'] = df.get('偏差数量', 0)
        if '偏差金额(含税)' in df.columns:
            df['净偏差金额'] = df['偏差金额(含税)']
        elif '偏差金额' in df.columns:
            df['净偏差金额'] = df['偏差金额']
        else:
            df['净偏差金额'] = 0
        return df

    df = df.copy()

    # 初始化净偏差列
    df['净偏差数量'] = df.get('偏差数量', 0)
    if '偏差金额(含税)' in df.columns:
        df['净偏差金额'] = df['偏差金额(含税)']
    elif '偏差金额' in df.columns:
        df['净偏差金额'] = df['偏差金额']
    else:
        df['净偏差金额'] = 0

    # ---------- 并查集构建物料组 ----------
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for p in alt_pairs:
        # 提取物料编码
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            if isinstance(p[0], (list, tuple)):
                code_a = str(p[0][1]) if len(p[0]) > 1 else str(p[0][0])
                code_b = str(p[1][1]) if len(p[1]) > 1 else str(p[1][0])
            else:
                code_a = str(p[0])
                code_b = str(p[1])
            union(code_a, code_b)

    # 构建组映射（根节点 -> 成员列表）
    group_members = {}
    for code in parent.keys():
        root = find(code)
        group_members.setdefault(root, []).append(code)

    if not group_members:
        return df

    # ---------- 按订单分组计算组内净偏差 ----------
    if group_key is None:
        group_key = ['订单日期', '流程日期']
    date_col = group_key[0] if group_key[0] in df.columns else ('订单开始日期' if '订单开始日期' in df.columns else group_key[0])
    order_col = group_key[1] if len(group_key) > 1 and group_key[1] in df.columns else '流程订单'
    df['_key'] = df[date_col].astype(str) + '|' + df[order_col].astype(str)

    for key, group in df.groupby('_key'):
        # 收集该订单内所有物料编码及对应的行索引
        code_to_indices = {}
        for idx, row in group.iterrows():
            code = str(row['物料编码'])
            code_to_indices.setdefault(code, []).append(idx)

        # 为每个物料组计算净偏差
        group_net = {}
        for root, members in group_members.items():
            present = [m for m in members if m in code_to_indices]
            if not present:
                continue
            total_qty = 0
            total_amt = 0
            for code in present:
                for idx in code_to_indices[code]:
                    total_qty += df.at[idx, '偏差数量'] if pd.notna(df.at[idx, '偏差数量']) else 0
                    for col in ['偏差金额(含税)', '偏差金额']:
                        if col in df.columns:
                            try:
                                v = pd.to_numeric(df.at[idx, col], errors='coerce')
                                if pd.notna(v):
                                    total_amt += v
                                break
                            except Exception:
                                pass
            # 数量净偏差为0时强制金额为0
            if total_qty == 0:
                total_amt = 0
            group_net[root] = (total_qty, total_amt)

        # 将净偏差写回该组内的所有行
        for root, (net_qty, net_amt) in group_net.items():
            for code in group_members[root]:
                if code in code_to_indices:
                    for idx in code_to_indices[code]:
                        df.at[idx, '净偏差数量'] = net_qty
                        df.at[idx, '净偏差金额'] = net_amt
                        df.at[idx, '_替代料组'] = f"组_{root[:8]}"

    df.drop(columns=['_key'], inplace=True)

    # 数值格式化：保留2位小数，避免浮点精度问题
    df['净偏差数量'] = df['净偏差数量'].round(2)
    df['净偏差金额'] = df['净偏差金额'].round(2)

    # 更新"是否替代料"列：_替代料组非空的即为替代料
    if '_替代料组' in df.columns:
        df['是否替代料'] = df['_替代料组'].notna().map({True: '是', False: '否'})

    # 保留"净偏差"列作为"净偏差金额"的别名（向后兼容）
    if '净偏差金额' in df.columns and '净偏差' not in df.columns:
        df['净偏差'] = df['净偏差金额']

    return df
