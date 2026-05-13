import sys, os
with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the inventory mode branch in run_app
idx = content.find('InventoryView')
if idx >= 0:
    print("=== InventoryView usage in run_app ===")
    print(content[max(0,idx-200):idx+200])
else:
    print("NOT FOUND")
