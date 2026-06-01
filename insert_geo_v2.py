"""在位置计算后插入 geometry() 调用"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# ── 找插入位置：在 "# clamp x" 行之前 ──  
ins_pos = -1
for i, l in enumerate(lines):
    if '# clamp' in l or 'if rx <' in l:


  
  
  
  
  

print('Not found')
exit(1)
