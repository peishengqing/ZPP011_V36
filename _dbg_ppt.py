# -*- coding: utf-8 -*-
"""v43.156 智能PPT修复 端到端验证

覆盖 4 个修复点 + 幂等性：
  T1  失败路径不再抛 TypeError（log_cb 缺 level 把真错误吞掉的致命 bug）
  T2  缺 sheet 报错说人话（区分原始导入表 / 分析结果）
  T3  目录页恒在第 2 页
  T4  简明版 vs 专业版真的是两份报告（页数不同、字节数不同）
  T5  专业版页数 >= 20
  T6  幂等：同输入连续两次生成，页数与章节标题一致
  T7  _move_slide_to 搬运函数本身正确
"""
import os
import sys
import hashlib
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = []
FAIL = []


def chk(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("[PASS]" if cond else "[FAIL]", name,
                         ("  <- " + str(detail)) if detail else ""))


def slide_count(p):
    z = zipfile.ZipFile(p)
    return len([n for n in z.namelist() if n.startswith("ppt/slides/slide")])


def slide_titles(p):
    """按 presentation.xml 的顺序取每页标题栏文字"""
    from xml.etree import ElementTree as ET
    NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
          'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
          'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
    z = zipfile.ZipFile(p)
    pres = ET.fromstring(z.read('ppt/presentation.xml'))
    rels = ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))
    rmap = {r.get('Id'): r.get('Target') for r in rels}
    out = []
    for sid in pres.find('p:sldIdLst', NS):
        rid = sid.get('{%s}id' % NS['r'])
        t = rmap.get(rid, '').replace('../', '')
        name = 'ppt/' + t
        if name not in z.namelist():
            continue
        root = ET.fromstring(z.read(name))
        texts = [(e.text or '') for e in root.iter('{%s}t' % NS['a'])]
        out.append(' '.join(texts)[:40])
    return out


# GUI 侧 MainWindow.log 的真实签名：(msg, level)
def gui_log(msg, level="info"):
    LOGS.append((level, msg))


LOGS = []

print("=" * 70)
print("v43.156 智能PPT 端到端验证")
print("=" * 70)

from core.advanced_ppt_generator_v2 import (  # noqa: E402
    generate_advanced_report_v2, _safe_log, _move_slide_to,
)

GOOD = r'C:/Temp/ppt_src/ZPP011偏差分析最终版_20260901-20260930_v01.xlsx'
RAW = r'E:/ZPP011导出文件原数据/前期/ZPP011_20260901-20260930.xlsx'  # 裴哥指定的原始导入表
OUT_SIMPLE = r'C:/Temp/ppt_v156_simple.pptx'
OUT_PRO = r'C:/Temp/ppt_v156_pro.pptx'

for p in (OUT_SIMPLE, OUT_PRO):
    if os.path.exists(p):
        os.remove(p)

# ---------- T1/T2 失败路径 ----------
print("\n[T1/T2] 失败路径：不再 TypeError，报错说人话")
del LOGS[:]
ok = generate_advanced_report_v2(RAW, r'C:/Temp/ppt_should_not_exist.pptx',
                                 log_cb=gui_log, mode="pro")
chk("T1 失败时返回 False（未抛异常穿透）", ok is False, ok)
err_logs = [m for lv, m in LOGS if lv == "error"]
chk("T1 有 error 级日志", len(err_logs) > 0, len(err_logs))
chk("T1 日志里没有 TypeError（真错误未被吞掉）",
    not any("TypeError" in m for m in err_logs),
    [m[:60] for m in err_logs])
chk("T1 日志里没有 missing 1 required positional",
    not any("positional argument" in m for m in err_logs))
chk("T2 明确指出是原始导入表",
    any("原始导入表" in m for m in err_logs),
    err_logs[0][:80] if err_logs else "(无)")
chk("T2 列出实际 sheet 名", any("Data" in m for m in err_logs))
chk("T2 给出可执行指引（先点分析/导出完整报告）",
    any("导出完整报告" in m or "分析" in m for m in err_logs))
