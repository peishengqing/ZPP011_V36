import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\inventory_loader.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix: add "物料" to the aliases for "物料编码"
old = '"物料编码": ["物料编码", "物料号", "料号", "产品编码"]'
new = '"物料编码": ["物料编码", "物料号", "料号", "产品编码", "物料"]'

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("FIXED: Added '物料' alias for '物料编码'")
else:
    print("Pattern not found! Searching...")
    idx = content.find('"物料编码"')
    if idx >= 0:
        print(content[idx:idx+80])
