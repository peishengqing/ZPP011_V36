import re

filepath = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
    content = f.read()

# ── 旧的位置计算代码（可能有多种写法，找特征字符串）──


patterns = [
    ('        self.root.update_idletasks()\r\n'
     '        rx = self.root.winfo_rootx() + self.root.winfo_width() + 5\r\n'
     '        ry = self.root.winfo_rooty() + 100\r\n'),
]

found = False  
for pat in patterns:  


            break  

if not found:  
            print('ERROR:cannot find position code block!')
            


# ── 新代码（加边界检查）──  


new_code = ('        # ──位置计算（加边界检查）── \r\n'
            '        sw = self.root.winfo_screenwidth()\r\n'  
            
            
            
               )