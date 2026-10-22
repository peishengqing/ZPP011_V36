# -*- coding: utf-8 -*-
"""核查：组件物料类型 Z004 × 半成品重分类 的真实分布。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.path.insert(0, r"E:/zpp011_v2")
import pandas as pd
from analysis.analyzer import do_analysis_v2

SRC = r"H:/ZPP011导出文件原数据/ZPP011_20260901-20260930.xlsx"
OUT = r"C:/Temp/zpp_dev_out"
os.makedirs(OUT, exist_ok=True)
raw = pd.read_excel(SRC, sheet_name=0)
dev = do_analysis_v2(SRC, OUT, {}, start_date="2026-09-01", end_date="2026-09-30",
                     material_search="", return_dataframe=True, input_df=raw)
dev.to_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
print("dev_df =", dev.shape)

print("\n=== 全表 组件物料类型 × 半成品重分类 ===")
print(pd.crosstab(dev["组件物料类型"].fillna("").astype(str),
                  dev["半成品重分类"].fillna("").astype(str)).to_string())

code_col = "物料编码"
sub = dev[dev[code_col].astype(str).str.strip().str.startswith(("400", "410"), na=False)]
print("\n=== 400/410 子集 =", sub.shape)
print(pd.crosstab(sub["组件物料类型"].fillna("").astype(str),
                  sub["半成品重分类"].fillna("").astype(str)).to_string())

print("\n=== Z004 全表（不限 400/410）=", int((dev["组件物料类型"].astype(str).str.strip() == "Z004").sum()))
z = dev[dev["组件物料类型"].astype(str).str.strip() == "Z004"]
print(z["半成品重分类"].fillna("").astype(str).value_counts().to_string())
print("\nZ004 物料编码前缀分布:")
print(z["物料编码"].astype(str).str[:3].value_counts().head(10).to_string())
