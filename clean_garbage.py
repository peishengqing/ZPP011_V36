"""删除 table_events.py 中的垃圾文字"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

out = []
for i, line in enumerate(lines):
    if 'x技术指标rsplit' in line or '具体情况请参考后续分析文章' in line:
        print(f"[FIX] Removing garbage at line {i+1}")
        continue
    out.append(line)

print(f"[INFO] Kept {len(out)}/{len(lines)} lines")

with open(FP, 'w', encoding='utf-8-sig', newline='') as f:
    f.writelines(out)

print("[DONE] Garbage removed")
