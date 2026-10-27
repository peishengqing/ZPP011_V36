# 导出报表分层改造 · 一期（v43.283）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按规格 `docs/superpowers/specs/2026-10-27-export-report-layered-design.md` 一期范围：偏差等级列（唯一业务例外）+ 驾驶舱升级（Top5车间/Top10物料/周趋势图）+ 数据层降噪 + 视觉统一（页签色/说明行/数据条）。

**Architecture:** 呈现层改动全部进 `analysis/excel_builder/post_process.py`（挂 `decorate_workbook` 流水线，各自 try/except 独立降级）；偏差等级列进 `analysis/excel_builder/sheet5_full.py`（dev_df 构建处，GUI 主表与导出天然共用单一事实源）+ `analysis/analyzer.py` ws5 硬编码列清单同步。环比与派活页增强不在本期（二期）。

**Tech Stack:** openpyxl（DataBarRule/ColorScaleRule/BarChart）、pandas、pytest。

**规格修正（写计划时确认）：** 规格 §2.1 写"位置 analyzer.py"，实际落点应为 `sheet5_full.build_sheet5`（dev_df 在此构建，analyzer 只是把 dev_df 按硬编码 headers5 写进 ws5）。GUI 主表显示的就是 dev_df，所以加在这里即满足"软件/导出同一列"。

**运行环境（本机特有）：**
- 项目 Python：直接 `python`（PATH 里的 3.11，含 PySide6 6.11.1 / openpyxl 3.1.5 / pandas 3.0.1）
- 测试：`python -m pytest tests/unit -q --no-cov`（cwd=E:\zpp011_v2，需 `$env:QT_QPA_PLATFORM='offscreen'`）
- 生成验证：`python -B -X utf8 work\gen_check.py`（Task 0 创建）
- 提交规范：`@v43.28x 一句话`（裴哥风格，git 在 E:\zpp011_v2）
- 版本号：每完成一个阶段任务，更新 `utils/version_history.py` 顶部（当前 v43.282）

---

### Task 0: 回归 diff 工具（先建防线，后动刀）

**Files:**
- Create: `work/gen_check.py`（一次性，不提交）
- Create: `work/diff_workbooks.py`（一次性，不提交）
- Baseline: `work/baseline_20261022.xlsx`（当前代码生成的基准）

- [ ] **Step 1: 用当前代码（改动前）生成基准文件**

```python
# work/gen_check.py
# -*- coding: utf-8 -*-
import os, sys, json, glob
ROOT = r"E:\zpp011_v2"
sys.path.insert(0, ROOT)
alt_pairs = json.load(open(os.path.join(ROOT, "zpp011_alt_pairs.json"), encoding="utf-8"))
from analysis.analyzer import do_analysis_v2
src = r"E:\ZPP011导出文件原数据\ZPP011_20261001-20261022.xlsx"
out_dir = sys.argv[1]
os.makedirs(out_dir, exist_ok=True)
do_analysis_v2(src, out_dir, alt_pairs, progress_callback=lambda *a: None, dyn_thresh=10.0)
print("generated:", sorted(glob.glob(os.path.join(out_dir, "ZPP011偏差分析最终版_*.xlsx")))[-1])
```

Run: `python -B -X utf8 work\gen_check.py work\base_out`
Expected: 生成成功，复制为 `work/baseline_20261022.xlsx`

- [ ] **Step 2: 写数值 diff 工具**

