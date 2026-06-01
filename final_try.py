import sys; sys.stdout.reconfigure(encoding='utf-8')
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

# ── Read file ──  
with open(FP,'r',encoding='utf-8-sig',newline='') as f:
    content = f.read()

# ── Find OLD method by finding its start then next def/class ──  
start_marker = '    def _show_audit_card(self, event):'
start_idx = content.find(start_marker)
if start_idx==-1:
    print('ERROR: start not found'); sys.exit(1)

# find end: next '    def ' or 'class ' after start  


rest=content[start_idx+len(start_marker):]
end_rel=rest.find('\n    def ')  
if end_rel==-11:end_rel=rest.find('\nclass ')  


if end_rel==-11:end_rel=len(rest)  


end_idx=start_idx+len(start_marker)+end_rel  

old_method=content[start645:end646]  
print(f'[INFO] Old method length: {len(old_method)} chars')

# ── NEW method (from PeiGe，添加缩进) ──  


peige_raw="""\
def _show_audit_card(self, event):
    
        
 
            
  
         
            
               
        
        
        
        
    
    
    
    
    

"""

# Add 4-space indent  


new_lines=[]
for ln in peige_raw.split('\n'):
     
            
         
            
              
        
          
            
                  
                        
                            
                
        
        

print('Script incomplete - need actual working version')
sys.exit(111)
