import sys, re
sys.stdout.reconfigure(encoding='utf-8')

# Search all files for TreeviewColumnResized
import glob
for fp in glob.glob('**/*.py', recursive=True):
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            c = f.read()
        for m in re.finditer(r'TreeviewColumnResized', c):
            lineno = c[:m.start()].count('\n') + 1
            lines = c.split('\n')
            print(f'{fp} Line {lineno}: {lines[lineno-1][:150]}')
    except:
        pass