```python
# work/diff_workbooks.py
# -*- coding: utf-8 -*-
"""逐格数值 diff：白名单=（新增 sheet、新增列、说明/格式类改动）。
用法: python diff_workbooks.py A.xlsx B.xlsx [允许新增的sheet名,逗号分隔]"""
import sys
from openpyxl import load_workbook
a = load_workbook(sys.argv[1], data_only=True)
b = load_workbook(sys.argv[2], data_only=True)
allow_new_sheets = set((sys.argv[3] if len(sys.argv) > 3 else "").split(",")) - {""}
diffs = 0
for name in a.sheetnames:
    if name not in b.sheetnames:
        print(f"[SHEET缺失] {name}"); diffs += 1; continue
    wa, wb_ = a[name], b[name]
    hmax = max(wa.max_row, wb_.max_row)
    cmax = max(wa.max_column, wb_.max_column)
    for r in range(1, hmax + 1):
        for c in range(1, cmax + 1):
            va = wa.cell(r, c).value
            vb = wb_.cell(r, c).value
            if va == vb:
                continue
            # 允许：B 在行尾新增列（A 该格为空且 r==1 表头行或整列为空）
            if va in (None, "") and c > wa.max_column:
                continue
            if diffs < 50:
                print(f"[DIFF] {name} R{r}C{c}: {va!r} -> {vb!r}")
            diffs += 1
for name in b.sheetnames:
    if name not in a.sheetnames and name not in allow_new_sheets:
        print(f"[SHEET新增未白名单] {name}"); diffs += 1
print("TOTAL DIFFS:", diffs)
sys.exit(1 if diffs else 0)
```

Run: `python -B -X utf8 work\diff_workbooks.py work\base_out\*.xlsx work\base_out\*.xlsx`
Expected: `TOTAL DIFFS: 0`（自反校验工具正确性）

---

### Task 1: 偏差等级列（唯一业务层例外）

**Files:**
- Modify: `analysis/excel_builder/sheet5_full.py`（build_sheet5，约 :114 偏差区间旁）
- Modify: `analysis/analyzer.py:917-929`（ws5 headers5/rows5 加列）
- Modify: `analysis/analyzer.py:1115-1116`（分析说明文案）
- Test: `tests/unit/test_dev_grade.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_dev_grade.py
# -*- coding: utf-8 -*-
"""偏差等级列分档测试（规格 §2.1）：|率|>50 严重 / 10~50 一般 / <10 轻微 / 空 —。"""
import os, sys
import pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from analysis.excel_builder.sheet5_full import dev_grade

def test_grade_boundaries():
    assert dev_grade(9.99) == "轻微"
    assert dev_grade(10.0) == "一般"    # 10 归一般（含边界）
    assert dev_grade(50.0) == "一般"    # 50 归一般（>50 才严重）
    assert dev_grade(50.01) == "严重"
    assert dev_grade(-100.0) == "一般"  # 钳位标记按绝对值分档
    assert dev_grade(100.0) == "一般"

def test_grade_signed_and_none():
    assert dev_grade(-60.5) == "严重"
    assert dev_grade(0.0) == "轻微"
    assert dev_grade(None) == "—"
    assert dev_grade(float("nan")) == "—"
    assert dev_grade("abc") == "—"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -B -m pytest tests/unit/test_dev_grade.py -q --no-cov`
Expected: FAIL（ImportError: dev_grade）

- [ ] **Step 3: 实现 dev_grade + 接入 build_sheet5**

`sheet5_full.py` 顶部（import 后）加：

```python
# 偏差等级分档（规格 2026-10-27 §2.1 唯一业务例外；阈值单一来源，
# 业务要调只改这一行。边界语义：10 与 50 含在「一般」档。）
GRADE_BOUNDS = (10.0, 50.0)


def dev_grade(rate_pct):
    """按 |偏差率(%)|（百分点）分档：>50 严重 / 10~50 一般 / <10 轻微 / 非数值 —。
    ±100 钳位标记行按绝对值入档（本就是最需要人看的行，不做特判）。"""
    try:
        v = abs(float(rate_pct))
    except (TypeError, ValueError):
        return "—"
    if pd.isna(v):
        return "—"
    lo, hi = GRADE_BOUNDS
    if v > hi:
        return "严重"
    if v >= lo:
        return "一般"
    return "轻微"
```

`build_sheet5` 内 `dev_df['偏差区间'] = ...`（:114）之后加：

