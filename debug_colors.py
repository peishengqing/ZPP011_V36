import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'E:\zpp011_dev\模块化脚本\widgets.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find C dict
idx = content.find('C = {')
if idx >= 0:
    print("=== C (color/theme) dict ===")
    print(content[idx:idx+800])