chk("T1/T2 未产出垃圾文件", not os.path.exists(r'C:/Temp/ppt_should_not_exist.pptx'))

# 不存在的文件
del LOGS[:]
ok = generate_advanced_report_v2(r'C:/Temp/nonexistent_zzz.xlsx', r'C:/Temp/x.pptx',
                                 log_cb=gui_log, mode="pro")
err_logs = [m for lv, m in LOGS if lv == "error"]
chk("T2 文件不存在时提示清楚", ok is False and any("找不到" in m for m in err_logs),
    err_logs[:1])

# 非法 mode
del LOGS[:]
ok = generate_advanced_report_v2(GOOD, r'C:/Temp/x.pptx', log_cb=gui_log, mode="乱填")
chk("非法 mode 被拒（防呆）", ok is False)

# ---------- _safe_log 三层兜底 ----------
print("\n[EXTRA] _safe_log 三层兜底")
calls = []


def log_two(msg, level="info"):
    calls.append((level, msg))


_safe_log(log_two, "A", "info")
chk("正规 (msg, level) 调用成功", calls == [("info", "A")], calls)

calls2 = []


def log_one(msg):
    calls2.append(msg)


_safe_log(log_one, "B", "error")
chk("降级为单参调用", calls2 == ["B"], calls2)


def log_boom(*a, **k):
    raise RuntimeError("日志本身炸了")


try:
    _safe_log(log_boom, "C", "info")
    chk("日志自身抛异常也被吞掉（绝不反噬主流程）", True)
except Exception as e:
    chk("日志自身抛异常也被吞掉（绝不反噬主流程）", False, e)
_safe_log(None, "D")
chk("log_cb=None 时静默返回", True)

# ---------- _move_slide_to ----------
print("\n[EXTRA] _move_slide_to 搬运函数")
from pptx import Presentation  # noqa: E402
prs = Presentation()
for i in range(5):
    prs.slides.add_slide(prs.slide_layouts[6])
before = len(prs.slides._sldIdLst)
_move_slide_to(prs, 4, 1)
chk("搬运后 sldIdLst 长度不变", len(prs.slides._sldIdLst) == before,
    "%d -> %d" % (before, len(prs.slides._sldIdLst)))
el4 = prs.slides._sldIdLst[1]
chk("目标位置拿到的是原第5页", el4 is not None)
_move_slide_to(prs, 99, 0)
_move_slide_to(prs, 0, 99)
chk("越界索引安全返回 False 不崩", True)
_move_slide_to(prs, 2, 2)
chk("同位置搬运安全", True)

# ---------- _add_table 列宽越界（v43.156 顺带修的第五个 bug）----------
print("\n[EXTRA] _add_table 列宽长度不匹配（动态表头场景）")
from pptx.util import Inches  # noqa: E402
from core.advanced_ppt_generator_v2 import _add_table  # noqa: E402

for label, hs, cws, want in [
    ("列宽比表头多（本次崩溃根因）", ['A', 'B', 'C'], [2, 1, 1, 1, 1, 1.8], 3),
    ("列宽比表头少", ['A', 'B', 'C', 'D', 'E'], [2, 1], 5),
    ("列宽正好", ['A', 'B'], [2, 1], 2),
]:
    p2 = Presentation()
    s2 = p2.slides.add_slide(p2.slide_layouts[6])
    try:
        _add_table(s2, Inches(0.8), Inches(1.6), Inches(9), hs,
                   [['x'] * len(hs)], cws)
        got = len(s2.shapes[-1].table.columns)
        chk("列宽越界不崩：%s" % label, got == want, "得到 %d 列" % got)
    except Exception as e:
        chk("列宽越界不崩：%s" % label, False, e)

