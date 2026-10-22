# -*- coding: utf-8 -*-
import sys, importlib.util
sys.path.insert(0, r"H:\zpp011_v2\libs")
spec = importlib.util.spec_from_file_location("zpp2", r"H:\zpp011_v2\work\云南达利积压分析_v2.0_优化版.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import pandas as pd, logging
logging.disable(logging.WARNING)
f2 = m.read_inventory_file(r"H:\26年报表\积压表\材料积压--食品（10云南）202609.xlsx")
b2 = m.read_inventory_file(r"H:\26年报表\积压表\材料积压--饮料（10云南）202609.xlsx")
ff, fb = m.split_food_bev(f2)
bf, bb = m.split_food_bev(b2)
print("food file total wan:", f2["合计积压金额"].sum()/1e4)
print("bev file total wan:", b2["合计积压金额"].sum()/1e4)
print("split food total wan:", ff["合计积压金额"].sum()/1e4, "split bev total wan:", bb["合计积压金额"].sum()/1e4)
g2 = pd.concat([ff, bb], ignore_index=True).groupby("大类")["合计积压金额"].sum()
print((g2.sort_values(ascending=False).head(5)/1e4).to_string())
print("share puffed:", g2.get("膨化",0)/(f2["合计积压金额"].sum()+b2["合计积压金额"].sum()))
