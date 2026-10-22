# -*- coding: utf-8 -*-
"""
_dbg_trae.py — v43.157 分厂版(TRAE版)PPT 端到端验证

跑法（需带 pandas + python-pptx 的解释器）：
    "C:/Users/Administrator/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" _dbg_trae.py

覆盖 T1~T7：
  T1 9 页结构 + 页面顺序 + 页脚编号
  T2 数据实时性：所有关键数字都能从「汇总统计」表对上（含车间数 9+7=16 口径）
  T3 与 TRAE 硬编码基准逐值对照（换数据表数字必须跟着变）
  T4 原因页标签已改为「净偏差数量」（不再谎称金额）
  T5 容错：只有食品厂数据 / 无原因表 / 只有原料分类 都不崩且出说明页
  T6 失败路径：原始导入表(只有 Data sheet) 给中文可执行提示，log_cb 不被 TypeError 顶掉
  T7 幂等：同输入连续两次生成，页数与页序完全一致
  T8 入口改造：菜单文案已改、export_controller 指向 ppt_trae、两入口不再同一函数
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from pptx import Presentation

from core.ppt_trae import generate_trae_report, build_dataset, DataError

SRC = r'E:/Users/Administrator/Desktop/ZPP011偏差分析最终版_20261004_164358.xlsx'
OUTDIR = r'C:/Temp/ppt_trae_out'
RAW = r'E:/ZPP011导出文件原数据/前期/ZPP011_20260901-20260930.xlsx'  # 只有 Data sheet

PASS, FAIL = [], []


def ck(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  [PASS] ' if cond else '  [FAIL] ') + name + (
        ('  -> ' + detail) if detail else ''))


def texts_of(slide):
    return [sh.text_frame.text for sh in slide.shapes
            if sh.has_text_frame and sh.text_frame.text.strip()]


def make(src, out):
    logs = []
    ok = generate_trae_report(src, out, log_cb=lambda m, l='info': logs.append((l, m)))
    return ok, logs


os.makedirs(OUTDIR, exist_ok=True)

# ---------------------------------------------------------------- T1 结构
print('\n=== T1 9 页结构 ===')
out1 = os.path.join(OUTDIR, 't1.pptx')
ok, logs = make(SRC, out1)
ck('T1.1 生成成功', ok, str(logs))
prs = Presentation(out1)
ck('T1.2 恰好 9 页', len(prs.slides) == 9, f'实际 {len(prs.slides)}')
ck('T1.3 16:9 (13.333x7.5in)',
   abs(prs.slide_width.inches - 13.333) < 0.01 and
   abs(prs.slide_height.inches - 7.5) < 0.01,
   f'{prs.slide_width.inches:.3f}x{prs.slide_height.inches:.3f}')
titles = [' | '.join(texts_of(s)[:1]) for s in prs.slides]
want = ['云南达利食品', '目录', '总体概览', '食品厂专题', '食品厂专题',
        '饮料厂专题', '饮料厂专题', '预警对比', '谢谢']
for i, (t, w) in enumerate(zip(titles, want)):
    ck(f'T1.4 P{i+1} 是「{w}」页', w in t, t[:40])
# 页脚编号：TRAE 原版封面(P1)与结尾(P9)本就无 footer，中间 7 页才有
for i, s in enumerate(prs.slides):
    if i in (0, len(prs.slides) - 1):
        continue
    ck(f'T1.5 P{i+1} 页脚编号 {i+1:02d}',
       any(f'{i+1:02d}' == t.strip() for t in texts_of(s)))
ck('T1.5b 结尾页沿用 TRAE 原版：无页脚（与原脚本一致）',
   not any(t.strip() == '09' for t in texts_of(list(prs.slides)[8])))
ck('T1.6 无空白页（每页至少 1 个文本）',
   all(len(texts_of(s)) > 0 for s in prs.slides))
all_text = '\n'.join(t for s in prs.slides for t in texts_of(s))
ck('T1.7 无 nan / None / inf 泄漏',
   'nan' not in all_text.lower() and 'None' not in all_text
   and 'inf' not in all_text.lower().replace('info', ''))

# ---------------------------------------------------------------- T2 数据
print('\n=== T2 数据实时性（对「汇总统计」表） ===')
D = build_dataset(SRC)
sm = pd.read_excel(SRC, sheet_name='汇总统计')
amt = float(pd.to_numeric(sm['总偏差金额(含税)'], errors='coerce').sum())
cnt = int(pd.to_numeric(sm['总条数'], errors='coerce').sum())
ck('T2.1 总净偏差 = 汇总统计求和',
   abs(D['total']['amt_wan'] - amt / 1e4) < 0.005,
   f"{D['total']['amt_wan']} vs {amt/1e4:.2f}")
ck('T2.2 总条数 = 汇总统计求和', D['total']['cnt'] == cnt,
   f"{D['total']['cnt']} vs {cnt}")
ws_sum = int(sum(s['车间'].nunique() for _, s in sm.groupby('工厂名称')))
ck('T2.3 车间数 = 各厂相加(9+7=16，不是全局去重15)',
   D['total']['workshops'] == ws_sum == 16, str(D['total']['workshops']))
ck('T2.4 两厂车间数相加等于总数',
   D['food']['workshops'] + D['bev']['workshops'] == D['total']['workshops'],
   f"{D['food']['workshops']}+{D['bev']['workshops']}")
for key, kw in (('food', '食品'), ('bev', '饮料')):
    sub = sm[sm['工厂名称'].astype(str).str.contains(kw, na=False)]
    a = float(pd.to_numeric(sub['总偏差金额(含税)'], errors='coerce').sum()) / 1e4
    ck(f'T2.5 {key} 净偏差 = 该厂求和',
       abs(D[key]['amt_wan'] - a) < 0.005, f"{D[key]['amt_wan']} vs {a:.2f}")
    ck(f'T2.6 {key} 条数 = 该厂求和',
       D[key]['cnt'] == int(pd.to_numeric(sub['总条数'], errors='coerce').sum()))
    vc = sub['预警'].astype(str).value_counts()
    exp = {k: int(vc[[i for i in vc.index if k in i]].sum())
           for k in ('红色预警', '黄色预警', '绿色预警')}
    ck(f'T2.7 {key} 预警红黄绿', D[key]['alerts'] == exp,
       f"{D[key]['alerts']} vs {exp}")
# 车间排名：负偏差绝对值降序 TOP8
for key, kw in (('food', '食品'), ('bev', '饮料')):
    sub = sm[sm['工厂名称'].astype(str).str.contains(kw, na=False)]
    g = (sub.groupby('车间')['总偏差金额(含税)'].sum().reset_index())
    g = g[g['总偏差金额(含税)'] < 0].assign(a=lambda x: x['总偏差金额(含税)'].abs())
    g = g.sort_values('a', ascending=False).head(8)
    ck(f'T2.8 {key} 车间排名顺序与绝对值降序一致',
       [r['车间'] for _, r in g.iterrows()] == [n for n, _ in D[key]['workshop_top']],
       f"{[n for n,_ in D[key]['workshop_top']][:4]}")
    ck(f'T2.9 {key} 车间排名值为负且带 2 位小数',
       all(v < 0 for _, v in D[key]['workshop_top']) and
       all(round(v, 2) == v for _, v in D[key]['workshop_top']))
# 分类
for key, kw in (('food', '食品'), ('bev', '饮料')):
    sub = sm[sm['工厂名称'].astype(str).str.contains(kw, na=False)]
    g = (sub.groupby('物料分类')['总偏差金额(含税)'].sum().reset_index()
           .sort_values('总偏差金额(含税)'))
    ck(f'T2.10 {key} 物料分类顺序',
       [r['物料分类'] for _, r in g.iterrows()] ==
       [c['name'] for c in D[key]['categories']],
       str([c['name'] for c in D[key]['categories']]))
# 原因
rs = pd.read_excel(SRC, sheet_name='偏差原因分析')
for key, kw in (('food', '食品'), ('bev', '饮料')):
    sub = rs[rs['工厂'].astype(str).str.contains(kw, na=False)]
    g = sub.groupby('备注原因')['净偏差数量'].sum().reset_index(name='q')
    g = g.assign(a=lambda x: x['q'].abs()).sort_values('a', ascending=False).head(6)
    ck(f'T2.11 {key} 原因 TOP6 与源表一致',
       [(r['备注原因'], round(r['q'] / 1e4, 2)) for _, r in g.iterrows()] ==
       D[key]['reasons'], f"{[n for n,_ in D[key]['reasons']][:3]}")
ck('T2.12 日期范围来自分析说明表', '2026-09-01' in D['range'], D['range'])
ck('T2.13 阈值来自分析说明表', '10' in D['threshold'], D['threshold'])
ck('T2.14 month 由 range 推导', D['month'] == '2026 年 9 月', D['month'])

# ---------------------------------------------------------------- T3 基准
print('\n=== T3 与 TRAE 硬编码基准对照 ===')
BENCH = [
    ('总净偏差', D['total']['amt_wan'], -446.4, 0.1),
    ('总条数', D['total']['cnt'], 17647, 0),
    ('食品净偏差', D['food']['amt_wan'], -201.7, 0.1),
    ('饮料净偏差', D['bev']['amt_wan'], -244.8, 0.1),
    ('食品正偏差', D['food']['pos_wan'], 184.9, 0.1),
    ('食品负偏差', D['food']['neg_wan'], -207.2, 0.1),
    ('饮料正偏差', D['bev']['pos_wan'], 64.6, 0.1),
    ('饮料负偏差', D['bev']['neg_wan'], -77.9, 0.1),
    ('食品条数', D['food']['cnt'], 16468, 0),
    ('饮料条数', D['bev']['cnt'], 1179, 0),
    ('食品车间数', D['food']['workshops'], 9, 0),
    ('饮料车间数', D['bev']['workshops'], 7, 0),
    ('涉及车间数', D['total']['workshops'], 16, 0),
    ('食品备注覆盖率', D['food']['cov'], 32.8, 0.05),
    ('饮料备注覆盖率', D['bev']['cov'], 27.1, 0.05),
]
for name, got, exp, tol in BENCH:
    ck(f'T3 {name} ≈ {exp}', abs(got - exp) <= tol, f'实得 {got}')
ck('T3 食品预警 11/3/2',
   D['food']['alerts'] == {'红色预警': 11, '黄色预警': 3, '绿色预警': 2})
ck('T3 饮料预警 9/3/5',
   D['bev']['alerts'] == {'红色预警': 9, '黄色预警': 3, '绿色预警': 5})
ck('T3 食品原材料 -207.4 万',
   abs([c for c in D['food']['categories'] if c['name'] == '原材料'][0]['amt_wan']
       - (-207.4)) < 0.1)
ck('T3 饮料半成品 -237.2 万',
   abs([c for c in D['bev']['categories'] if c['name'] == '半成品'][0]['amt_wan']
       - (-237.2)) < 0.1)
ck('T3 食品首要根因「定额/系统问题」79.8 万',
   D['food']['reasons'][0] == ('定额/系统问题', 79.8), str(D['food']['reasons'][0]))
ck('T3 饮料首要原因「替代料」1.6 万',
   D['bev']['reasons'][0][0] == '替代料', str(D['bev']['reasons'][0]))

# ---------------------------------------------------------------- T4 标签
print('\n=== T4 原因页标签已改为「净偏差数量」 ===')
cat_txt = '\n'.join(texts_of(Presentation(out1).slides[4]) +
                    texts_of(Presentation(out1).slides[6]))
ck('T4.1 原因页标题含「净偏差数量」', '偏差原因' in cat_txt and
   '净偏差数量' in cat_txt, '')
ck('T4.2 不再出现「偏差原因 TOP (按净偏差金额)」',
   '偏差原因 TOP (按净偏差金额)' not in cat_txt)
ck('T4.3 分类页仍标「净偏差金额」', '按物料分类 · 净偏差金额' in cat_txt)

# ---------------------------------------------------------------- T5 容错
print('\n=== T5 容错 ===')
# 5.1 只有食品厂
only = pd.read_excel(SRC, sheet_name='汇总统计')
only = only[only['工厂名称'].astype(str).str.contains('食品')]
tmp = os.path.join(OUTDIR, 'only_food.xlsx')
with pd.ExcelWriter(tmp, engine='openpyxl') as w:
    only.to_excel(w, sheet_name='汇总统计', index=False)
o = os.path.join(OUTDIR, 't5_food.pptx')
ok, logs = make(tmp, o)
ck('T5.1 只有食品厂也生成成功', ok, str(logs[-1:]))
D5 = build_dataset(tmp)
ck('T5.2 饮料厂标记为无数据', D5['bev']['has_data'] is False)
ck('T5.3 仍为 9 页（不缩页）', len(Presentation(o).slides) == 9,
   str(len(Presentation(o).slides)))
t5 = '\n'.join(t for s in Presentation(o).slides for t in texts_of(s))
ck('T5.4 饮料厂页出现「本期无数据」', '本期无数据' in t5)
ck('T5.5 车间数只算食品厂', D5['total']['workshops'] == 9,
   str(D5['total']['workshops']))
# 5.2 无原因表：用一个只保留必要 sheet 的干净工作簿
#     （不能整本重写 —— openpyxl 写不出 emoji 名的「📋 分析说明」，
#     且部分 sheet 会被 pandas 判为不可见，出现 "At least one sheet must be visible"）
import shutil
nor = os.path.join(OUTDIR, 'no_reason.xlsx')
xl = pd.ExcelFile(SRC)
keep = [sh for sh in xl.sheet_names if sh != '偏差原因分析']
try:
    with pd.ExcelWriter(nor, engine='openpyxl') as w:
        pd.read_excel(SRC, sheet_name='汇总统计').to_excel(
            w, sheet_name='汇总统计', index=False)
    o5 = os.path.join(OUTDIR, 't5_noreason.pptx')
    ok, logs = make(nor, o5)
    ck('T5.6 缺「偏差原因分析」表不崩', ok, str(logs[-1:]))
    ck('T5.7 仍为 9 页', len(Presentation(o5).slides) == 9)
    D5n = build_dataset(nor)
    ck('T5.7b 两厂原因均为空列表',
       D5n['food']['reasons'] == [] and D5n['bev']['reasons'] == [])
    ck('T5.7c 两厂数据仍正常', D5n['food']['cnt'] == 16468)
    t5b = '\n'.join(t for s in Presentation(o5).slides for t in texts_of(s))
    ck('T5.8 原因区给出兜底文案', '缺少可归因的备注' in t5b or '本期无原因归因数据' in t5b)
except Exception as e:
    ck('T5.6 缺「偏差原因分析」表不崩', False, repr(e))
    traceback.print_exc()
# 5.3 汇总统计缺列
bad = os.path.join(OUTDIR, 'bad.xlsx')
with pd.ExcelWriter(bad, engine='openpyxl') as w:
    only[['工厂名称', '车间']].to_excel(w, sheet_name='汇总统计', index=False)
try:
    build_dataset(bad)
    ck('T5.9 缺列时抛 DataError（而非其它异常）', False, '没抛')
except DataError as e:
    ck('T5.9 缺列时抛 DataError 且提示可执行', '缺少必要列' in str(e), str(e)[:60])
except Exception as e:
    ck('T5.9 缺列时抛 DataError（而非其它异常）', False, type(e).__name__)

# ---------------------------------------------------------------- T6 失败
print('\n=== T6 失败路径 ===')
if os.path.exists(RAW):
    o6 = os.path.join(OUTDIR, 't6.pptx')
    ok, logs = make(RAW, o6)
    ck('T6.1 原始导入表生成失败', ok is False)
    err = '\n'.join(m for l, m in logs if l == 'error')
    ck('T6.2 提示中文可执行', '汇总统计' in err and '完整分析报告' in err, err[:90])
    ck('T6.3 日志里无 TypeError（回调未被顶掉）', 'TypeError' not in err, err[:90])
    ck('T6.4 未产出文件', not os.path.exists(o6))
else:
    print('  [SKIP] 原始导入表不存在，跳过 T6')

# 只传 1 个参数的 log_cb（GUI 签名是 (msg, level)）
o6b = os.path.join(OUTDIR, 't6b.pptx')
try:
    ok = generate_trae_report(SRC, o6b, log_cb=lambda m: None)
    ck('T6.5 单参 log_cb 不炸（降级成功）', ok is True)
except Exception as e:
    ck('T6.5 单参 log_cb 不炸（降级成功）', False, repr(e))
o6c = os.path.join(OUTDIR, 't6c.pptx')
try:
    ok = generate_trae_report(RAW, o6c,
                              log_cb=lambda m, l='info': (_ for _ in ()).throw(TypeError('x')))
    ck('T6.6 log_cb 自身抛异常也不炸', ok is False)
except Exception as e:
    ck('T6.6 log_cb 自身抛异常也不炸', False, repr(e))

# ---------------------------------------------------------------- T7 幂等
print('\n=== T7 幂等 ===')
oa = os.path.join(OUTDIR, 't7a.pptx')
ob = os.path.join(OUTDIR, 't7b.pptx')
make(SRC, oa)
make(SRC, ob)
pa, pb = Presentation(oa), Presentation(ob)
ck('T7.1 两次页数一致', len(pa.slides) == len(pb.slides) == 9)
same = all([t for t in texts_of(x)] == [t for t in texts_of(y)]
           for x, y in zip(pa.slides, pb.slides))
ck('T7.2 每页文本完全一致', same)
# 注意：pptx 整体字节数**本就不该**相等 —— python-pptx 每次保存都往 zip
# 条目写当前时间戳（图表内嵌的 xlsx 同理），差几字节属正常。
# 真正的幂等判据是「除图表内嵌 workbook 外，所有 zip 条目内容逐字节一致」。
import zipfile
za, zb = zipfile.ZipFile(oa), zipfile.ZipFile(ob)
ck('T7.3 zip 条目集合一致', set(za.namelist()) == set(zb.namelist()),
   f'{len(za.namelist())} vs {len(zb.namelist())}')
skip = ('ppt/embeddings/',)          # 图表内嵌 xlsx：含自身 zip 时间戳
diff = [n for n in za.namelist()
        if not n.startswith(skip) and za.read(n) != zb.read(n)]
ck('T7.4 除图表内嵌 xlsx 外，所有条目逐字节一致', not diff, str(diff[:3]))
ck('T7.5 字节差仅来自时间戳（差异 < 1KB）',
   abs(os.path.getsize(oa) - os.path.getsize(ob)) < 1024,
   f'{os.path.getsize(oa)} vs {os.path.getsize(ob)}')

# ---------------------------------------------------------------- T8 入口
print('\n=== T8 入口改造 ===')
mb = open('gui_pyside6/components/menu_bar.py', encoding='utf-8').read()
ck('T8.1 菜单已是「分厂版(9页)」', 'QAction("分厂版(9页)"' in mb)
ck('T8.2 旧文案「简明版」已清除', 'QAction("简明版"' not in mb)
ck('T8.3 分厂版仍连 _generate_smart_ppt_simple',
   'smart_simple_action.triggered.connect(self.mw._generate_smart_ppt_simple)' in mb)
ec = open('gui_pyside6/controllers/export_controller.py', encoding='utf-8').read()
ck('T8.4 控制器 import ppt_trae', 'from core.ppt_trae import generate_trae_report' in ec)
ck('T8.5 分厂版不再调 advanced(mode="simple")',
   'generate_trae_report(excel_path, output_path, log_cb=log_cb)' in ec)
ck('T8.6 专业版仍走 advanced mode="pro"',
   'generate_advanced_report_v2(\n                excel_path, output_path, '
   'log_cb=log_cb, mode="pro")' in ec)
ck('T8.7 输出文件名改为分厂报告', 'ZPP011分厂报告_' in ec)
mw = open('gui_pyside6/main_window.py', encoding='utf-8').read()
ck('T8.8 main_window docstring 已同步', '分厂版(9页)' in mw)
vh = open('utils/version_history.py', encoding='utf-8').read()
ck('T8.9 版本号已升到 v43.157', '"version": "v43.157"' in vh)

# 两入口产出确实不同
try:
    from core.advanced_ppt_generator_v2 import generate_advanced_report_v2
    opro = os.path.join(OUTDIR, 'pro.pptx')
    generate_advanced_report_v2(SRC, opro, mode='pro')
    n_trae = len(Presentation(out1).slides)
    n_pro = len(Presentation(opro).slides)
    ck('T8.10 分厂版(9页) 与 专业版 页数不同', n_trae != n_pro, f'{n_trae} vs {n_pro}')
    ck('T8.11 分厂版字节数与专业版不同',
       os.path.getsize(out1) != os.path.getsize(opro))
except Exception as e:
    ck('T8.10 两入口产出不同', False, repr(e))

# ---------------------------------------------------------------- 汇总
print('\n' + '=' * 60)
print(f'PASS {len(PASS)} / FAIL {len(FAIL)}')
if FAIL:
    print('\n失败项：')
    for f in FAIL:
        print('  - ' + f)
print('=' * 60)
sys.exit(1 if FAIL else 0)
