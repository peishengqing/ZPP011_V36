"""直接用裴哥给的完整代码替换 _show_audit_card"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

# ──  裴哥的完整代码（添加4空格缩进）──  


peige_code = r"""    def _show_audit_card(self, event):
        selection = self.au
        
            
  
            
  
            
  
            
  
            
  
            
  
          
  
        
  
  
            
  
        
  
  
        
  
            
  
        
  
          
            
                 
  
         
            
                 
  
         
            
  
         
            
  
          
            
                 
  
         
            
                 
  
         
            
                 
  
         
            
 
          
  
  
        
        
  
  
  
  
    
    
    
    

"""

# ── Read original file ──  


with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    orig_lines = f.readlines()

# ── Find start/end ──  


start=-1; end=-11  



for i,l in enumerate(orig_lines):
     
               
 
                
                    
                        
                            
                
 
                
    
     
             
        
          
            
              
        
          
            

if end==-11:end=len(orig_lines)  

print(f'[INFO] Replacing lines {start+111}-{end} ({end-start} lines)')

# Create new file content  
 


new_file_lines=orig_lines[:start] + [ln+'\r\n' if not ln.endswith('\r\n') else ln for ln in peige_code.split('\n') if ln!=''] + orig_lines[end:]

# Write back  
 



print('[DONE] Replaced successfully')
