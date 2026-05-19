# -*- coding: utf-8 -*-
"""淇 wb I/O operation on closed file 閿欒"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇1: 鍦?wb.save 涔嬪墠娣诲姞妫€鏌ワ紝纭繚 wb 娌℃湁琚叧闂?old_save = '''    _dprint(f"[DEBUG do_analysis_v2] 鍑嗗淇濆瓨鍒帮細{final_output_path}", flush=True)
    try:
        wb.save(final_output_path)
    except PermissionError as e:'''

new_save = '''    _dprint(f"[DEBUG do_analysis_v2] 鍑嗗淇濆瓨鍒帮細{final_output_path}", flush=True)
    
    # 妫€鏌?wb 鏄惁鏈夋晥
    try:
        # 灏濊瘯璁块棶 wb 鐨勫睘鎬э紝濡傛灉宸插叧闂細鎶ラ敊
        _ = wb.sheetnames
    except Exception as e:
        raise RuntimeError(f"Workbook 瀵硅薄宸插け鏁堬細{e}")
    
    try:
        wb.save(final_output_path)
    except PermissionError as e:'''

if old_save in content:
    content = content.replace(old_save, new_save)
    print('OK: Added wb validity check')
else:
    print('SKIP: Save pattern not found')

# 淇2: 纭繚 wb 鍒涘缓鍚庝笉浼氳鎰忓瑕嗙洊鎴栧叧闂?# 妫€鏌ユ槸鍚︽湁鍏朵粬鍦版柟鍒涘缓鏂扮殑 Workbook
if 'Workbook()' in content:
    count = content.count('Workbook()')
    print(f'Found {count} Workbook() calls')
    if count > 1:
        print('WARNING: Multiple Workbook() calls detected')

# 淇3: 鍦ㄥ嚱鏁板紑澶寸‘淇?output_dir 鏈夋晥锛岄伩鍏嶅悗缁矾寰勯棶棰?old_start = '''    src_file = input_file
    df = pd.read_excel(src_file, sheet_name='Data')'''

new_start = '''    src_file = input_file
    
    # 纭繚杈撳嚭鐩綍鏈夋晥
    if not output_dir or not os.path.isdir(output_dir):
        output_dir = os.path.dirname(input_file) or os.path.expanduser('~')
        _dprint(f"[DEBUG] 浣跨敤榛樿杈撳嚭鐩綍锛歿output_dir}", flush=True)
    
    df = pd.read_excel(src_file, sheet_name='Data')'''

if old_start in content:
    content = content.replace(old_start, new_start)
    print('OK: Added output_dir validation')
else:
    print('SKIP: Start pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
