# -*- coding: utf-8 -*-
import io, sys
import pandas as pd
out = io.open(r"H:\zpp011_v2\data_struct.txt", "w", encoding="utf-8")
def w(s=""): out.write(str(s) + "\n")
for p in [
    r"H:\26年报表\积压表\材料积压--食品（10云南）202608.xlsx",
    r"H:\26年报表\积压表\材料积压--饮料（10云南）202609.xlsx",
]:
    w("=" * 70); w(p)
    df = pd.read_excel(p, sheet_name="明细")
    w(f"shape={df.shape}")
    w("cols: " + " | ".join(repr(c) for c in df.columns))
    w("head:")
    w(df.head(4).to_string())
    for c in df.columns:
        cs = str(c).strip()
        if cs in ("大类", "分类", "仓库", "归属仓库", "工厂", "合计积压金额"):
            vc = df[c].value_counts(dropna=False).head(15)
            w(f"--- value_counts [{c}]")
            w(vc.to_string())
    w()
out.close()
print("done")
