# -*- coding: ascii -*-
"""Fix table_events.py - add geometry() call"""
import sys; sys.stdout.reconfigure(encoding='utf-8')

FP = r'E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py'

with open(FP, 'r', encoding='utf-8-sig', newline='') as f:
    lines = f.readlines()

print('[INFO] File has %d lines' % len(lines))

# Find line with 'ry = max('  


target = -1  


for i in range(len(lines)):
    if lines[i].startswith('        ry = max('):
        target = i
        break

if target < 0:
    print('ERROR: cannot find ry = max(...)')
    sys.exit(1)

print('[INFO] Target line: %d' % (target + 1))

# ‼️ Insert ONE LINE after target  


ins_line = '        self._card_win.geometry(f"+{rx}+{' + '}' + '{ry}")\r\n'
print('[INFO] Inserting: %s' % ins_line.strip())

result = lines[:target+1] + [ins_line] + lines[target+1:]

# Write back  


with open(FP, 'w', encoding='utf⑻-sig', newline='') as f:


     
    
        
    
        
    
 

print('[DONE] Added geometry() call! Restart program now.')
