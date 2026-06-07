import re, ast, sys

path = r'E:\zpp011_dev\模块化脚本\gui\event_handlers\analysis_events.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

safe_func = '''

def _safe_for_gbk(text):
    if not text: return text
    result = []
    for c in text:
        try:
            c.encode('gbk')
            result.append(c)
        except UnicodeEncodeError:
            pass
    return ''.join(result)

'''

# Insert after 'import sys'
idx = text.find('import sys\n')
if idx < 0:
    sys.stdout.write('ERROR: import sys not found\n')
    sys.exit(1)
text = text[:idx+len('import sys\n')] + safe_func + text[idx+len('import sys\n'):]

# Find and wrap all messagebox calls
funcs = ['showerror', 'showwarning', 'showinfo', 'askyesno', 'askokcancel']
count = 0
idx = 0
while idx < len(text):
    found = None
    for fname in funcs:
        marker = 'messagebox.%s(' % fname
        pos = text.find(marker, idx)
        if pos >= 0 and (found is None or pos < found[0]):
            found = (pos, fname)
    
    if found is None:
        break
    
    pos, fname = found
    
    # Find the span of this call's argument list (from first '(' to matching ')')
    p_start = pos + len('messagebox.%s(' % fname)
    depth = 1
    p = p_start
    while depth > 0 and p < len(text):
        if text[p] == '(':
            depth += 1
        elif text[p] == ')':
            depth -= 1
        p += 1
    
    call = text[pos:p]  # includes up to and including the closing )
    
    # Parse title and body from the call
    # call = 'messagebox.FUNC("title", body)'
    q1 = call.find('"')
    q2 = call.find('"', q1 + 1) if q1 >= 0 else -1
    comma = call.find(',', q2) if q2 >= 0 else -1
    
    if q1 >= 0 and q2 >= 0 and comma >= 0:
        title = call[q1:q2+1]
        # Body is everything between comma and the final ')'
        body = call[comma+1:p-1].strip()
        new_call = 'messagebox.%s(_safe_for_gbk(%s), _safe_for_gbk(%s))' % (fname, title, body)
        text = text[:pos] + new_call + text[p:]
        p = pos + len(new_call)
        count += 1
    else:
        p = p_start
    
    idx = p

sys.stdout.write('Wrapped %d messagebox calls\n' % count)

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(text)

with open(path, 'rb') as f:
    raw = f.read()
sys.stdout.write('Nulls: %d, Size: %d\n' % (raw.count(b'\x00'), len(raw)))
try:
    with open(path, 'r', encoding='utf-8') as f:
        ast.parse(f.read())
    sys.stdout.write('Syntax OK\n')
except SyntaxError as e:
    sys.stdout.write('SYNTAX ERROR line %d: %s\n' % (e.lineno, e.msg))
    lines = open(path, 'r', encoding='utf-8').read().split('\r\n')
    sys.stdout.write('Line: %r\n' % lines[e.lineno-1])
