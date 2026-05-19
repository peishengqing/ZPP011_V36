# -*- coding: utf-8 -*-
"""淇 analyzer.py 涓?os 瀵煎叆闂"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇1: 鍦?do_analysis_v2 鍑芥暟寮€澶存坊鍔犲鍏?old_start = '''def do_analysis_v2(
        input_file,
        output_dir,
        alt_pairs,
        progress_callback=None,
        cancel_check=None,
        start_date=None,
        end_date=None,
        material_search=None,
        output_path=None):
    _dprint("[DEBUG do_analysis_v2] 鍑芥暟寮€濮嬫墽琛?, flush=True)'''

new_start = '''def do_analysis_v2(
        input_file,
        output_dir,
        alt_pairs,
        progress_callback=None,
        cancel_check=None,
        start_date=None,
        end_date=None,
        material_search=None,
        output_path=None):
    # 纭繚鍑芥暟鍐呴儴鍙互璁块棶杩欎簺妯″潡
    import os
    import re
    import glob as _glob
    
    _dprint("[DEBUG do_analysis_v2] 鍑芥暟寮€濮嬫墽琛?, flush=True)'''

if old_start in content:
    content = content.replace(old_start, new_start)
    print('OK: Added imports at function start')
else:
    print('SKIP: Function start pattern not found')

# 淇2: 鍒犻櫎鍑芥暟鍐呴儴鐨勯噸澶?import os
old_debug_import = '''    # DEBUG: Log input DataFrame info
    import os
    _debug_log = os.path.join'''

new_debug_import = '''    # DEBUG: Log input DataFrame info
    _debug_log = os.path.join'''

if old_debug_import in content:
    content = content.replace(old_debug_import, new_debug_import)
    print('OK: Removed duplicate import os')
else:
    print('SKIP: Debug import pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
