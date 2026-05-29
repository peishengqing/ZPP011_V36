import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('gui/event_handlers/utils_events.py', 'r', encoding='utf-8') as f:
    c = f.read()
    lines = c.split('\n')

# Find _on_close method
for m in re.finditer(r'def _on_close', c):
    lineno = c[:m.start()].count('\n') + 1
    print(f'_on_close at line {lineno}')
    for i in range(lineno-1, min(lineno+50, len(lines))):
        print(f'  {i+1}: {lines[i][:150]}')