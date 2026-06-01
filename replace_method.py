"""replace _show_audit_card with PeiGe's correct version"""
FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

# ── locate old method ──  


start=-1; end=-1  


for i,l in enumerate(lines):
    if '_show_audit_card' in l and l.strip().startswith('def '):
        start=i; break  
 


for j in range(start+1, len(lines)):
    if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):  
        end=j; break  


if end==-1:end=len(lines)  

print(f'[INFO] Replacing lines {start}-{end-1} ({end-start} lines)')

# ── PeiGe's new method (add correct indent) ──  


new_method_raw = r"""    def _show_audit_card(self, event):
 
            return
 
            item = selection[0]
            vals = self.audit_tree.item(item, "values")
            cols = list(self.audit_tree["columns"])

            # Ƽ齐或截断 vals               
        
    
    
    
                        
                
    
            
                    
                    
        
            
          
            
        
         
            
        
        
            
        
          
            
        
        
            
        
        
                
                    
                        




print('Not implemented yet')
exit(1)
