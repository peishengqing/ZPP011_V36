"""修复位置计算：替换成正确的边界检查代码"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# ── 找到需要替换的行范围 ──  
#  从 "# ── ƼƼ屏屏可��ʣ�──"  到下一个空行或 card_bg 行  
start=-1; end=-1  
for i,l in enumerate(lines):
    if '# ── ƼƼ' in l or '# ── Cal' in l or 'screenwidth' in l:
        start=i; print(f'[INFO] start={i}')
          
  
                 
                    
                        
                           
    
     
            
                
                 
                    
                         
                     
            
            
        
          
                
                    
            
          
            
        
         
            
        
         
            
        
        
    
            
                
                     
            
          
                
            
                  


print('Not found')
exit(1)