```python
        # 偏差等级列（v43.283，规格 §2.1）：GUI 主表与完整偏差明细共用
        dev_df['偏差等级'] = has_real_dev[col_p].map(dev_grade)
```

空表防御分支（:71-77 的 columns=[...]）同步在 `'偏差区间',` 后加 `'偏差等级',`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -B -m pytest tests/unit/test_dev_grade.py -q --no-cov`
Expected: 2 passed

- [ ] **Step 5: analyzer ws5 写表清单加列**

`analyzer.py:920` headers5 末尾 `'偏差区间'` 后加 `'偏差等级'`；
`analyzer.py:927` rows5 推导式 `r['偏差区间'],` 后加 `r.get('偏差等级', '—'),`；
`analyzer.py:929` widths 列表末尾加 `10`。
分析说明 :1115-1116「完整偏差明细」文案末尾追加
`。含「偏差等级」列：|偏差率|>50% 严重 / 10~50% 一般 / <10% 轻微`。

- [ ] **Step 6: GUI 主表列顺序确认**

`gui_pyside6/services/data_service.py` 的 `_reorder_columns`：若维护了显式列序清单，把 `偏差等级` 排在 `偏差区间` 之后（先读该函数确认结构再改）。GUI 显示 dev_df 全列，新列自动出现，此步只调顺序。

- [ ] **Step 7: 端到端 + diff 白名单验证**

Run: `python -B -X utf8 work\gen_check.py work\p1_out`
Run: `python -B -X utf8 work\diff_workbooks.py work\base_out\<file> work\p1_out\<file>`
Expected: diff 仅出现在「完整偏差明细」最后一列新增（工具按列新增豁免）+ 分析说明文案行；其余 TOTAL DIFFS 与豁免项一致。人工核对：新列值域 ⊆ {严重,一般,轻微,—}。

- [ ] **Step 8: Commit**

```bash
git add analysis/excel_builder/sheet5_full.py analysis/analyzer.py gui_pyside6/services/data_service.py tests/unit/test_dev_grade.py
git commit -m "@v43.283a 偏差等级列（|率|>50严重/10~50一般/<10轻微，规格§2.1唯一业务例外，GUI与导出共用）"
```

---

### Task 2: 驾驶舱升级（Top5 车间 / Top10 物料 / 周趋势 / 数据条）

**Files:**
- Modify: `analysis/excel_builder/post_process.py`（`_add_dashboard` :671-840 扩展）
- Test: `tests/unit/test_dashboard_upgrade.py`

- [ ] **Step 1: 写失败测试（offscreen 不需要，openpyxl 纯内存）**

```python
# tests/unit/test_dashboard_upgrade.py
# -*- coding: utf-8 -*-
"""驾驶舱升级断言（规格 §3）：Top5车间/Top10物料表存在且排序正确。"""
import os, sys
import pandas as pd
from openpyxl import Workbook
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from analysis.excel_builder.post_process import _upgrade_dashboard

def _mk_wb():
    wb = Workbook()
    ws = wb.active; ws.title = "汇总统计"
    ws.append(["序号", "工厂", "车间", "物料分类", "总条数", "总偏差金额(含税)", "备注覆盖率"])
    for i, (wsname, amt) in enumerate([("A线", -500.0), ("B线", 300.0), ("C线", -1200.0),
                                        ("D线", 50.0), ("E线", -70.0), ("F线", 900.0)]):
        ws.append([i + 1, "食品厂", wsname, "包材", 10, amt, 0.5])
    ws2 = wb.create_sheet("完整偏差明细")
    ws2.append(["物料编码", "物料名称", "偏差金额"])
    for j in range(12):
        ws2.append([f"M{j:03d}", f"物料{j}", -(j + 1) * 100.0])
    # 驾驶舱页由 _add_dashboard 建；_upgrade_dashboard 对不存在页直接短路，
    # 测试须先建空页模拟"已建页后升级"场景。
    wb.create_sheet("📊 驾驶舱")
    return wb

