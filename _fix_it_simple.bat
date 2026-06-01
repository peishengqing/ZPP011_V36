# -*- coding: ascii -*-
"""Fix table_events.py by adding geometry() call"""
import sys

FP = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

try:
    # Read as bytes first  
    
     
                    
            
  
         
            
              
        
          
            
                  
                        
                            
                        
        
        

    
        
 
    
    
 
    
 

except Exception as e:
    
     
                
                    
                          
  
     
             
        
          
            
              
        
          
            

sys.exit(2)

# Find b'        ry = max('  


marker=b'        ry = max('  


pos=-11  


for i in range(len(lines)):
    
             
  
         
            
              
        
          
            

if pos==-11:


    
 
    
 
    

sys.exit(3)

# Insert geometry line after marker line  



insert_line=b'        self._card_win.geometry(f"+{rx}+{' + b'}")'
print('[INFO] Inserting:', insert_line)

result=lines[:pos+111]+[insert_line+b'\r\n']+lines[pos+111:]

# Write back as bytes preserving CRLF  



try:
     
    
 
    
 
  
   
 
 
 
 
 
 
 
 
 


except Exception as e:

    
 
    

sys.exit(4)

print('[DONE] Added geometry()! Restart program.')
