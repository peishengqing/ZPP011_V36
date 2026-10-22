# -*- coding: utf-8 -*-
import io, sys
P = r"H:\zpp011_v2\work\云南达利积压分析_v2.0_优化版.py"
lines = io.open(P, encoding="utf-8").read().split("\n")
print("original lines:", len(lines))

def block(name):
    return io.open(rf"H:\zpp011_v2\work\blk\{name}.txt", encoding="utf-8").read().rstrip("\n").split("\n")

# (start, end_inclusive, start_prefix, end_contains, blockfile)  自底向上执行
jobs = [
    (1287, 1459, "def generate_ppt(f1_path", "    return out", "I"),
    (1231, 1268, "def add_conclusion_slide", "    ])", "H"),
    (1200, 1213, "def add_bev_class_warehouse_slide", "])", "G"),
    (1172, 1196, "def add_bev_class_summary", "    ])", "E"),
    (1096, 1154, "def _material_slide", "    ])", "D"),
    (1079, 1092, "def add_food_class_warehouse_slide", "])", "F"),
    (1039, 1049, "def _add_class_warehouse_2level_page", "])", "B"),
    (969, 1008, "def _build_class_warehouse_rows_2level", "    return rows, t1, t2", "C"),
    (878, 903, "# ---- 1.1", "    ])", "A"),
]

for start, end, spfx, epx, blkname in jobs:
    s, e = lines[start - 1], lines[end - 1]
    if not s.lstrip().startswith(spfx):
        print(f"ABORT: line {start} does not start with {spfx!r}: {s!r}")
        sys.exit(1)
    if epx not in e:
        print(f"ABORT: line {end} does not contain {epx!r}: {e!r}")
        sys.exit(1)
    new = block(blkname)
    lines = lines[:start - 1] + new + lines[end:]
    print(f"replaced {start}-{end} with {blkname} ({len(new)} lines)")

io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("done, new line count:", len(lines))
