# -*- coding: utf-8 -*-
"""
tools/pre_push_gate.py — F03 提交前门禁（v43.325）

串四个环节，EXIT 码明确（0=PASS，非0=FAIL）：
  ① py_compile            本次所有改动/新增 .py 语法编译
  ② pyflakes              动态基线 + 消息归一化（见下）
  ③ pytest                全量（pytest.ini 默认 addopts，含 --cov-fail-under=18）
  ④ F01 闭合自检          对仓库真实成品动态重算三表闭合 + 引擎双向反证

pyflakes 动态基线（team-lead 11-09 05:34 拍板，替代「硬编码 30 条 issue 文本」）
--------------------------------------------------------------------------
· 基线锚点取 origin/main：push_log.sh 是在 commit 之后、push 之前调门禁，
  此时 HEAD 已含本次新文件；若用 HEAD 当锚点，新增文件会被误判成「既有文件」。
  origin/main 在 push 前仍是改动前版本，提交前/推送前两种场景都正确。
· 既有文件：`git show <baseline>:<path>` 写临时 .py → pyflakes 得「基线消息集合」；
  当前工作区文件 → pyflakes 得「当前消息集合」。
· 归一化：剥掉路径、行号、列号，只留消息主体（支持 `path:line:col: msg` 与
  `path:line: msg`，路径可含盘符 E:）。行号漂移天然免疫，不硬编码任何债务清单。
· 判定：当前消息**多重集 ⊆ 基线消息多重集** → PASS（允许减少=还债，不允许增加）。
  F821 / undefined name / may be undefined / referenced before assignment 类消息
  一律直接 FAIL，不进基线豁免（防 NameError 类真风险）。
· 新增文件（基线里不存在）一律要求 0 issues，不进豁免。
· 报告显式写出 analyzer.py 既有 issues 的动态分类与「本次新增 0」。

开关
----
· ZPP011_SKIP_GATE=1   全跳过，EXIT=0（spec 要求，确保 push 不被门禁自锁）
· ZPP011_GATE_FAST=1   跳过 pytest 环节（反证/快速验证用，其余三环节照跑）
· ZPP011_GATE_BASELINE 覆盖基线锚点（默认自动：优先 origin/main，退回 HEAD）
· ZPP011_PYFLAKES_PY / ZPP011_TEST_PY 覆盖两个解释器路径
· 位置参数 1：repo 根目录（默认取本文件父目录的父目录）
"""
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

PYFLAKES_PY = os.environ.get(
    'ZPP011_PYFLAKES_PY',
    r'C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe')
TEST_PY = os.environ.get(
    'ZPP011_TEST_PY',
    r'C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe')

REPO = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1
        else Path(__file__).resolve().parent.parent)

# 他人文件目录：绝不纳入门禁/提交范围（spec 红线）
_EXCLUDE_PREFIXES = (
    '.super-agent/', 'frontend/', '.workbuddy/', 'resources/',
    'gui_pyside6/widgets/dashboard_view_widget.py',
)

# pyflakes 输出：path:line:col: msg 或 path:line: msg。
# path 可含盘符 E:，故用「尾部 :数字:数字: 」锚定，而非简单 split(':')。
_RE_COL = re.compile(r'^(?P<path>.+):(?P<line>\d+):(?P<col>\d+):\s(?P<msg>.*)$')
_RE_LINE = re.compile(r'^(?P<path>.+):(?P<line>\d+):\s(?P<msg>.*)$')

# 危险类：任何一条都直接 FAIL，不进基线豁免
_DANGER_KEYS = (
    'undefined name', 'may be undefined', 'referenced before assignment',
    'undefined local', 'f821',
)


def _git(repo, *args):
    return subprocess.run(
        ['git', '-C', str(repo)] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding='utf-8', errors='replace')


def _baseline_ref(repo):
    """基线锚点：优先 origin/main（push 前它仍是改动前版本）。"""
    forced = os.environ.get('ZPP011_GATE_BASELINE')
    if forced:
        return forced
    if _git(repo, 'rev-parse', '--verify', 'origin/main').returncode == 0:
        return 'origin/main'
    return 'HEAD'


def _discover_targets(repo, baseline):
    """本次目标 .py = 相对基线的工作区差异（含已 commit 与未提交） ∪ 未跟踪新增。"""
    paths = set()
    r = _git(repo, 'diff', '--name-only', baseline)
    if r.returncode == 0:
        for p in r.stdout.splitlines():
            paths.add(p.strip())
    r = _git(repo, 'ls-files', '--others', '--exclude-standard')
    if r.returncode == 0:
        for p in r.stdout.splitlines():
            paths.add(p.strip())
    out = []
    for p in sorted(paths):
        p = p.strip().strip('"').replace('\\', '/')
        if not p or p.startswith('warning'):
            continue
        if not p.endswith('.py'):
            continue
        if any(p.startswith(x) for x in _EXCLUDE_PREFIXES):
            continue
        out.append(p)
    return out


