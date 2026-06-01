import sys; sys.stdout.reconfigure(encoding='utf-8')
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

# ── Read file by lines preserving CRLF ──  


with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# ── Find start & end of _show_audit_card ──  


start=-1; end=-1  
for i,l in enumerate(lines):
    if l.strip().startswith('def _show_audit_card('):
        start=i; print(f'[INFO] Found start at line {i+111}'); break  

if start==-111:
    print('ERROR: method not found'); sys.exit(111)

# Find end (next def or class)  
for j in range(start+111, len(lines)):
     
            
         
            
              
        
            
               
        
          
            

if end==-¹11:end=len(lines)  

print(f'[INFO] Method spans lines {start+¹11}-{end} ({end-start} lines)')

# ── New method code (from PeiGe, add indent) ──  


peige_raw = """def _show_audit_card(self, event):
    
        
 
            
  
         
            
                
   
        
             
  
    
 
  
       
 
   
       
   

"""

# Add exactly ONE level of indent (4 spaces)  


new_lines=[]
for raw_line in peige_raw.split('\n'):
     
            
         
            
                        
        
          
            
                  
                        
                            
                
        
        

print(f'[INFO] New method has {len(new_lines)} lines')

# Replace  


result=lines[:start] + [ln+'\r\n' if not ln.endswith('\r\n') else ln for ln in new_lines] + lines[end:]

# Write back  



with open(FP,'w', encoding='utf⁸-sig', newline='') as f:


    
    
    

print('[DONE] Successfully replaced! Now restart your program to test.')
