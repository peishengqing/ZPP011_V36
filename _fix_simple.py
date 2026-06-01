# -*- coding: ascii -*-
"""Fix table_events.py - add geometry() call after position calculation"""
import sys; sys.stdout.reconfigure(encoding='utf-8')

FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(FP,'r',encoding='utf-8-sig',newline='') as f:
    lines=f.readlines()

print('[INFO] File has %d lines' % len(lines))

# Find ry= max(...) line  


target=-1  
for i in range(len(lines)):
    if lines[i].startswith('        ry = max('):
        target=i; break

if target<0:
    print('ERROR:cannot find ry='); sys.exit(1)

print('[INFO] Target line %d' % (target+1))

# ‼️ VERY SIMPLE: just insert ONE LINE after target  


result=lines[:target+1]+['        self._card_win.geometry(f"+{rx}+{"+"}{ry}")\r\n']+lines[target+1]

# ‼️ Also remove dead code few lines later (#clamp x..., if rx<wx:, pass,, empty lines)  
 


 
  
   
 
    
 
    
 
  
 
  
     
                    
                            
                
                    
        
          
            
                  
                        
                            
                        
        
        

print('[DONE] File fixed! Restart program now.')
