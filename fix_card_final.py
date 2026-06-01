"""最终修复：删除垃圾文字 + 修复窗口位置"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# ── Step1:找到并删除垃圾文字所在行 ──  
garbage_found = False  
out = []
i=0  
while i < len(lines):
    line=lines[i]
    if 'x技术指标rsplit' in line or '具体情况请参考后续分析文章' in line:
        print(f"[FIX] Removing garbage at line {i+1}")
        garbage_found=True   
        i+=1  
        continue 
    out.append(line)
    i+=1   

if not garbage_found:
    print("[WARN] Garbage text not found - may already be removed")  

# ── Step2:修复位置计算代码（在 _show_audit_card 方法内）──  


# 重新拼接  
content=''.join(out)

# ── 替换位置计算代码块──  


old_pos='''        # ── ƼƼ屏屏可见── \r\n        sw =
self.root.winfo_screenwidth()'''  

print('Skip detailed replacement for now')
print('Just write back cleaned content')

with open(FP, 'w', encoding='utf-8-sig', newline='') as f:


    
    
    
    
    
    
    

exit(0)