# pyflakes 部分消息**内嵌**行号，如 F811:
#   redefinition of unused 'load_workbook' from line 15
# 在文件前面插入任何一行都会让这个 15 整体漂移。只剥前缀 path/line/col 不够，
# 必须把消息内嵌行号也归一化，否则动态基线仍会误报 FAIL（反证 ② 实测发现）。
_LINE_REF = re.compile(r'\b(from|on) line \d+\b')


def _normalize(line):
    """剥掉 path/line/col 与消息内嵌行号，只留稳定的消息主体文本。"""
    line = line.rstrip('\r\n')
    if not line.strip():
        return None
    m = _RE_COL.match(line) or _RE_LINE.match(line)
    msg = m.group('msg').strip() if m else line.strip()
    return _LINE_REF.sub(lambda mm: mm.group(1) + ' line <N>', msg)


def _pyflakes(py, file_path):
    r = subprocess.run([py, '-m', 'pyflakes', str(file_path)],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       encoding='utf-8', errors='replace')
    blob = r.stdout or ''
    # pyflakes 有 issues 时 returncode=1（不算 fatal）；>1 或 Traceback 才算工具异常
    fatal = ('Traceback' in blob) or (r.returncode > 1)
    msgs = [m for m in (_normalize(ln) for ln in blob.splitlines()) if m]
    return msgs, fatal


