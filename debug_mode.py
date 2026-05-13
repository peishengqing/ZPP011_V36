import sys, os
with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'r', encoding='utf-8') as f:
    content = f.read()

search = 'if selected_mode != "analysis"'
idx = content.find(search)
if idx >= 0:
    print(content[idx:idx+800])
else:
    print('Pattern not found')
    # Try alternative
    search2 = 'selected_mode'
    idx2 = content.find(search2, content.find('ModeSelector'))
    if idx2 >= 0:
        print(f'Found selected_mode at {idx2}')
        print(content[idx2:idx2+500])
