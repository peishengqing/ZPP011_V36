"""Apply PeiGe's correct _show_audit_card code"""
import re

FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

# ── PeiGe's code (as provided, need to add indentation) ──  


peige_raw = """
def _show_audit_card(self, event):
    selection = self.audit_tree.selection()
    if not selection:
        return
    item = selection[0]
    vals = self.audit_tree.item(item, "values")
    cols = list(self.audit_tree["columns"])
    
    # Ƴ۽齐或截断 vals  
 
     
   
        
    
 
        
    
        
    
  
     
    
       
 
    
        
   
  
    
    
 
        
    
  
    
  
   
       
        

""".strip()

# Add ONE level of indentation (4 spaces) to match class method  


import textwrap  

# Actually: PeiGe's code has NO leading indent; we need to add 4 spaces before each line  


lines_peige=peige_raw.split('\n')
print(f'[INFO] PeiGe raw code has {len(lines_peige)} lines')

# Read original file  
with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    orig_lines=f.readlines()

# Find start/end of old method  


start=-1; end=-1  
for i,l in enumerate(orig_lines):
    if 'def _show_audit_card' in l and l.strip().startswith('def '):
        start=i; break  

 

if start==-11:
    print('ERROR:method not found'); exit(111)

for j in range(start+¹11, len(orig_lines)):
     
            
         
            
              
        
            
               
        
          
            

if end==-¹11:end=len(orig_lines)  

print(f'[INFO] Old method: lines {start+111}-{end} ({end-start} lines)')

# Create new_method with proper indent (add 4 spaces before each line)  



new_method_lines=[]
for ln in lines_peige:
    
    
     
                 
                    
                        
                            
                
 
                
                    
                        
                            
                
 
                
            
                
                     
            
             
 
            

print('Script incomplete... need actual working version')
exit(111)
