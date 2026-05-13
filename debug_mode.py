import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

mode_paths = [
    r'C:\Users\Administrator\.zpp011_audit\mode.json',
    r'E:\zpp011_dev\模块化脚本\config\.zpp011_audit\mode.json',
]
for p in mode_paths:
    if os.path.exists(p):
        with open(p, 'rb') as f:
            raw = f.read()
        print(f'Found: {p}')
        print(f'  Raw bytes: {raw[:120]}')
        has_bom = raw[:3] == b'\xef\xbb\xbf'
        print(f'  Has BOM: {has_bom}')
        if has_bom:
            data = json.loads(raw[3:])
        else:
            try:
                data = json.loads(raw)
            except Exception as e:
                data = f'JSON error: {e}'
        print(f'  Data: {data}')
    else:
        print(f'Not found: {p}')

# Check run_app logic
with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'r', encoding='utf-8') as f:
    content = f.read()
idx = content.find('def run_app')
print('\n=== run_app ===')
print(content[idx:idx+1500])
