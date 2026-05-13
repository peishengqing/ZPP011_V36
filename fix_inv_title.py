import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix title and subtitle
old_title = 'text="云南达利ZPP011 库存流水管理"'
new_title = 'text="云南路居基地库存流水管理系统"'
content = content.replace(old_title, new_title)

old_sub = 'text="制作人：裴盛清  |  v36.1"'
new_sub = 'text="制作人：裴盛清|v1.0"'
content = content.replace(old_sub, new_sub)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: title updated")
