import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = 'from widgets import C, STEPS\nfrom analysis.analyzer import do_analysis_v2'
new = 'from widgets import C, STEPS\nfrom storage import storage\nfrom analysis.analyzer import do_analysis_v2'

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('FIXED')
else:
    print('NOT FOUND')
