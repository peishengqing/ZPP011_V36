import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. Check how analysis mode creates the title bar
with open(r'E:\zpp011_dev\模块化脚本\gui\ui_builder.py', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find('def build_ui')
if idx >= 0:
    print("=== build_ui (first 2000 chars) ===")
    print(content[idx:idx+2000])
else:
    print("build_ui not found, searching for title...")
    for keyword in ['title', '标题', '云南达利']:
        idx2 = content.find(keyword)
        if idx2 >= 0:
            print(f"\nFound '{keyword}' at {idx2}:")
            print(content[max(0,idx2-100):idx2+300])
