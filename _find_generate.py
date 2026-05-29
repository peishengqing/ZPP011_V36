import sys, re
sys.stdout.reconfigure(encoding='utf-8')

# Search for event_generate or any mechanism that creates this virtual event
import glob
for fp in glob.glob('**/*.py', recursive=True):
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            c = f.read()
        for m in re.finditer(r'event_generate|TreeviewColumn', c):
            lineno = c[:m.start()].count('\n') + 1
            lines = c.split('\n')
            line_text = lines[lineno-1][:150]
            if 'ColumnResized' in line_text or 'event_generate' in line_text:
                print(f'{fp} Line {lineno}: {line_text}')
    except:
        pass