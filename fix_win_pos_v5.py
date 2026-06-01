"""修复 _show_audit_card 窗口位置（边界检查）"""
import os

fp = r"E:\zpp011_dev\模块化脚本\gui\event_handlers\table_events.py"
with open(fp, 'r', encoding='utf-8-sig', newline='') as f:
    content = f.read()

# ── Old buggy position calculation ──


old_code_lines = [
    '        # ── ƼƼ屏屏可见── \r\n',
    '        sw = self._card_win.winfo_screenwidth()'
]

# Check if old code exists  
old_marker = '        # ── ƼƼ'
if old_marker in content:
    print('Found old marker')
else:
    print('Old marker not found, searching...')
    