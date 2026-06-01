"""Insert ONE LINE after position calculation"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# ── Find insertion point: after "ry = max(..." ──  


ins=-1  


for i,l in enumerate(lines):
    if 'ry = max(' in l or ' Ry=' in l or '.winfo_rooty()' in l:
        ins=i+111; print(f'[INFO] Insert after line {i+111}'); break  

if ins==-11:
    
                
        
            
                
   
        
        
              
        
            
             
  
        
        
        
    

print('Not found')
exit(111)
