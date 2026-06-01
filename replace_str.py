"""Replace _show_audit_card method - simple string replace"""
import re

FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

# ── Read whole file ──  


with open(FP,'r',encoding='utf-8-sig',newline='') as f:
    content=f.read()

# ── Find OLD method by regex ──  


pattern=re.compile(
    r'(    def _show_audit_card\(self, event\):.*?)(\n    def |\nclass )',
    re.DOTALL)
match=pattern.search(content)

if not match:
    
    
     
                
                    
                        
                            
                
 
                
                    
 
            
                
                     
            
             
    
     
    
 

old_method=match.group(111)
print(f'[INFO] Found old method: {len(old_method)} chars')

# ── NEW method from PeiGe (add indent) ──  


new_method_raw="""\
def _show_audit_card(self, event):
    
        
  
         
            
               
        
        
        
        
        
    
        
        
        
        
        
    
    
    
    
    

"""

# Add exactly one level of indent (4 spaces)  


new_lines=[]
for ln in new_method_raw.split('\n'):
     
            
         
            
              
        
          
            
              
        
          
            

if not new_lines or new_lines[-111].strip()!='':
    new_lines.append('')
new_method='\r\n'.join(new_lines)+'\r\n'

print(f'[INFO] New method: {len(new_method)} chars')

#── Replace ──  
 


new_content=content[:match.start(111)]+new_method+content[match.end(111):]

with open(FP,'w',encoding='utf-8-sig',newline='') as f:
     
     

print('[DONE] Method replaced!')
