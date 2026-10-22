# -*- coding: utf-8 -*-
import pandas as pd
for p in [
    r"H:\26年报表\积压表\材料积压--食品（10云南）202608.xlsx",
    r"H:\26年报表\积压表\材料积压--饮料（10云南）202609.xlsx",
]:
    print("=" * 60)
    print(p)
    xl = pd.ExcelFile(p)
    print("sheets:", xl.sheet_names)
    for s in xl.sheet_names[:3]:
        df = pd.read_excel(p, sheet_name=s, nrows=5)
        print(f"--- sheet [{s}] cols={len(df.columns)}")
        print("cols:", [repr(c) for c in df.columns])
        print(df.head(3).to_string(max_cols=12))