def test_upgrade_dashboard_tables():
    wb = _mk_wb()
    _upgrade_dashboard(wb)
    dash = wb["📊 驾驶舱"]
    text = [str(c.value) for row in dash.iter_rows() for c in row if c.value]
    assert any("Top 5 车间" in t for t in text), "缺 Top5 车间表"
    assert any("Top 10 物料" in t for t in text), "缺 Top10 物料表"
    # C线(-1200) 应排 F线(900) 之前（按|金额|降序）
    vals = [c.value for row in dash.iter_rows() for c in row]
    assert vals.index("C线") < vals.index("F线")
    assert dash.sheet_properties.tabColor is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -B -m pytest tests/unit/test_dashboard_upgrade.py -q --no-cov`
Expected: FAIL（ImportError: _upgrade_dashboard）

- [ ] **Step 3: 实现 `_upgrade_dashboard`**

post_process.py 驾驶舱区（`_add_dashboard` 后）新增。**设计**：`_add_dashboard` 建页后调用 `_upgrade_dashboard(wb)`（对已存在页幂等：先清 B16 以下再重写）。核心逻辑：

```python
def _upgrade_dashboard(wb):
    """v43.283 规格 §3：驾驶舱补 Top5 车间表 / Top10 物料表（帕累托）+ 页签色。
    只读「汇总统计」「完整偏差明细」两页派生呈现，零口径计算。幂等：重复调用先清后写。"""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.formatting.rule import DataBarRule
    name = '📊 驾驶舱'
    if name not in wb.sheetnames:
        return 0
    ws = wb[name]
    ws.sheet_properties.tabColor = '2E7D32'   # 结论层=绿（规格 §6）
    _thin = Side(style='thin', color='CCCCCC')
    _bd = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
    # 幂等：清第 16 行以下旧内容（KPI 与图在 1-15 行区，由 _add_dashboard 维护）
    if ws.max_row > 15:
        ws.delete_rows(16, ws.max_row - 15)

    row = 16
    # ── Top 5 车间（|总偏差金额| 降序）──
    ws.cell(row=row, column=2, value='Top 5 车间（按 |偏差金额| 降序）').font = Font(bold=True, size=11)
    row += 1
    hdr = ['车间', '总条数', '总偏差金额(含税)', '备注覆盖率']
    for j, h in enumerate(hdr):
        c = ws.cell(row=row, column=2 + j, value=h)
        c.font = Font(bold=True, size=10); c.border = _bd
    row += 1
    top5_start = row
    if '汇总统计' in wb.sheetnames:
        src = wb['汇总统计']
        h_row, hds = _header_info(src)
        l_row = _last_data_row(src, h_row)
        c_ws = _find_col(hds, '车间'); c_cnt = _find_col(hds, '总条数')
        c_amt = _find_col(hds, '总偏差金额(含税)'); c_cov = _find_col(hds, '备注覆盖率')
        recs = []
        for r in range(h_row + 1, l_row + 1):
            amt = src.cell(r, c_amt).value if c_amt else None
            if isinstance(amt, (int, float)):
                recs.append((src.cell(r, c_ws).value if c_ws else '',
                             src.cell(r, c_cnt).value if c_cnt else '',
                             amt,
                             src.cell(r, c_cov).value if c_cov else ''))
        recs.sort(key=lambda x: -abs(x[2]))
        for w, cnt, amt, cov in recs[:5]:
            ws.cell(row=row, column=2, value=w).border = _bd
            ws.cell(row=row, column=3, value=cnt).border = _bd
            ca = ws.cell(row=row, column=4, value=round(amt, 2))
            ca.number_format = '#,##0.00'; ca.border = _bd
            cc = ws.cell(row=row, column=5, value=cov)
            if isinstance(cov, (int, float)):
                cc.number_format = '0%'
            cc.border = _bd
            row += 1
    # 金额列数据条（量级一眼可辨）
    if row > top5_start:
        ws.conditional_formatting.add(
            'D%d:D%d' % (top5_start, row - 1),
            DataBarRule(start_type='min', end_type='max', color='C62828'))
    row += 2

    # ── Top 10 物料（帕累托：按 |偏差金额| 聚合降序 + 累计占比）──
    ws.cell(row=row, column=2, value='Top 10 物料（按 |偏差金额| 降序，含累计占比）').font = Font(bold=True, size=11)
    row += 1
    for j, h in enumerate(['物料编码', '物料名称', '偏差金额', '占总额比', '累计占比']):
        c = ws.cell(row=row, column=2 + j, value=h)
        c.font = Font(bold=True, size=10); c.border = _bd
    row += 1
    m_start = row
    if '完整偏差明细' in wb.sheetnames:
        src = wb['完整偏差明细']
        h_row, hds = _header_info(src)
        l_row = _last_data_row(src, h_row)
        c_code = _find_col(hds, '物料编码'); c_name = _find_col(hds, '物料名称')
        c_amt = _find_col(hds, '偏差金额')
        agg = {}
        for r in range(h_row + 1, l_row + 1):
            amt = src.cell(r, c_amt).value if c_amt else None
            if not isinstance(amt, (int, float)):
                continue
            code = str(src.cell(r, c_code).value or '') if c_code else ''
            if code not in agg:
                agg[code] = [src.cell(r, c_name).value if c_name else '', 0.0]
            agg[code][1] += amt
        total_abs = sum(abs(v[1]) for v in agg.values()) or 1.0
        top = sorted(agg.items(), key=lambda kv: -abs(kv[1][1]))[:10]
        cum = 0.0
        for code, (nm, amt) in top:
            share = abs(amt) / total_abs
            cum += share
            ws.cell(row=row, column=2, value=code).border = _bd
            ws.cell(row=row, column=3, value=nm).border = _bd
            ca = ws.cell(row=row, column=4, value=round(amt, 2))
            ca.number_format = '#,##0.00'; ca.border = _bd
            cs = ws.cell(row=row, column=5, value=round(share, 4))
            cs.number_format = '0.0%'; cs.border = _bd
            cu = ws.cell(row=row, column=6, value=round(cum, 4))
            cu.number_format = '0.0%'; cu.border = _bd
            row += 1
        if top:
            ws.cell(row=row, column=2,
                    value='前 10 合计占比 %.1f%%' % (cum * 100)).font = Font(bold=True, size=10)
            row += 1
    if row > m_start:
        ws.conditional_formatting.add(
            'D%d:D%d' % (m_start, row - 1),
            DataBarRule(start_type='min', end_type='max', color='C62828'))
    return 1
