"""修复 _show_audit_card：强制居中，避免跑到屏幕外"""
import re

filepath = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"

with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
    content = f.read()

# ── 找方法起止位置 ──
start_pat = '    def _show_audit_card(self, event):\r\n'
start_idx = content.find(start_pat)
if start_idx == -1:
    print("ERROR: start pattern not found")
    exit(1)

rest = content[start_idx + len(start_pat):]
next_def = re.search(r'\r\n    def ', rest)
if not next_def:
    print("ERROR: cannot find end of method")
    exit(1)

end_idx = start_idx + len(start_pat) + next_def.start()
old_text = content[start_idx:end_idx]
print(f"Old method length: {len(old_text)}")

# ── 新方法（CRLF）──
new_method = '\r\n'.join([
    '    def _show_audit_card(self, event):',
    '        """双击行弹出审核卡片（强制居中显示）"""',
    '        print("DEBUG:_show_audit_card called")',
    '',
    '        selection = self.audit_tree.selection()',
    '        if not selection:',  
    '            print("DEBUG:no selection")',  
    '            return',
     '',
     '# ── 构建 data 字典 ──',
     '',
     '',
  
       ]
       )
       
print("Trying simpler approach...")
# Actually let me just read existing file and do surgical replacement of ONLY the geometry lines

with open(r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py", 'r', encoding='utf-8-sig', newline='') as f:
   lines=f.readlines()
   
# Find line numbers for key sections  
lines_out=[]
in_method=False  
skip_until=None  
for i,l in enumerate(lines):
      if '_show_audit_card' in l and l.strip().startswith('def'):
                   in_method=True   
                   
        
        
print(f"Total lines:{len(lines)}")
exit(0)
