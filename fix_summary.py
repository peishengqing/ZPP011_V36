import re

with open('gui_pyside6/main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 _update_summary 方法的起止行
start = None
end = None
for i, line in enumerate(lines):
    if '    def _update_summary(self):' in line:
        start = i
    elif start is not None and end is None:
        if line.startswith('    def ') and i > start:
            end = i
            break

print(f'start={start}, end={end}')
if start is not None:
    print('当前方法内容:')
    for i in range(start, min(end, start+70)):
        print(f'{i+1}: {repr(lines[i])}')