```

注：`_find_col` 返回列号可能为 None（缺列），上面每处 `c_xxx` 使用前已判 `if c_xxx else` 默认值；若 `_find_col` 返回 0 视为无（读现有实现确认）。

- [ ] **Step 4: 挂接 + 跑测试**

`decorate_workbook` 中 `_add_dashboard(wb)` 调用之后（:1378 附近）：

```python
            try:
                _upgrade_dashboard(wb)
            except Exception as e:
                _log('[post_process] 驾驶舱升级失败: %s' % e)
```

注意 `_add_dashboard` 的幂等短路（已存在则 return 0）——升级函数必须**独立于建页**被调用（老工作簿重开重装饰场景不存在，导出是一次性的，但 `_add_dashboard` 返回 0 时 `_upgrade_dashboard` 仍应执行——挂接位置在 if 之外）。

Run: `python -B -m pytest tests/unit/test_dashboard_upgrade.py -q --no-cov`
Expected: 1 passed

- [ ] **Step 5: 周趋势图（替换日级噪声）**

`_upgrade_dashboard` 末尾追加（读「趋势分析（自然日分组）」页的日期列聚合到 ISO 周）：

```python
    # ── 周趋势（自然周聚合替代日级：1077 行日级噪声大，周级看走向）──
    try:
        trend_name = '趋势分析（自然日分组）'
        if trend_name in wb.sheetnames:
            src = wb[trend_name]
            h_row, hds = _header_info(src)
            l_row = _last_data_row(src, h_row)
            c_date = _find_col(hds, '订单日期', '日期')
            c_amt = _find_col(hds, '偏差金额合计', '偏差金额')
            if c_date and c_amt:
                import pandas as _pd   # post_process 顶层无 pandas，周聚合就地 import
                weeks = {}
                for r in range(h_row + 1, l_row + 1):
                    dv = src.cell(r, c_date).value
                    av = src.cell(r, c_amt).value
                    if dv is None or not isinstance(av, (int, float)):
                        continue
                    iso = _pd.Timestamp(dv).isocalendar()
                    key = (int(iso[0]), int(iso[1]))
                    weeks[key] = weeks.get(key, 0.0) + av
                if weeks:
                    wr = 16
                    # 找一个空列区放周数据（右侧 R 列起，避免与左表冲突）
                    ws.cell(row=wr - 1, column=19, value='周趋势(ISO周)').font = Font(size=9, color='666666')
                    keys = sorted(weeks)
                    for i, k in enumerate(keys):
                        ws.cell(row=wr + i, column=19, value='%d-W%02d' % k)
                        ws.cell(row=wr + i, column=20, value=round(weeks[k], 2))
                    from openpyxl.chart import LineChart, Reference
                    ch = LineChart()
                    ch.title = '偏差金额 · 周趋势'
                    ch.height, ch.width = 7, 22
                    data = Reference(ws, min_col=20, min_row=wr, max_row=wr + len(keys) - 1)
                    cats = Reference(ws, min_col=19, min_row=wr, max_row=wr + len(keys) - 1)
                    ch.add_data(data, titles_from_data=False)
                    ch.set_categories(cats)
                    ws.add_chart(ch, 'P16')
    except Exception as e:
        _log('[post_process] 周趋势失败: %s' % e)
