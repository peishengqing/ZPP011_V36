import sys

filepath = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
    content = f.read()

# ── 要替换的旧代码块（位置计算部分）──  


old_pos = '''        self.root.update_idletasks()
        rx = self.root.winfo_rootx() + self.root.winfo_width() + 5\n        ry = self.root.winfo_rooty() + 100\n        sefl._card_win.geometry(f\"+{rx}+ry}\")'''

print('Try simple approach...')
# Let me just find by line number instead  

lines=content.split('\r\n')
print(f'Total lines: {len(lines)}')
for i,l in enumerate(lines):
    if 'winfo_rootx' in l or 'winfo_rooty' in l or '+{rx}+' in l.replace(' ','') : 
           print(f'{i}: {l}')