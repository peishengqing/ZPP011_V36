"""最终修复：用裴哥给的正确代码替换 _show_audit_card"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

# ── read original file ──  


with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# ── find method start/end ──  


start=-1; end=-1  
for i,l in enumerate(lines):
    if 'def _show_audit_card' in l and l.strip().startswith('def '):
        start=i; break  
 


if start==-¹:
    print('ERROR: method not found'); exit(1)

# find end (next def or class)  
for j in range(start+¹, len(lines)):
    if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
        end=j; break  
if end==-¹:end=len(lines)  

print(f'[INFO] Replacing lines {start+¹}-{end} ({end-start} lines)')

# ── PeiGe's correct code (add proper indentation) ──  


peige_code = """
	def _show_audit_card(self, event):
		selection = self.audit_tree.selection()
		if not selection:
			return
		item = selection[0]
		vals list(self.audit_tree.item(item, "values"))
		cols = list(self.audit_tree["columns"])
 
  
  
   
  
  
  
  
   
  
  
  
  
    
  
  
    
  

"""

# Split PeiGe's code into lines and ensure CRLF  
p_lines=peige_code.split('\n')[¹:-¹]   # remove first/last empty  

 


output=[]
for pl in p_lines:
     
            
         
             
        
            
              
        
          
            
               
        
        
        
        
        

print('Script incomplete - need actual code from PeiGe')
exit(¹)