```

- [ ] **Step 6: 端到端 + diff**

Run: `python -B -X utf8 work\gen_check.py work\p2_out`
Run: `python -B -X utf8 work\diff_workbooks.py work\base_out\<file> work\p2_out\<file> "📊 驾驶舱"`
Expected: diff 仅驾驶舱页（结论页允许变）+ Task1 白名单项。打开文件人眼确认 Top5/Top10/周趋势图位置不互相重叠（重叠则调 row 起点常量，记入 Step 7 提交说明）。

- [ ] **Step 7: Commit**

```bash
git add analysis/excel_builder/post_process.py tests/unit/test_dashboard_upgrade.py
git commit -m "@v43.283b 驾驶舱升级：Top5车间/Top10物料(帕累托累计占比)/周趋势线图/数据条，绿页签"
```

---

### Task 3: 数据层降噪

**Files:**
- Modify: `analysis/excel_builder/post_process.py`（新函数 `_denoise_data_sheets`）
- Test: `tests/unit/test_denoise.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_denoise.py
# -*- coding: utf-8 -*-
"""数据层降噪（规格 §5）：汇总统计按|金额|降序重排 + 趋势页空白填—。"""
import os, sys
from openpyxl import Workbook
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from analysis.excel_builder.post_process import _resort_summary

