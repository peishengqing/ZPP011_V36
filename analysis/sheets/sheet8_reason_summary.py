#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sheet8_reason_summary.py — Sheet8 偏差原因汇总（v36 抽取，未修改逻辑）
"""
import pandas as pd
from utils.helpers import standardize_remark


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

    has_reason = df[(df['备注原因'].notna()) & (
        df['备注原因'] != '') & (df['材料偏差'] != 0)].copy()
    has_reason['_std_reason'] = has_reason['备注原因'].apply(standardize_remark)

    reason_summary = []

    for (factory, ws_name), ws_grp in has_reason.groupby(['工厂名称', '车间']):
        mat_reasons = ws_grp.groupby(['物料分类', '组件物料描述', '_std_reason']).agg(
            次数=('材料偏差', 'count'),
            多耗=('材料偏差', lambda x: x[x > 0].sum()),
            少耗=('材料偏差', lambda x: abs(x[x < 0].sum())),
            单位=('组件单位', lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else ''),
            示例备注=('备注原因', lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else ''),
        ).reset_index()
        mat_reasons['总偏差'] = mat_reasons['多耗'] + mat_reasons['少耗']
        mat_reasons = mat_reasons.sort_values('总偏差', ascending=False)

        def fmt_top(grp_df, label):
            result = ''
            for rank, (_, mr) in enumerate(grp_df.head(5).iterrows(), 1):
                parts = []
                unit = mr['单位'] if pd.notna(mr['单位']) and mr['单位'] != '' else ''
                if mr['多耗'] > 0:
                    parts.append(f"多耗{mr['多耗']:.1f}{unit}")
                if mr['少耗'] > 0:
                    parts.append(f"少耗{mr['少耗']:.1f}{unit}")
                dev_str = f"（{'，'.join(parts)}）" if parts else ''
                std_r = mr['_std_reason']
                ex = str(mr['示例备注'])[:15] if pd.notna(mr['示例备注']) and str(mr['示例备注']).strip() != '' else ''
                result += f"{mr['组件物料描述']}{dev_str} — {std_r}（例：{ex}…，{mr['次数']}次）\n"
            return result.rstrip('\n') or '无'

        raw_top5_str = fmt_top(
            mat_reasons[mat_reasons['物料分类'].isin(['原材料'])], '原料')
        pkg_top5_str = fmt_top(
            mat_reasons[mat_reasons['物料分类'].isin(['包材'])], '包材')

        ws_all = df[(df['工厂名称'] == factory) & (df['车间'] == ws_name)]
        reason_summary.append({
            '工厂': factory,
            '车间': ws_name,
            '多耗': round(ws_all[ws_all['材料偏差'] > 0]['材料偏差'].sum(), 2),
            '少耗': round(abs(ws_all[ws_all['材料偏差'] < 0]['材料偏差'].sum()), 2),
            '净偏差': round(ws_all['材料偏差'].sum(), 2),
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
                '多耗': round(ws_data[ws_data['材料偏差'] > 0]['材料偏差'].sum(), 2),
                '少耗': round(abs(ws_data[ws_data['材料偏差'] < 0]['材料偏差'].sum()), 2),
                '净偏差': round(ws_data['材料偏差'].sum(), 2),
                '原因数': 0,
                '原料主要原因（Top5）': '无备注',
                '包材主要原因（Top5）': '无备注',
            })

    reason_summary_df = pd.DataFrame(reason_summary)
    report_progress(progress_idx, "Sheet8-原因汇总", 100)
    return reason_summary_df
