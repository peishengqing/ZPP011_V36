import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find ModeSelector logic in run_app
idx = content.find('def run_app')
# Search for mode/ModeSelector/mode.json after run_app
search_from = idx
keywords = ['mode', 'ModeSelector', 'mode.json', 'default_mode', 'inventory', 'analysis']
for kw in keywords:
    pos = content.find(kw, search_from)
    if pos >= 0 and pos < idx + 4000:
        start = max(search_from, pos - 30)
        end = min(len(content), pos + 200)
        snippet = content[start:end]
        print(f'--- Found "{kw}" at {pos} ---')
        print(snippet)
        print()
