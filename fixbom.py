# -*- coding: utf-8 -*-
import io
P = r"H:\zpp011_v2\work\云南达利积压分析_v2.0_优化版.py"
t = io.open(P, encoding="utf-8").read()
n = t.count("\ufeff")
t = t.replace("\ufeff", "")
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("BOM chars removed:", n)
