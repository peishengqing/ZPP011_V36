#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet8_reason_summary.py — Sheet8 偏差原因汇总（v36 抽取，未修改逻辑）
"""
import pandas as pd
from analysis.excel_builder.write_sheet_util import ensure_numeric_cols

_CIRCLES = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩']


def _fmt_qty(v):
    """数量格式化：保留1位小数并去掉多余的0（1166.7 / 529 / 3）；
    小于0.1的非零值保留2位小数，避免显示成 0"""
    a = abs(float(v))
    s = f"{a:.2f}" if 0 < a < 0.1 else f"{a:.1f}"
    return s.rstrip('0').rstrip('.') if '.' in s else s


def _dev_breakdown(ws_df, mode):
    """
    按 物料分类(原料/包材) → 单位 两层分解偏差量。
    mode: 'over'=多耗(>0求和) / 'under'=少耗(<0绝对值求和) / 'net'=净偏差(带方向)
    返回多行字符串，如：
        原料：①3557.4KG ②12包
        包材：①529个 ②88.7KG
    半成品并入原料口径。
    """
    tmp = ws_df.copy()
    tmp['_cat'] = tmp['物料分类'].astype(str).apply(
        lambda x: '包材' if x == '包材' else '原料')
    unit_series = tmp['组件单位'].fillna('').astype(str).str.strip() \
        if '组件单位' in tmp.columns else pd.Series('', index=tmp.index)
    tmp['_unit'] = unit_series.replace('', '未知')

    parts = []
    for cat in ('原料', '包材'):
        sub = tmp[tmp['_cat'] == cat]
        if sub.empty:
            continue
        if mode == 'over':
            g = sub[sub['材料偏差'] > 0].groupby('_unit')['材料偏差'].sum()
        elif mode == 'under':
            g = sub[sub['材料偏差'] < 0].groupby('_unit')['材料偏差'].sum().abs()
        else:  # net
            g = sub.groupby('_unit')['材料偏差'].sum()
        g = g[g.round(2) != 0]
        if g.empty:
            continue
        # 按绝对值降序排列并编号
        g = g.reindex(g.abs().sort_values(ascending=False).index)
        items = []
        for k, (unit, val) in enumerate(g.items()):
            prefix = _CIRCLES[k] if k < 10 else f'{k + 1}.'
            if mode == 'net':
                direction = '净多耗' if val > 0 else '净少耗'
                items.append(f"{prefix}{direction}{_fmt_qty(val)}{unit}")
            else:
                items.append(f"{prefix}{_fmt_qty(val)}{unit}")
        parts.append(f"{cat}：{' '.join(items)}")
    return '\n'.join(parts) or '0'


def build_sheet8(df, report_progress, progress_idx=8):
    """
    构建 Sheet8 偏差原因汇总 DataFrame
    参数:
        df: 主数据 DataFrame
        report_progress: 进度回调函数
        progress_idx: 进度索引（默认8）
    返回:
        reason_summary_df: 偏差原因汇总 DataFrame
    """
    report_progress(progress_idx, "Sheet8-原因汇总", 0)

# 确保数值列为数值类型（防止字符串导致比较错误）
    ensure_numeric_cols(df, ["材料偏差", "偏差率(%)", "偏差金额", "偏差金额(含税)", "数量-实际", "数量-定额"])
    # 使用 analyzer.py 中已经生成的 '标准原因' 列（替代料、系统无定额等已正确标记）
    # 如果没有该列（兼容旧版），则动态生成
    if '标准原因' not in df.columns:
        from utils.helpers import standardize_remark
        df['标准原因'] = df['备注原因'].apply(standardize_remark)

    # 过滤：必须有标准原因且材料偏差不为0
    has_reason = df[(df['标准原因'].notna()) & (
        df['标准原因'] != '') & (df['材料偏差'] != 0)].copy()
    has_reason['_std_reason'] = has_reason['标准原因']

    reason_summary = []

    for (factory, ws_name), ws_grp in has_reason.groupby(['工厂名称', '车间']):
        # 物料级合计：多耗/少耗按物料跨所有原因汇总（不再只看单一原因）
        mat_reasons = ws_grp.groupby(['物料分类', '组件物料描述']).agg(
            次数=('材料偏差', 'count'),
            多耗=('材料偏差', lambda x: x[x > 0].sum()),
            少耗=('材料偏差', lambda x: abs(x[x < 0].sum())),
            单位=('组件单位', lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else ''),
        ).reset_index()
        mat_reasons['总偏差'] = mat_reasons['多耗'] + mat_reasons['少耗']
        # 主导原因：取绝对偏差最大的那条原因作为标签，并带其示例备注
        reason_grp = ws_grp.groupby(['组件物料描述', '_std_reason']).agg(
            主导_多耗=('材料偏差', lambda x: x[x > 0].sum()),
            主导_少耗=('材料偏差', lambda x: abs(x[x < 0].sum())),
            示例备注=('备注原因', lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else ''),
        ).reset_index()
        reason_grp['主导_合计'] = reason_grp['主导_多耗'] + reason_grp['主导_少耗']
        dom = reason_grp.sort_values('主导_合计', ascending=False).drop_duplicates(
            subset=['组件物料描述'], keep='first')
        dom = dom[['组件物料描述', '_std_reason', '示例备注']].rename(
            columns={'_std_reason': '主导原因'})
        mat_reasons = mat_reasons.merge(dom, on='组件物料描述', how='left')
        mat_reasons = mat_reasons.sort_values('总偏差', ascending=False)

        def fmt_top(grp_df, label):
            result = ''
            for rank, (_, mr) in enumerate(grp_df.head(5).iterrows(), 1):
                unit = mr['单位'] if pd.notna(mr['单位']) and mr['单位'] != '' else ''
                net = round(float(mr['多耗']) - float(mr['少耗']), 1)
                if net > 0:
                    dev_str = f"（多耗{net:.1f}{unit}）"
                elif net < 0:
                    dev_str = f"（少耗{abs(net):.1f}{unit}）"
                else:
                    dev_str = ''
                std_r = mr['主导原因']
                ex = str(mr['示例备注']).strip() if pd.notna(mr['示例备注']) and str(mr['示例备注']).strip() != '' else ''
                ex_part = f"（例：{ex}，{mr['次数']}次）" if ex else f"（{mr['次数']}次）"
                result += f"{mr['组件物料描述']}{dev_str} — {std_r}{ex_part}\n"
            return result.rstrip('\n') or '无'

        raw_top5_str = fmt_top(
            mat_reasons[mat_reasons['物料分类'].isin(['原材料'])], '原料')
        pkg_top5_str = fmt_top(
            mat_reasons[mat_reasons['物料分类'].isin(['包材'])], '包材')

        ws_all = df[(df['工厂名称'] == factory) & (df['车间'] == ws_name)]
        reason_summary.append({
            '工厂': factory,
            '车间': ws_name,
            '多耗': _dev_breakdown(ws_all, 'over'),
            '少耗': _dev_breakdown(ws_all, 'under'),
            '净偏差数量': _dev_breakdown(ws_all, 'net'),
            '原因数': len(ws_grp),
            '原料主要原因（Top5）': raw_top5_str,
            '包材主要原因（Top5）': pkg_top5_str,
        })

    reason_index_set = set(zip(has_reason['工厂名称'], has_reason['车间']))
    for factory, ws_name in df.groupby(['工厂名称', '车间']).groups.keys():
        if (factory, ws_name) not in reason_index_set:
            ws_data = df[(df['工厂名称'] == factory) & (df['车间'] == ws_name)]
            reason_summary.append({
                '工厂': factory,
                '车间': ws_name,
                '多耗': _dev_breakdown(ws_data, 'over'),
                '少耗': _dev_breakdown(ws_data, 'under'),
                '净偏差数量': _dev_breakdown(ws_data, 'net'),
                '原因数': 0,
                '原料主要原因（Top5）': '无备注',
                '包材主要原因（Top5）': '无备注',
            })

    reason_summary_df = pd.DataFrame(reason_summary)
    report_progress(progress_idx, "Sheet8-原因汇总", 100)
    return reason_summary_df
