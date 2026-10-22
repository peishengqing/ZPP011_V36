# -*- coding: utf-8 -*-
import io
import pandas as pd
out = io.open(r"H:\zpp011_v2\work\bev_probe.txt", "w", encoding="utf-8")
def w(s=""): out.write(str(s) + "\n")
base = r"H:\26年报表\积压表"
df9 = pd.read_excel(base + r"\材料积压--饮料（10云南）202609.xlsx", sheet_name="明细")
df8 = pd.read_excel(base + r"\材料积压--饮料（10云南）202608.xlsx", sheet_name="明细")
for name, df in (("202608", df8), ("202609", df9)):
    df.columns = [str(c).strip() for c in df.columns]
    amt = pd.to_numeric(df["合计积压金额"], errors="coerce").fillna(0)
    w("=" * 50); w(f"{name} rows: {len(df)} total 万: {amt.sum()/1e4:.2f}")
    w("-- 大类:"); w((df.groupby("大类")["合计积压金额"].sum()/1e4).round(2).to_string())
    w("-- 拟处理意见:"); w(df["拟处理意见"].value_counts(dropna=False).to_string())
    w("-- 是否存在报废风险:"); w(df["是否存在报废风险"].value_counts(dropna=False).to_string())
    w("-- 报废原因:"); w(df["报废原因"].value_counts(dropna=False).head(8).to_string())
    w("-- 开始积压时间:"); w(df["开始积压时间"].astype(str).str[:7].value_counts().head(8).to_string())
    w("-- 最后领用年月:"); w(df["最后领用年月"].astype(str).value_counts(dropna=False).head(8).to_string())
    for c in ["销售计划","新品","集团统筹","改版","生产或仓库多报货","其他"]:
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce").fillna(0).sum()
            w(f"-- 原因列[{c}]: {v/1e4:.2f} 万")
    top = df.assign(_a=amt).nlargest(5, "_a")[["物料名称","数量","单价","合计积压金额","归属仓库","开始积压时间","拟处理意见","责任人"]]
    w("-- Top5 物料:"); w(top.to_string(index=False))
w("=" * 50)
w("8月->9月 物料变动:")
c8 = set(df8["物料编码"].astype(str)); c9 = set(df9["物料编码"].astype(str))
new9 = df9[df9["物料编码"].astype(str).isin(c9 - c8)]
w(f"新增: {len(new9)} 项, {pd.to_numeric(new9['合计积压金额'],errors='coerce').fillna(0).sum()/1e4:.2f} 万")
gone = df8[df8["物料编码"].astype(str).isin(c8 - c9)]
w(f"消失: {len(gone)} 项, {pd.to_numeric(gone['合计积压金额'],errors='coerce').fillna(0).sum()/1e4:.2f} 万")
out.close(); print("done")
