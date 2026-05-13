# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\ui_builder.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find('def _refresh_alt_view(self, inner):')
print(f'Found _refresh_alt_view at: {idx}')

if idx > 0:
    before = content[:idx]
    last_blank = before.rfind('\n\n')
    last_newline = content.rfind('\n', 0, idx)
    # Remove from the blank line before status section to end
    cut_point = last_newline
    new_content = content[:cut_point] + '\n'
    print(f'New content ends with: {repr(new_content[-60:])}')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('ui_builder.py updated')
else:
    print('Not found')