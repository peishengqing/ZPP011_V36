#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?
result = subprocess.run(['git', 'checkout', 'HEAD', '--', '.'], cwd=root, capture_output=True, text=True)
if result.returncode == 0:
    print('SUCCESS: All files restored from git')
else:
    print(f'FAILED: {result.stderr}')
