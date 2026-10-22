# -*- coding: utf-8 -*-
import sys, importlib.util, logging
sys.path.insert(0, r"H:\zpp011_v2\libs")
spec = importlib.util.spec_from_file_location("zpp2", r"H:\zpp011_v2\work\云南达利积压分析_v2.0_优化版.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
logging.disable(logging.WARNING)
f2 = m.read_inventory_file(r"H:\26年报表\积压表\材料积压--食品（10云南）202609.xlsx")
print("cols has 仓库类型:", "仓库类型" in f2.columns)
g = f2.groupby("仓库类型")["合计积压金额"].sum()/1e4
print(g.to_string())
print("total:", f2["合计积压金额"].sum()/1e4)
