# -*- coding: utf-8 -*-
import io, re
p = r"H:\zpp011_v2\work\云南达利积压分析_v2.0_优化版.py"
lines = io.open(p, encoding="utf-8").read().splitlines()
print("total lines:", len(lines))
markers = [
    "# ---- 1.1", "# ---- 1.2 / 2.2", "def _build_class_warehouse_rows(", "def _build_class_warehouse_rows_2level(",
    "def _paginate_rows_2level", "def _add_class_warehouse_2level_page", "def _paginate_rows(", "def add_food_class_warehouse_slide",
    "# ---- 1.3", "def _material_slide", "def add_food_packaging_slide", "def add_food_raw_slide",
    "# ---- 2.1", "def add_bev_class_summary", "# ---- 2.2", "def add_bev_class_warehouse_slide",
    "def add_bev_packaging_slide", "def add_bev_raw_slide", "# ---- 10 核心结论", "def add_conclusion_slide",
    "# 缺数据占位", "def add_placeholder_box", "def generate_ppt(", "# GUI", "def run_gui(", "# 入口", "if __name__",
]
for m in markers:
    for i, ln in enumerate(lines, 1):
        if m in ln:
            print(f"{i:>5}  {ln.strip()[:80]}")
            break