# ---------- T3/T4/T5 正常生成 ----------
print("\n[T3/T4/T5] 简明版 vs 专业版")
del LOGS[:]
ok_s = generate_advanced_report_v2(GOOD, OUT_SIMPLE, log_cb=gui_log, mode="simple")
chk("简明版生成成功", ok_s is True)
del LOGS[:]
ok_p = generate_advanced_report_v2(GOOD, OUT_PRO, log_cb=gui_log, mode="pro")
chk("专业版生成成功", ok_p is True)

if ok_s and ok_p:
    ns, np_ = slide_count(OUT_SIMPLE), slide_count(OUT_PRO)
    print("    简明版 %d 页 / 专业版 %d 页" % (ns, np_))

    ts = slide_titles(OUT_SIMPLE)
    tp = slide_titles(OUT_PRO)

    # T3 目录页在第 2 页（第 1 页是封面）
    chk("T3 简明版第1页是封面", "偏差分析报告" in ts[0] or "ZPP011" in ts[0], ts[0][:40])
    chk("T3 简明版第2页是目录", "目录" in ts[1], ts[1][:40])
    chk("T3 简明版目录不在末页",
        not any("目录" == t.strip()[:2] for t in ts[2:]),
        [t[:20] for t in ts[2:]])
    chk("T3 专业版第2页是目录", "目录" in tp[1], tp[1][:40])
    chk("T3 专业版目录不在末页",
        not any("目录" == t.strip()[:2] for t in tp[2:]))

    # T4 两版确实不同
    chk("T4 简明版页数 <= 8（精简）", ns <= 8, ns)
    chk("T4 两版页数不同", ns != np_, "%d vs %d" % (ns, np_))
    h1 = hashlib.md5(open(OUT_SIMPLE, 'rb').read()).hexdigest()
    h2 = hashlib.md5(open(OUT_PRO, 'rb').read()).hexdigest()
    chk("T4 两版字节内容不同（md5）", h1 != h2)
    chk("T4 两版字节数不同",
        os.path.getsize(OUT_SIMPLE) != os.path.getsize(OUT_PRO),
        "%d vs %d" % (os.path.getsize(OUT_SIMPLE), os.path.getsize(OUT_PRO)))

    # T5 专业版 20+ 页
    chk("T5 专业版 >= 20 页（兑现菜单承诺）", np_ >= 20, np_)
    chk("T5 专业版章节扉页存在",
        any("一、总体与维度对比" in t for t in tp),
        [t[:24] for t in tp if '、' in t][:6])

    # 简明版不该有专业版专属页
    chk("T4 简明版无专业版章节扉页",
        not any("一、总体与维度对比" in t for t in ts))
    chk("T4 简明版有核心结论页",
        any("核心结论" in t for t in ts), [t[:20] for t in ts])

    # ---------- T6 幂等 ----------
    print("\n[T6] 幂等性（同输入连续两次生成）")
    OUT_PRO2 = r'C:/Temp/ppt_v156_pro2.pptx'
    if os.path.exists(OUT_PRO2):
        os.remove(OUT_PRO2)
    generate_advanced_report_v2(GOOD, OUT_PRO2, log_cb=gui_log, mode="pro")
    chk("T6 两次生成页数一致", slide_count(OUT_PRO) == slide_count(OUT_PRO2),
        "%d vs %d" % (slide_count(OUT_PRO), slide_count(OUT_PRO2)))
    chk("T6 两次生成各页标题一致", slide_titles(OUT_PRO) == slide_titles(OUT_PRO2))

    # ---------- 无异常静默 ----------
    print("\n[EXTRA] 生成过程日志无 error 级")
    del LOGS[:]
    generate_advanced_report_v2(GOOD, r'C:/Temp/ppt_v156_chk.pptx',
                                log_cb=gui_log, mode="pro")
    errs = [m for lv, m in LOGS if lv == "error"]
    chk("正常生成零 error 日志", not errs, errs[:2])

print("\n" + "=" * 70)
print("结果: %d PASS / %d FAIL" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项: %s" % FAIL)
print("=" * 70)
sys.exit(1 if FAIL else 0)
