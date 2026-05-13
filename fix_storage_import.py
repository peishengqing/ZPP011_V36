import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add storage import after the widgets import line
old_import = 'from widgets import C, STEPS\nimport time'
new_import = 'from widgets import C, STEPS\nfrom storage import storage\nimport time'

if old_import in content:
    content = content.replace(old_import, new_import)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('FIXED: added "from storage import storage" to events.py')
else:
    print('Pattern not found for import')
    idx = content.find('from widgets')
    if idx >= 0:
        print(f'Context: {repr(content[idx:idx+60])}')
