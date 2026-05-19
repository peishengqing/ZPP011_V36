# -*- coding: utf-8 -*-
"""ZPP011-EXEC-v37.2-001 鏈€缁堟墽琛岃剼鏈?""
import os

# ============================================================
# 淇1: gui/events.py - _load_data_worker 娣诲姞鍒楀悕娓呯悊
# ============================================================
fp1 = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
with open(fp1, 'r', encoding='utf-8') as f:
    c1 = f.read()

# 娣诲姞鍒楀悕娓呯悊
old_load = """        dev_df = pd.read_excel(latest_file, sheet_name='瀹屾暣鍋忓樊鏄庣粏')
        if dev_df.empty:
            raise ValueError("鍋忓樊鏄庣粏宸ヤ綔琛ㄤ负绌?)

        # 4. 瑙ｆ瀽鍋忓樊鐜?""

new_load = """        dev_df = pd.read_excel(latest_file, sheet_name='瀹屾暣鍋忓樊鏄庣粏')
        if dev_df.empty:
            raise ValueError("鍋忓樊鏄庣粏宸ヤ綔琛ㄤ负绌?)

        # 鍒楀悕娓呯悊锛堝幓闄ょ┖鏍硷級
        dev_df.columns = [str(col).strip().replace(' ', '') for col in dev_df.columns]
        print(f"[DEBUG _load_data_worker] 鍒楀悕: {list(dev_df.columns)}", flush=True)

        # 4. 瑙ｆ瀽鍋忓樊鐜?""

if old_load in c1:
    c1 = c1.replace(old_load, new_load)
    print('1. OK: Added column cleaning in _load_data_worker')
else:
    print('1. SKIP')

# 娣诲姞鏃ユ湡鍒楁槧灏?old_date = """        # 鐢熸垚鍞竴ID
        audit_df['_uid'] = (
            audit_df['璁㈠崟鏃ユ湡'].astype(str).str[:10] + '_' +
            audit_df['娴佺▼璁㈠崟'].astype(str) + '_' +
            audit_df['缁勪欢鐗╂枡鍙?].astype(str)
        )"""

new_date = """        # 鏃ユ湡鍒楁槧灏?        if '璁㈠崟寮€濮嬫棩鏈? in audit_df.columns and '璁㈠崟鏃ユ湡' not in audit_df.columns:
            audit_df['璁㈠崟鏃ユ湡'] = audit_df['璁㈠崟寮€濮嬫棩鏈?].astype(str).str[:10]
        elif '璁㈠崟鏃ユ湡' not in audit_df.columns:
            audit_df['璁㈠崟鏃ユ湡'] = ''

        # 鐢熸垚鍞竴ID
        audit_df['_uid'] = (
            audit_df['璁㈠崟鏃ユ湡'].astype(str).str[:10] + '_' +
            audit_df['娴佺▼璁㈠崟'].astype(str) + '_' +
            audit_df['缁勪欢鐗╂枡鍙?].astype(str)
        )"""

if old_date in c1:
    c1 = c1.replace(old_date, new_date)
    print('2. OK: Added date column mapping')
else:
    print('2. SKIP')

with open(fp1, 'w', encoding='utf-8') as f:
    f.write(c1)

# ============================================================
# 淇2: gui/events.py - generate_ppt 澧炲己寮傚父鎹曡幏
# ============================================================
with open(fp1, 'r', encoding='utf-8') as f:
    c1 = f.read()

old_ppt = """        def worker():
            try:
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log)
                self.root.after(0, lambda: self._on_ppt_done(output_path))
            except Exception as e:
                self.root.after(0, lambda: self._on_ppt_error(str(e)))"""

new_ppt = """        def worker():
            try:
                import ppt_generator
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log)
                self.root.after(0, lambda: self._on_ppt_done(output_path))
            except ImportError as e:
                self.root.after(0, lambda e=e: self._on_ppt_error(f"缂哄皯渚濊禆 python-pptx锛歿e}"))
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                self.root.after(0, lambda e=e, err=err: self._on_ppt_error(f"鐢熸垚澶辫触锛歿e}\\n{err}"))"""

if old_ppt in c1:
    c1 = c1.replace(old_ppt, new_ppt)
    print('3. OK: Enhanced PPT exception handling')
else:
    print('3. SKIP')

# 娣诲姞璺緞鏍囧噯鍖?old_path = """        out_dir = self.output_dir.get() or os.path.dirname(excel_path)
        base = os.path.splitext(os.path.basename(excel_path))[0]
        output_path = os.path.join(out_dir, base + ".pptx")"""

new_path = """        out_dir = self.output_dir.get() or os.path.dirname(excel_path)
        base = os.path.splitext(os.path.basename(excel_path))[0]
        output_path = os.path.abspath(os.path.join(out_dir, base + ".pptx"))"""

if old_path in c1:
    c1 = c1.replace(old_path, new_path)
    print('4. OK: Added path normalization')
else:
    print('4. SKIP')

with open(fp1, 'w', encoding='utf-8') as f:
    f.write(c1)

# ============================================================
# 淇3: sheet2_alt.py - 娣诲姞 alt_names 璋冭瘯杈撳嚭
# ============================================================
fp2 = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\sheets\sheet2_alt.py'
with open(fp2, 'r', encoding='utf-8') as f:
    c2 = f.read()

# 鍦?converted_pairs 鍚庢坊鍔犺皟璇曡緭鍑?old_conv = """    print(f"[DEBUG do_analysis_v2] Sheet2瀹屾垚锛寋len(alt_df)} 琛?, flush=True)"""

new_conv = """    # 璋冭瘯杈撳嚭锛氭樉绀鸿浆鎹㈠悗鐨勯厤瀵规牱鏈?    if converted_pairs:
        print(f"[DEBUG] converted_pairs 鏍锋湰锛堝墠3锛夛細{converted_pairs[:3]}", flush=True)
    print(f"[DEBUG do_analysis_v2] Sheet2瀹屾垚锛寋len(alt_df)} 琛?, flush=True)"""

if old_conv in c2:
    c2 = c2.replace(old_conv, new_conv)
    print('5. OK: Added alt_names debug output')
else:
    print('5. SKIP')

with open(fp2, 'w', encoding='utf-8') as f:
    f.write(c2)

print('\\nAll fixes applied!')
