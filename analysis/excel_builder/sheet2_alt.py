#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet2_alt.py — Sheet2 替代料明细（v36 抽取，兼容三元组配对）
返回: (alt_df, alt_order_mat_set)
"""
import pandas as pd


def build_sheet2(df, alt_pairs, report_progress, progress_idx=2):
    """
    构建 Sheet2 替代料明细 DataFrame 及替代料订单-物料集合
    参数:
        df: 主数据 DataFrame
        alt_pairs: 替代料配对列表，每个元素为 (物料A, 物料B)
                  物料可以是字符串、二元组 (code, name) 或三元组 (factory, code, name)
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认2）
    返回:
        (alt_df, alt_order_mat_set):
            alt_df: 替代料明细 DataFrame
            alt_order_mat_set: set of (订单号, 物料描述) 用于标记替代料
    """
    report_progress(progress_idx, "Sheet2-替代料明细", 0)
    print("[DEBUG do_analysis_v2] 开始生成Sheet2")

    # ---------- 兼容性转换：将配对中的物料提取为描述字符串 ----------
    converted_pairs = []
    for a, b in alt_pairs:
        def get_desc(item):
            if isinstance(item, (list, tuple)):
                if len(item) == 3:
                    return str(item[2]) if item[2] else ''
                elif len(item) == 2:
                    return str(item[1]) if item[1] else ''
                else:
                    return str(item[0]) if item[0] else ''
            else:
                return str(item)
        desc_a = get_desc(a)
        desc_b = get_desc(b)
        if desc_a and desc_b:
            converted_pairs.append((desc_a, desc_b))
        else:
            print(f"[警告] 跳过无效替代料配对: {a} ↔ {b}")

    col_p = '偏差率(%)'
    code_col = next((c for c in df.columns if c in ('组件物料编码', '组件物料号')), None)
    alt_rows = []

    def _match_rows(grp, desc):
        """三级匹配：精确 → 包含 → 编码，返回匹配的行"""
        if not desc:
            return grp.iloc[0:0]
        # 第一级：精确匹配
        rows = grp[grp['组件物料描述'] == desc]
        if len(rows) > 0:
            return rows
        # 第二级：包含匹配
        rows = grp[grp['组件物料描述'].str.contains(desc, na=False, regex=False)]
        if len(rows) > 0:
            return rows
        # 第三级：编码匹配
        if code_col:
            rows = grp[grp[code_col].astype(str).str.contains(desc, na=False, regex=False)]
            if len(rows) > 0:
                return rows
        return grp.iloc[0:0]

    group_seq = 0  # 替代料组序号

    # ---- 性能优化：预建索引，避免「逐订单 × 逐配对」全扫描 ----
    # 原实现复杂度 O(订单数 × 配对数)，在 1 万行 / 1500 订单 / 40 配对下耗时可达数十秒。
    # 改为：先建「描述/编码 -> 出现过的订单集合」索引，对每个配对仅定位相关订单，
    # 再仅遍历这些订单做三级匹配（语义与原 _match_rows 完全一致）。
    # 按物料A分组，处理1对多的情况
    a_to_bs = {}
    for mat_a_desc, mat_b_desc in converted_pairs:
        a_to_bs.setdefault(mat_a_desc, []).append(mat_b_desc)

    order_groups = {}
    desc_to_orders = {}
    for _order, _grp in df.groupby('流程订单'):
        order_groups[_order] = _grp
        _dset = set()
        for _d in _grp['组件物料描述'].dropna().astype(str):
            _dset.add(_d)
        for _d in _dset:
            desc_to_orders.setdefault(_d, set()).add(_order)
    if code_col:
        code_to_orders = {}
        for _order, _grp in order_groups.items():
            _cset = set()
            for _c in _grp[code_col].dropna().astype(str):
                _cset.add(_c)
            for _c in _cset:
                code_to_orders.setdefault(_c, set()).add(_order)

    def _related_orders(sub):
        """收集所有「描述或编码包含 sub（子串）」的订单，保留与原 _match_rows 一致的三级匹配语义"""
        if not sub:
            return set()
        res = set()
        for _d, _ords in desc_to_orders.items():
            if sub in _d:
                res |= _ords
        if code_col:
            for _c, _ords in code_to_orders.items():
                if sub in _c:
                    res |= _ords
        return res

    # 仅遍历「至少有一个配对物料出现」的订单
    _target_orders = set()
    for _a_desc, _b_descs in a_to_bs.items():
        _target_orders |= _related_orders(_a_desc)
        for _b in _b_descs:
            _target_orders |= _related_orders(_b)

    for order in _target_orders:
        grp = order_groups[order]
        for mat_a_desc, mat_b_descs in a_to_bs.items():
            rows_a = _match_rows(grp, mat_a_desc)
            if len(rows_a) == 0:
                continue
            a = rows_a.iloc[0]

            # 找到所有匹配的物料B
            b_list = []
            for mat_b_desc in mat_b_descs:
                rows_b = _match_rows(grp, mat_b_desc)
                if len(rows_b) > 0:
                    b_list.append(rows_b.iloc[0])

            if not b_list:
                continue

            # 提取A的数值
            qty_a = a.get('材料偏差', a.get('偏差数量', 0))
            amt_a = a.get('偏差金额(含税)', a.get('偏差金额', 0))

            # 计算整个替代料组的净偏差（A只算一次 + 所有B）
            total_qty_b = sum(float(b.get('材料偏差', b.get('偏差数量', 0))) for b in b_list)
            total_amt_b = sum(float(b.get('偏差金额(含税)', b.get('偏差金额', 0))) for b in b_list)
            net_qty = round(float(qty_a) + total_qty_b, 2)
            net_amt = round(float(amt_a) + total_amt_b, 2)

            # 替代料组标识
            group_seq += 1
            group_id = f"ALT_{order}_{group_seq}"

            # 每个B一行，共享同一净偏差值（A只算一次）
            for b in b_list:
                alt_rows.append({
                    '订单日期': pd.Timestamp(a['订单开始日期']).strftime('%Y-%m-%d'),
                    '车间': a['车间'],
                    '订单号': order,
                    '替代料组': group_id,
                    '物料A编码': a.get('组件物料编码', a.get('组件物料号', '')),
                    '物料A': a['组件物料描述'],
                    '单位': a['组件单位'] if pd.notna(a['组件单位']) else '',
                    '偏差A': a['材料偏差'],
                    '偏差率A': a[col_p],
                    '物料B编码': b.get('组件物料编码', b.get('组件物料号', '')),
                    '物料B': b['组件物料描述'],
                    '偏差B': b['材料偏差'],
                    '偏差率B': b[col_p],
                    '净偏差': net_qty,
                    '净偏差数量': net_qty,
                    '净偏差金额': net_amt,
                    '净偏差率': f"{(net_qty / a['数量-定额'] * 100):.1f}%" if a.get('数量-定额', 0) != 0 else '',
                    '备注': '替代料' if len(b_list) == 1 else '替代料(1对多)',
                    '标准原因': a.get('标准原因', ''),
                })

    alt_df = pd.DataFrame(alt_rows)
    print(f"[DEBUG do_analysis_v2] Sheet2完成，{len(alt_df)} 行")
    if len(alt_df) == 0 and len(converted_pairs) > 0:
        print(f"[DEBUG] 配对数: {len(converted_pairs)}, 前3个: {converted_pairs[:3]}")
        sample_descs = list(set(df['组件物料描述'].dropna()))[:5]
        print(f"[DEBUG] df物料描述样本: {sample_descs}")
    report_progress(progress_idx, "Sheet2-替代料明细", 100)

    # 构建替代料订单-物料集合（用于后续标记）
    alt_order_mat = set()
    for _, r in alt_df.iterrows():
        alt_order_mat.add((str(r['订单号']), str(r['物料A'])))
        # 1对多时物料B可能含 " + "，需要拆开
        for b_name in str(r['物料B']).split(' + '):
            b_name = b_name.strip()
            if b_name:
                alt_order_mat.add((str(r['订单号']), b_name))

    return alt_df, alt_order_mat
