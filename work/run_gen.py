# -*- coding: utf-8 -*-
import sys, importlib.util
sys.path.insert(0, r"H:\zpp011_v2\libs")   # pypinyin (若已装好)
spec = importlib.util.spec_from_file_location("zpp2", r"H:\zpp011_v2\work\云南达利积压分析_v2.0_优化版.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import logging
logging.disable(logging.WARNING)
f1 = r"H:\26年报表\积压表\材料积压--食品（10云南）202608.xlsx"
d1 = r"H:\26年报表\积压表\材料积压--饮料（10云南）202608.xlsx"
f2 = r"H:\26年报表\积压表\材料积压--食品（10云南）202609.xlsx"
d2 = r"H:\26年报表\积压表\材料积压--饮料（10云南）202609.xlsx"
out = r"H:\zpp011_v2\work\v20_8月vs9月.pptx"
p = m.generate_ppt(f1, d1, f2, d2, out=out)
from pptx import Presentation
prs = Presentation(p)
print("pypinyin available:", m._HAS_PINYIN)
print("slides:", len(prs.slides), "->", p)
