# -*- coding: utf-8 -*-
"""淇 ppt_generator.py 鏀寔 progress_cb 杩涘害鍥炶皟"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝ppt_generator.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇1: 淇敼鍑芥暟绛惧悕锛屾坊鍔?progress_cb 鍙傛暟
old_sig = 'def run_ppt_generation(excel_path, output_path, log_cb=None):'
new_sig = 'def run_ppt_generation(excel_path, output_path, log_cb=None, progress_cb=None):'

if old_sig in content:
    content = content.replace(old_sig, new_sig)
    print('OK: Added progress_cb parameter')
else:
    print('SKIP: Function signature not found')

# 淇2: 鍦ㄥ叧閿楠ゆ坊鍔犺繘搴﹀洖璋冿紙鏁版嵁璇诲彇瀹屾垚鍚庯級
old_after_read = '''        info_df = safe_read('鍒嗘瀽璇存槑')
        trend_df = safe_read('瓒嬪娍鍒嗘瀽')

        if not summary_df.empty:'''

new_after_read = '''        info_df = safe_read('鍒嗘瀽璇存槑')
        trend_df = safe_read('瓒嬪娍鍒嗘瀽')
        
        # 杩涘害鍥炶皟锛氭暟鎹鍙栧畬鎴?        if progress_cb:
            progress_cb(10, 100, "鏁版嵁璇诲彇瀹屾垚")
        
        if not summary_df.empty:'''

if old_after_read in content:
    content = content.replace(old_after_read, new_after_read)
    print('OK: Added progress callback after data read')
else:
    print('SKIP: Data read section not found')

# 淇3: 鍦ㄦ櫤鑳借В璇荤敓鎴愬悗娣诲姞杩涘害鍥炶皟
old_after_summary = '''        _log(f"  [PPT] 鏅鸿兘瑙ｈ鐢熸垚瀹屾垚 ({len(summary_text)} 瀛楃)")

        # 鍒涘缓 PPT'''

new_after_summary = '''        _log(f"  [PPT] 鏅鸿兘瑙ｈ鐢熸垚瀹屾垚 ({len(summary_text)} 瀛楃)")
        
        # 杩涘害鍥炶皟锛氬紑濮嬪垱寤篜PT
        if progress_cb:
            progress_cb(20, 100, "寮€濮嬬敓鎴怭PT...")

        # 鍒涘缓 PPT'''

if old_after_summary in content:
    content = content.replace(old_after_summary, new_after_summary)
    print('OK: Added progress callback after summary')
else:
    print('SKIP: Summary section not found')

# 淇4: 鍦ㄤ繚瀛樺墠娣诲姞杩涘害鍥炶皟
old_before_save = '''        prs.save(output_path)
        _log(f"[PPT] 璇︾粏姹囨姤 PPT 宸蹭繚瀛? {output_path} (鍏眥len(prs.slides)}椤?")'''

new_before_save = '''        # 杩涘害鍥炶皟锛氬嵆灏嗕繚瀛?        if progress_cb:
            progress_cb(90, 100, "姝ｅ湪淇濆瓨鏂囦欢...")
        
        prs.save(output_path)
        
        # 杩涘害鍥炶皟锛氬畬鎴?        if progress_cb:
            progress_cb(100, 100, "瀹屾垚")
        
        _log(f"[PPT] 璇︾粏姹囨姤 PPT 宸蹭繚瀛? {output_path} (鍏眥len(prs.slides)}椤?")'''

if old_before_save in content:
    content = content.replace(old_before_save, new_before_save)
    print('OK: Added progress callback before save')
else:
    print('SKIP: Save section not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')

