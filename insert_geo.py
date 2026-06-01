"""在位置计算后加一行 geometry() 调用"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# ──  找需要插入的位置 ──  
#  在 "if rx < wx:"  之前插入  

for i,l in enumerate(lines):
    if '# clamp x' in l or 'if rx < wx' in l:


  
  
              
        
        
          
            
            
                 
            


print('Not found')
exit(1)
