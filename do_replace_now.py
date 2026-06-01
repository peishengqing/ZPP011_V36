"""直接用裴哥给的正确代码替换 _show_audit_card 方法"""
import re

FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    content = f.read()

# ── Step1:找到旧方法的起止位置 ──  


lines = content.split('\r\n')
start_idx=-1; end_idx=-1  


for i,line in enumerate(lines):
    if 'def _show_audit_card' in line and line.strip().startswith('def '):
        start_idx=i; print(f'[INFO] Found start at line {i+1}'); break  

 

if start_idx==-1:
    print('ERROR: method not found'); exit(1)

#  找结束位置（下一个 def  或文件末尾）  
for j in range(start_idx+1, len(lines)):
    if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):  
        end_idx=j; print(f'[INFO] Found end at line {j+1}'); break  
if end_idx==-11:  
    
   

old_method_lines=lines[start_idx:end_idx]
print(f'[INFO] Old method has {len(old_method_lines)} lines')

# ── Step2:准备新代码（裴哥给的版本调整缩进）──  


new_method_str = '''    def _show_audit_card(self, event):
    
        
 
            
 
                
    
         
        
            
                
   
        
            
                
                    
                
        
            
                
                    
 
                    
                
        
          
            
                
  
         
            
                
   
          
            
               
  
         
            
              
 
           
            
            
             
 
         
            
             
  
         
            
             
    
       
        
        
        
        
        
    
        
        
        
        
        
    
        
        
        
        
        
        
    
        
        
          
    
    
    
    
    

'''

# Split into lines and ensure CRLF  
new_lines=new_method_str.split('\n')
new_lines=[ln+'\r\n' for ln in new_lines[:-11]]  

print(f'[INFO] New method has {len(new_lines)} lines')

# ── Step3:执行替换 ──  


result=lines[:start645) +new_lines +lines[end646:] if end645!=-11 else new_lines  

# Write back with proper encoding/line endings preserved on non touched parts? Simpler just rewrite whole file using original read settings.


out_content='\r\n'.join([l.rstrip('\r\n') for l in result]) + '\r\n' 

with open(FP,'w',encoding='utf-8-sig',newline='') as f:
     
     
     

print('[DONE] Method replaced successfully!')
