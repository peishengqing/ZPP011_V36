# -*- coding: utf-8 -*-
"""淇 analyzer.py do_analysis_v2 杩斿洖璺緞闂"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇1: 鍦?report_progress(11, "鐢熸垚Excel", 50) 涔嬪墠娣诲姞璺緞楠岃瘉
old_start = '''    report_progress(11, "鐢熸垚Excel", 50)

    # 鈹€鈹€ 鍒嗘瀽璇存槑 sheet 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€'''

new_start = '''    report_progress(11, "鐢熸垚Excel", 50)

    # ---------- 纭畾杈撳嚭璺緞 ----------
    if output_path:
        final_output_path = output_path
    else:
        # 纭繚杈撳嚭鐩綍鏈夋晥
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = os.path.dirname(input_file) or os.path.expanduser('~')
        pattern = os.path.join(output_dir, f'ZPP011鍋忓樊鍒嗘瀽鏈€缁堢増_{date_range}_v*.xlsx')
        existing = _glob.glob(pattern)
        versions = [int(re.search(r'_v(\d+)\.xlsx$', os.path.basename(f)).group(1))
                    for f in existing if re.search(r'_v(\d+)\.xlsx$', os.path.basename(f))]
        next_ver = max(versions) + 1 if versions else 1
        final_output_path = os.path.join(
            output_dir,
            f'ZPP011鍋忓樊鍒嗘瀽鏈€缁堢増_{date_range}_v{next_ver:02d}.xlsx'
        )

    # 纭繚鐩綍瀛樺湪
    os.makedirs(os.path.dirname(final_output_path), exist_ok=True)

    # 鈹€鈹€ 鍒嗘瀽璇存槑 sheet 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€'''

if old_start in content:
    content = content.replace(old_start, new_start)
    print('OK: Added path validation before save')
else:
    print('SKIP: Start pattern not found')

# 淇2: 鍦?return 涔嬪墠娣诲姞鏈€缁堥獙璇?old_return = '''    report_progress(11, "鐢熸垚Excel", 100)
    # 杩斿洖瀹為檯淇濆瓨鐨勮矾寰?    _dprint(f"[DEBUG do_analysis_v2] 淇濆瓨瀹屾垚锛岃繑鍥烇細{final_output_path}", flush=True)
    return final_output_path'''

new_return = '''    report_progress(11, "鐢熸垚Excel", 100)
    
    # 鏈€缁堥獙璇?    if not final_output_path:
        raise RuntimeError("final_output_path is None锛岃矾寰勭敓鎴愬け璐?)
    
    if not os.path.exists(final_output_path):
        raise RuntimeError(f"鏂囦欢淇濆瓨澶辫触锛岃矾寰勪笉瀛樺湪锛歿final_output_path}")

    _dprint(f"[DEBUG do_analysis_v2] 淇濆瓨瀹屾垚锛岃繑鍥烇細{final_output_path}", flush=True)
    return final_output_path'''

if old_return in content:
    content = content.replace(old_return, new_return)
    print('OK: Added final validation')
else:
    print('SKIP: Return pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
