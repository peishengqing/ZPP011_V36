# -*- coding: utf-8 -*-
import importlib.util, time, logging
spec = importlib.util.spec_from_file_location("zpp2", r"E:\exe\云南达利积压分析_v2.0_优化版.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
logging.disable(logging.WARNING)
base = r"H:\26年报表\积压表"
f1 = base + r"\材料积压--食品（10云南）202608.xlsx"
d1 = base + r"\材料积压--饮料（10云南）202608.xlsx"
f2 = base + r"\材料积压--食品（10云南）202609.xlsx"
d2 = base + r"\材料积压--饮料（10云南）202609.xlsx"
ts = time.strftime("%Y%m%d_%H%M%S")
out = rf"C:\Users\Administrator\Desktop\云南达利积压分析报告\云南达利积压分析_v2.0_8月vs9月_{ts}.pptx"
p = m.generate_ppt(f1, d1, f2, d2, out=out)
from pptx import Presentation
print("slides:", len(Presentation(p).slides), "| saved:", p)