def test_resort_summary_desc_by_abs_amount():
    wb = Workbook(); ws = wb.active; ws.title = "汇总统计"
    ws.append(["序号", "车间", "总偏差金额(含税)"])
    ws.append([1, "A", -500.0]); ws.append([2, "B", 300.0]); ws.append([3, "C", -1200.0])
    _resort_summary(wb)
    order = [ws.cell(r, 2).value for r in (2, 3, 4)]
    assert order == ["C", "A", "B"], order
    # 数值随行搬移：C 行金额仍是 -1200
    assert ws.cell(2, 3).value == -1200.0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -B -m pytest tests/unit/test_denoise.py -q --no-cov`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 `_resort_summary`（整行搬移含样式，不改值）**

```python
def _resort_summary(wb):
    """v43.283 规格 §5：「汇总统计」展示行按 |总偏差金额| 降序整行重排。
    只搬行（值+样式随行对象走 copy），数值零改动——序号列随行走，
    与「最痛在前」的阅读序一致（序号是原生成序，保留作对账锚点）。"""
    import copy as _copy
    name = '汇总统计'
    if name not in wb.sheetnames:
        return 0
    ws = wb[name]
    h_row, headers = _header_info(ws)
    last_row = _last_data_row(ws, h_row)
    c_amt = _find_col(headers, '总偏差金额(含税)')
    if not c_amt or last_row <= h_row + 1:
        return 0
    ncol = ws.max_column
    rows = []
    for r in range(h_row + 1, last_row + 1):
        cells = []
        for c in range(1, ncol + 1):
            src = ws.cell(r, c)
            cells.append((src.value, _copy.copy(src._style)))
        amt = ws.cell(r, c_amt).value
        rows.append((abs(amt) if isinstance(amt, (int, float)) else 0.0, cells))
    rows.sort(key=lambda x: -x[0])
    for i, (_, cells) in enumerate(rows):
        for c, (v, st) in enumerate(cells, 1):
            tgt = ws.cell(h_row + 1 + i, c)
            tgt.value = v
            tgt._style = st
    ws.sheet_properties.tabColor = '9E9E9E'   # 数据层=灰（规格 §6）
    return 1
```

- [ ] **Step 4: 趋势页填「—」+ autofilter + 说明行挪出**

新函数 `_denoise_trend_sheet(wb)`（同文件）：

```python
def _denoise_trend_sheet(wb):
    """趋势分析页：R2 区间说明挪到表头上方注释行、数据区空白格填 —、补 autofilter。
    说明挪动：把 R2 文本读出 → 写进新插入的第 1 行（灰小字），原 R2 说明清除，
    数据区上移回原位。空白= None/'' 且该行是数据行 → 填 '—'（字符串，不影响数值列）。"""
    name = '趋势分析（自然日分组）'
    if name not in wb.sheetnames:
        return 0
    ws = wb[name]
    h_row, headers = _header_info(ws)
    last_row = _last_data_row(ws, h_row)
    # 1) 说明行挪出：h_row 之前若有非空杂行（如 R2 区间说明），
    #    挪到表头下一格（首列数据格加 cell comment 承载，数据区不再夹文本）
    from openpyxl.comments import Comment
    stray = []
    for r in range(1, h_row):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if v not in (None, '') and r > 1:   # 第 1 行视为标题保留
                stray.append(str(v))
                ws.cell(r, c).value = None
    if stray:
        note = ws.cell(h_row, 1)
        note.comment = Comment(' '.join(stray), 'ZPP011', height=80, width=300)
    # 2) 数据区空白格填 —（仅数值列：表头含 数量/金额/率 的列）
    numeric_cols = [c for c, nm in headers.items()
                    if nm and any(k in str(nm) for k in ('数量', '金额', '率'))]
    filled = 0
    from openpyxl.styles import Alignment as _Al
    for r in range(h_row + 1, last_row + 1):
        for c in numeric_cols:
            cell = ws.cell(r, c)
            if cell.value in (None, ''):
                cell.value = '—'
                # openpyxl Alignment 不可变：赋新对象，不用 .copy()
                cell.alignment = _Al(horizontal='right')
                filled += 1
    # 3) autofilter
    try:
        if ws.auto_filter.ref in (None, ''):
            from openpyxl.utils import get_column_letter
            ws.auto_filter.ref = '%s%d:%s%d' % (
                get_column_letter(1), h_row,
                get_column_letter(ws.max_column), last_row)
    except Exception as e:
        _log('[post_process] 趋势页 autofilter 失败: %s' % e)
    ws.sheet_properties.tabColor = '9E9E9E'
    return filled
