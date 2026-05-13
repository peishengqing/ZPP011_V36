# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = []

# Fix 1: _filter_audit_tree values tuple (行 2634/2635)
# Position 13 (0-indexed) is orig_remark → audit_result
# Position 14 (0-indexed) is ai_suggest → AI建议
# Original (correct order):
#   13: orig_remark  ← WRONG, should be audit_result
#   14: AI建议       ← correct but labeled ai_suggest
# The audit_result col should come BEFORE AI建议 in the values tuple
old1 = "                remark,  # remark\n                batch_remark,  # batch_remark\n                str(row.get('原备注', ''))[:30],  # orig_remark\n                str(row.get('AI建议', ''))[:50],  # ai_suggest"
new1 = "                remark,  # remark\n                batch_remark,  # batch_remark\n                str(row.get('audit_result', ''))[:30],  # audit_result\n                str(row.get('AI建议', ''))[:50],  # AI建议"
if old1 in content:
    changes.append("Fix1: _filter_audit_tree audit_result position")
    content = content.replace(old1, new1, 1)
else:
    print("Fix1 NOT found - checking raw content...")
    # Let's find the exact text
    idx = content.find("remark,  # remark\n                batch_remark,  # batch_remark")
    if idx >= 0:
        snippet = content[idx:idx+200]
        print(repr(snippet))

# Fix 2: _refresh_audit_tree values tuple
# Current (行 3065-3066):
#   str(row.get('audit_result', '')),
#   str(row.get('AI建议', '')),
# Should be swapped (audit_result should be col 14, AI建议 should be col 13)
old2 = "                str(row.get('audit_result', '')),\n                str(row.get('AI建议', '')),"
new2 = "                str(row.get('AI建议', '')),\n                str(row.get('audit_result', '')),"
if old2 in content:
    changes.append("Fix2: _refresh_audit_tree audit_result position")
    content = content.replace(old2, new2, 1)
else:
    print("Fix2 NOT found - checking...")
    idx2 = content.find("str(row.get('audit_result', '')),\n                str(row.get('AI建议', '')),")
    if idx2 >= 0:
        snippet2 = content[idx2:idx2+150]
        print(repr(snippet2))
    else:
        print("Fix2 text not found at all")

print("Changes made:", changes)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("events.py written")