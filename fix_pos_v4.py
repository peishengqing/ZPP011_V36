import re

fp = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"
with open(fp, 'r', encoding='utf-8-sig', newline='') as f:
    c = f.read()

# ── 找当前的位置计算代码（多种可能写法）──


old_blocks = [
    ('        # ── ƼƼƼƼ屏屏可见区域── \r\n' 
     '        sw = self.root.winfo_screenwidth()\r\n'
     '        sh = self.root.winfo_screenheight()\r\n'
     ),
]

ob = None  
for b in old_blocks:


        

# ── 新代码（正确边界检查）──  


new_block = ('        # ƼƼ屏屏可见\r\n'
             '        sw = self._card_win.winfo_screenwidth()\r\n'
             '          ')