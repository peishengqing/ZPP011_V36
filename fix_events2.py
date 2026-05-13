# -*- coding: utf-8 -*-
import sys, io, re
sys.stdout.reconfigure(encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = []

# Fix 1: admin column hardcoded ''
old = "                    '',  # admin (生产管理员)"
new = "                    str(row.get('车间', '')),  # admin (生产管理员)"
if old in content:
    content = content.replace(old, new, 1)
    changes.append("Fix1: admin column from 车间")
else:
    changes.append("Fix1 FAILED")

# Fix 2: save_audit_btn not enabled
old = "            for btn_name in ['audit_ai_btn', 'audit_export_btn', 'unified_ai_btn', 'unified_export_btn']:"
new = "            for btn_name in ['audit_ai_btn', 'audit_export_btn', 'unified_ai_btn', 'unified_export_btn', 'save_audit_btn']:"
if old in content:
    content = content.replace(old, new, 1)
    changes.append("Fix2: add save_audit_btn")
else:
    changes.append("Fix2 FAILED")

print("Changes:", changes)
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("done")