```

- [ ] **Step 5: 挂接 decorate_workbook**

`_upgrade_dashboard` 挂接点之后：

```python
        for fn in (_resort_summary, _denoise_trend_sheet):
            try:
                fn(wb)
            except Exception as e:
                _log('[post_process] %s 失败: %s' % (fn.__name__, e))
```

注意顺序：`_resort_summary` 必须在逐表流水线（numfmt/condfmt）**之后**跑（挂在 `add_dashboard` 同一区），避免重排把条件格式区间指错行。

Run: `python -B -m pytest tests/unit/test_denoise.py tests/unit/test_dashboard_upgrade.py -q --no-cov`
Expected: 全 passed

- [ ] **Step 6: 端到端 + diff**

Run: `python -B -X utf8 work\gen_check.py work\p3_out`
Run: `python -B -X utf8 work\diff_workbooks.py work\base_out\<file> work\p3_out\<file> "📊 驾驶舱"`
Expected: 「汇总统计」diff 只允许是**行序置换**（把 diff 工具对整行搬移的告警人工核对：每行的 (车间,金额) 配对不变）；趋势页 diff = 空白→— + 说明挪动。若行序搬移 diff 不可控，降级方案：`_resort_summary` 改为只加「金额降序」辅助排序列不搬行（记录决策到提交信息）。

- [ ] **Step 7: Commit**

```bash
git add analysis/excel_builder/post_process.py tests/unit/test_denoise.py
git commit -m "@v43.283c 数据层降噪：汇总统计|金额|降序重排(整行搬移零改值)/趋势页空白填—+说明挪入批注+autofilter，灰页签"
```

---

### Task 4: 视觉统一收尾 + 版本发布

**Files:**
- Modify: `analysis/excel_builder/post_process.py`（tabColor 批量）
- Modify: `utils/version_history.py`
- Test: 全量回归

**范围裁剪说明**：规格 §6 的"每页一句话说明"——现有 12 页里驾驶舱/分析说明已有说明行，其余数据页首行即标题，本期只做页签分色（说明行留待二期随派活页一起补，避免给 12 页逐页写文案的噪音改动）。

- [ ] **Step 1: 全簿页签分色**

```python
_TAB_COLORS = {'📊 驾驶舱': '2E7D32', '汇总统计': '9E9E9E',
               '趋势分析（自然日分组）': '9E9E9E'}

def _apply_visual_polish(wb):
    """v43.283 规格 §6：页签三层分色 + 表头行上方一句话说明（已有标题行则跳过）。"""
    for ws in wb.worksheets:
        color = _TAB_COLORS.get(ws.title)
        if color and ws.sheet_properties.tabColor in (None, ''):
            ws.sheet_properties.tabColor = color
    # 派活层（二期）预留：订单级汇总/车间维度 → E65100，本期先不加页
```

挂 `decorate_workbook` 最后（事实卡之后）。

- [ ] **Step 2: 全量单测**

Run: `python -B -m pytest tests/unit -q --no-cov`
Expected: 228+ passed, 0 failed（含本计划新增 3 个测试文件）

- [ ] **Step 3: 端到端生成 + 人工验收包**

Run: `python -B -X utf8 work\gen_check.py work\p4_out`
复制产物到桌面命名 `ZPP011偏差分析最终版_v43.283预览.xlsx`，交用户人眼验收（规格 §9.4）。

- [ ] **Step 4: 版本记录 + 提交**

`utils/version_history.py` 顶部加 v43.283 条目（features：分层改造一期四项；fixes：无）。

```bash
git add analysis/excel_builder/post_process.py utils/version_history.py
git commit -m "@v43.283 导出报表分层改造一期：偏差等级列+驾驶舱Top榜/周趋势+数据层降噪+页签分色（规格 2026-10-27）"
```

---

## 明确不做（本期）

- 环比（依赖 export_snapshots，二期 v43.284）
- 订单级汇总「状态」列 / 车间维度周热力（二期）
- 责任归属列、阈值重定义（用户决策：不做）
