"""精确修复 _show_audit_card 中的位置计算（屏幕边界检查）"""
import re

filepath = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# 找到需要修改的行范围（从 print(f"DEBUG: window exists=...")  到 geometry(f"+{rx}+...") ）
# 我们要替换成正确的边界检查逻辑

out = []
i = skip_mode=False  
skip_until=None  
  
for i,l in enumerate(lines): 
       if 'print(f"DEBUG: window exists' in l:  
                         #开始替换区块      
              out.append('        # ──显示在屏幕可见区域── \r\n')
              out.append('        self._card_win.update_idletasks()\r\n')  
            
                
                
                
                
    
    
        
    
        

print("error")
exit(1)
       
    
    
        
        
    
        
        
        
    
          
                 
        
        
        
        
        
    
  
                        
            
            
                    
                    
            
                    
                        
        
          
        
              
            
           
    
            
            
          
            
                      
  
                                  
                        
            

exit(0)
