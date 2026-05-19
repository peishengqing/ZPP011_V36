# -*- coding: utf-8 -*-
"""淇 _load_data_worker 鍒楀悕闂 v2"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇1: 璇诲彇Excel鍚庢坊鍔犲垪鍚嶆竻鐞嗗拰鍔ㄦ€佸垪鍚嶆煡鎵?old_read = '''        # 3. 璇诲彇
        dev_df = pd.read_excel(latest_file, sheet_name='瀹屾暣鍋忓樊鏄庣粏')
        if dev_df.empty:
            raise ValueError("鍋忓樊鏄庣粏宸ヤ綔琛ㄤ负绌?)

        # 4. 瑙ｆ瀽鍋忓樊鐜?        def parse_rate(v):
            if isinstance(v, str):
                return float(v.replace('%','').replace('锛?,'>').replace('>','')) / 100
            return abs(float(v)) if pd.notna(v) else 0
        dev_df['鍋忓樊鐜囨暟鍊?] = dev_df['鍋忓樊鐜?].apply(parse_rate)'''

new_read = '''        # 3. 璇诲彇
        dev_df = pd.read_excel(latest_file, sheet_name='瀹屾暣鍋忓樊鏄庣粏')
        if dev_df.empty:
            raise ValueError("鍋忓樊鏄庣粏宸ヤ綔琛ㄤ负绌?)

        # 娓呯悊鍒楀悕锛堝幓闄ょ┖鏍硷級
        dev_df.columns = [str(col).strip().replace(' ', '') for col in dev_df.columns]
        print(f"[DEBUG _load_data_worker] 鍒楀悕: {list(dev_df.columns)}", flush=True)

        # 4. 瑙ｆ瀽鍋忓樊鐜囷紙鍔ㄦ€佹煡鎵惧垪鍚嶏級
        def parse_rate(v):
            if isinstance(v, str):
                return float(v.replace('%','').replace('锛?,'>').replace('>','')) / 100
            return abs(float(v)) if pd.notna(v) else 0
        
        rate_col = None
        for col in ['鍋忓樊鐜?, '鍋忓樊鐜?%)', '鍋忓樊鐜囷紙%锛?]:
            if col in dev_df.columns:
                rate_col = col
                break
        
        if rate_col:
            dev_df['鍋忓樊鐜囨暟鍊?] = dev_df[rate_col].apply(parse_rate)
            print(f"[DEBUG] 浣跨敤鍋忓樊鐜囧垪: {rate_col}", flush=True)
        else:
            dev_df['鍋忓樊鐜囨暟鍊?] = 0.0
            print("[WARN] 鏈壘鍒板亸宸巼鍒楋紝璁句负0", flush=True)'''

if old_read in content:
    content = content.replace(old_read, new_read)
    print('OK: Added column cleaning and dynamic rate column')
else:
    print('SKIP: Read pattern not found')

# 淇2: 鍔ㄦ€佹煡鎵炬棩鏈熷垪
old_date = '''        # 鐢熸垚鍞竴ID
        audit_df['_uid'] = (
            audit_df['璁㈠崟鏃ユ湡'].astype(str).str[:10] + '_' +
            audit_df['娴佺▼璁㈠崟'].astype(str) + '_' +
            audit_df['缁勪欢鐗╂枡鍙?].astype(str)
        )'''

new_date = '''        # 鍔ㄦ€佹煡鎵炬棩鏈熷垪
        date_col = None
        for col in ['璁㈠崟寮€濮嬫棩鏈?, '璁㈠崟鏃ユ湡', '鏃ユ湡']:
            if col in audit_df.columns:
                date_col = col
                break
        
        if date_col and date_col != '璁㈠崟鏃ユ湡':
            audit_df['璁㈠崟鏃ユ湡'] = pd.to_datetime(audit_df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
        elif '璁㈠崟鏃ユ湡' not in audit_df.columns:
            audit_df['璁㈠崟鏃ユ湡'] = ''
        
        # 鐢熸垚鍞竴ID
        audit_df['_uid'] = (
            audit_df['璁㈠崟鏃ユ湡'].astype(str).str[:10] + '_' +
            audit_df['娴佺▼璁㈠崟'].astype(str) + '_' +
            audit_df['缁勪欢鐗╂枡鍙?].astype(str)
        )'''

if old_date in content:
    content = content.replace(old_date, new_date)
    print('OK: Added dynamic date column')
else:
    print('SKIP: Date pattern not found')

# 淇3: 鍦?_on_load_done 涓坊鍔犺皟璇曟棩蹇?old_done = '''            self.audit_data = result_df
            self._full_dev_df = result_df.copy()'''

new_done = '''            self.audit_data = result_df
            self._full_dev_df = result_df.copy()
            
            # 璋冭瘯鏃ュ織
            print(f"[DEBUG _on_load_done] 鍔犺浇 {len(result_df)} 琛?, flush=True)
            print(f"[DEBUG] 鍒楀悕: {list(result_df.columns)}", flush=True)
            if len(result_df) > 0:
                print(f"[DEBUG] 鍓?琛? {result_df.head(3).to_dict()}", flush=True)'''

if old_done in content:
    content = content.replace(old_done, new_done)
    print('OK: Added debug logging')
else:
    print('SKIP: Done pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
