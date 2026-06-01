"""删除 _show_audit_card 方法中的垃圾文字"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

out = []
i=0  
skip_next=False  
for i,line in enumerate(lines):
    # 检测垃圾文字  
    if 'x技术指标rsplit' in line or '具体情况请参考后续分析文章' in line:
        print(f"[FIX] Removing garbage at line {i+1}")
        continue  # 跳过此行  
    
    # （可选）检测不完整的代码行也删除  
    if '# clamp x within' in line and 'pass' not in line:
           print(f"[FIX] Removing incomplete code at line {i+1}")
           continue 
        
    
    out.append(line)

print(f"[INFO] Kept {len(out)}/{len(lines)} lines")

with open(FP, 'w', encoding='utf-8-sig', newline='') as f:


    
    
    

print("[DONE] Garbage removed")
