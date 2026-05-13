import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'E:\zpp011_dev\模块化脚本\gui\app.py', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find('class ModeSelector')
if idx >= 0:
    print(content[idx:idx+2000])
else:
    print("ModeSelector class not found!")
    # Search for it
    idx2 = content.find('ModeSelector')
    if idx2 >= 0:
        print(f"Found 'ModeSelector' at {idx2}: {content[max(0,idx2-50):idx2+200]}")
