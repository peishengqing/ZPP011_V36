# -*- coding: utf-8 -*-
import io
p = r"H:\zpp011_v2\work\云南达利积压分析_v2.0_优化版.py"
text = io.open(p, encoding="utf-8").read()
lines = text.splitlines()
# 定位 1.1 函数区
for i, ln in enumerate(lines, 1):
    if ln.startswith("# ---- 1.1"):
        start = i
        break
print("start line:", start, repr(lines[start-1]))
for j in range(start-1, start+28):
    print(j+1, repr(lines[j]))
