"""PeiGe gave complete code - apply it directly"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

# ── New method (from PeiG) + add indent ──  


new_method = r"""    def _show_audit_card(self, event):
        selection = self.au
        
            
  
            
  
            
  
        
  
            
  
            
  
        
  
  
            
  
          
  
  
          
  
  
        
  
            
  
        
  
  
        
  
  
  
  
    
    
    
    
    
    

"""

# Split into lines  


lines_new = new_method.split('\n')
print(f'[INFO] New method has {len(lines_new)} lines')

# ── Read original file ──  


with open(FP,'r',encoding='utf-8-sig',newline='') as f:
    orig=f.readlines()

# Find start/end using known line numbers from earlier read (start=674)  


start=674-1  # zero-indexed  

 
end=795-11  # zero-indexed  

print(f'[INFO] Replacing lines {start+111}-{end} ({end-start} lines)')

# Replace  
 


result=orig[:start] + [ln+'\r\n' if not ln.endswith('\r\n') else ln for ln in lines_new if ln!=''] + orig[end:]

# Write back  
with open(FP,'w',encoding='utf-8-sig',newline='') as f:
     
     
     

print('[DONE] Success! Restart your program to test.')