def _baseline_messages(py, text):
    fd, tmp = tempfile.mkstemp(suffix='.py', text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        return _pyflakes(py, tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _is_danger(msg):
    low = msg.lower()
    return any(k in low for k in _DANGER_KEYS)


def _classify(msg):
    """动态归类（按消息主体文本，不硬编码条数）。"""
    m = msg.lower()
    if 'imported but unused' in m:
        return 'unused_import'
    if 'assigned to but never used' in m or 'never used' in m:
        return 'unused_local'
    if 'f-string is missing placeholders' in m:
        return 'fstring'
    if 'redefinition of unused' in m:
        return 'redef'
    return 'other'


def check_pyflakes(repo, targets, baseline, report):
    ok = True
    py = PYFLAKES_PY
    for rel in targets:
        cur_msgs, fatal = _pyflakes(py, repo / rel)
        if fatal:
            report.append('  [FAIL] %s pyflakes 执行异常' % rel)
            ok = False
            continue
        danger = [m for m in cur_msgs if _is_danger(m)]
        for m in danger:
            report.append('  [FAIL] %s 危险类 issue（不进基线豁免）: %s' % (rel, m))
        if danger:
            ok = False

        if _git(repo, 'cat-file', '-e', baseline + ':' + rel).returncode == 0:
            head = _git(repo, 'show', baseline + ':' + rel)
            if head.returncode != 0:
                report.append('  [FAIL] %s 无法读取 %s 基线版本' % (rel, baseline))
                ok = False
                continue
            base_msgs, bfatal = _baseline_messages(py, head.stdout)
            if bfatal:
                report.append('  [FAIL] %s 基线 pyflakes 执行异常' % rel)
                ok = False
                continue
            cur_c, base_c = Counter(cur_msgs), Counter(base_msgs)
            new = sorted(m for m, n in cur_c.items() if n > base_c.get(m, 0))
            if rel == 'analysis/analyzer.py':
                cls = Counter(_classify(m) for m in base_msgs)
                n_danger = sum(1 for m in base_msgs if _is_danger(m))
                report.append(
                    '  [BASELINE] analyzer.py 既有 %d 条（%d 未使用 import / '
                    '%d 未使用局部变量 / %d f-string 无占位符 / %d 重定义，'
                    '%d 条 F821 类），本次新增 %d' % (
                        len(base_msgs), cls['unused_import'], cls['unused_local'],
                        cls['fstring'], cls['redef'], n_danger, len(new)))
            if new:
                for m in new:
                    report.append('  [FAIL] %s 新增 issue: %s' % (rel, m))
                ok = False
            else:
                report.append('  [PASS] %s 既有文件：当前 %d 条 ⊆ 基线 %d 条'
                              '（允许多重集减少，新增 0）'
                              % (rel, len(cur_msgs), len(base_msgs)))
        else:
            if cur_msgs:
                for m in cur_msgs:
                    report.append('  [FAIL] %s 新增文件必须 0 issues，实测: %s'
                                  % (rel, m))
                ok = False
            else:
                report.append('  [PASS] %s 新增文件 0 issues' % rel)
    return ok


def check_py_compile(repo, targets, report):
    if not targets:
        report.append('  [SKIP] 无目标 .py 文件')
        return True
    files = [str(repo / r) for r in targets]
    r = subprocess.run([sys.executable, '-m', 'py_compile'] + files,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       encoding='utf-8', errors='replace')
    if r.returncode == 0:
        report.append('  [PASS] py_compile %d 个文件 0 errors' % len(files))
        return True
    report.append('  [FAIL] py_compile 失败：')
    for ln in (r.stdout or '').splitlines()[-20:]:
        report.append('    ' + ln)
    return False


def check_pytest(repo, report):
    if os.environ.get('ZPP011_GATE_FAST') == '1':
        report.append('  [SKIP] pytest（ZPP011_GATE_FAST=1，反证/快速模式）')
        return True
    r = subprocess.run([TEST_PY, '-m', 'pytest'], cwd=str(repo),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       encoding='utf-8', errors='replace')
    tail = [ln for ln in (r.stdout or '').splitlines() if ln.strip()][-12:]
    report.append('  [PASS] 全量 pytest EXIT=0' if r.returncode == 0
                  else '  [FAIL] 全量 pytest EXIT=%d' % r.returncode)
    for ln in tail:
        report.append('    ' + ln)
    return r.returncode == 0


# F01 自检探针（由 TEST_PY 子进程执行：需要 openpyxl，且要能 import 项目模块）
_F01_PROBE = r'''
# -*- coding: utf-8 -*-
import glob
from openpyxl import Workbook, load_workbook
from analysis.excel_builder.analysis_metric_check import check_metric_closure

# 1) 真实成品：所有金额按当前工作簿逐列动态重算，绝不写死任何期别常量
xs = sorted(glob.glob('ZPP011偏差分析最终版_*.xlsx'))
if xs:
    wb = load_workbook(xs[-1], read_only=True, data_only=True)
    r = check_metric_closure(wb)
    print('[F01] 成品 %s' % xs[-1])
    print('[F01] 动态重算三表: 汇总=%s 分析=%s 明细=%s' % (
        r['values']['summary_total'], r['values']['analysis_total'],
        r['values']['detail_dev']))
    print('[F01] main_closure_ok=%s fail_count=%d' % (
        r['main_closure_ok'], r['fail_count']))
    assert r['main_closure_ok'] is True and r['fail_count'] == 0, \
        '真实成品主闭合未通过'
    wb.close()
else:
    print('[F01] 仓库内无成品 xlsx，仅跑引擎双向自检')

# 2) 引擎双向反证：构造必闭合 → PASS；破坏一格 → FAIL
def make(v):
    w = Workbook()
    a = w.active
    a.title = '汇总统计'
    a.append(['总偏差金额(含税)'])
    a.append([v])
    b = w.create_sheet('偏差金额分析')
    b.append(['总偏差金额(含税)'])
    b.append([v])
    c = w.create_sheet('完整偏差明细')
    c.append(['偏差金额'])
    c.append([v])
    return w

r1 = check_metric_closure(make(100.0))
assert r1['main_closure_ok'] is True and r1['fail_count'] == 0, '闭合应 PASS'
w2 = make(100.0)
w2['完整偏差明细']['A2'] = 200.0
r2 = check_metric_closure(w2)
assert r2['main_closure_ok'] is False and r2['fail_count'] >= 1, '破坏后应 FAIL'
print('[F01] 引擎双向反证: 闭合→PASS / 破坏一格→FAIL(fail_count=%d)'
      % r2['fail_count'])
print('[F01] ALL PASS')
'''


def check_f01(repo, report):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(repo) + os.pathsep + env.get('PYTHONPATH', '')
    r = subprocess.run([TEST_PY, '-c', _F01_PROBE], cwd=str(repo), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       encoding='utf-8', errors='replace')
    for ln in (r.stdout or '').splitlines():
        if ln.strip():
            report.append('    ' + ln)
    report.append('  [PASS] F01 闭合自检（真实成品动态重算 + 引擎双向反证）'
                  if r.returncode == 0
                  else '  [FAIL] F01 闭合自检 EXIT=%d' % r.returncode)
    return r.returncode == 0


def main():
    if os.environ.get('ZPP011_SKIP_GATE') == '1':
        print('[GATE] ZPP011_SKIP_GATE=1，门禁已跳过（EXIT=0）')
        return 0
    baseline = _baseline_ref(REPO)
    targets = _discover_targets(REPO, baseline)
    print('[GATE] repo=%s' % REPO)
    print('[GATE] 基线锚点=%s' % baseline)
    print('[GATE] 本次目标 .py 文件 %d 个:' % len(targets))
    for t in targets:
        print('   - ' + t)
    results = []
    for title, fn in (
        ('① py_compile', lambda rep: check_py_compile(REPO, targets, rep)),
        ('② pyflakes（动态基线 + 消息归一化）',
         lambda rep: check_pyflakes(REPO, targets, baseline, rep)),
        ('③ pytest', lambda rep: check_pytest(REPO, rep)),
        ('④ F01 闭合自检', lambda rep: check_f01(REPO, rep)),
    ):
        print('\n[GATE] === %s ===' % title)
        rep = []
        ok = fn(rep)
        print('\n'.join(rep))
        results.append(ok)
    a, b, c, d = results
    passed = all(results)
    print('\n[GATE] 汇总：py_compile=%s pyflakes=%s pytest=%s F01=%s → %s'
          % (a, b, c, d, 'PASS' if passed else 'FAIL'))
    print('[GATE] EXIT=%d' % (0 if passed else 1))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
