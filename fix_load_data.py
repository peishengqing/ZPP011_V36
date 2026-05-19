# -*- coding: utf-8 -*-
"""淇 _load_data_worker 鍔犺浇鏁版嵁闂"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇1: 鍦ㄨ鍙朎xcel鍚庢坊鍔犳棩蹇楀拰鍒楀悕娓呯悊
old_read = '''        # 3. 璇诲彇
        dev_df = pd.read_excel(latest_file, sheet_name='瀹屾暣鍋忓樊鏄庣粏')
        if dev_df.empty:
            raise ValueError("鍋忓樊鏄庣粏宸ヤ綔琛ㄤ负绌?)'''

new_read = '''        # 3. 璇诲彇
        dev_df = pd.read_excel(latest_file, sheet_name='瀹屾暣鍋忓樊鏄庣粏')
        if dev_df.empty:
            raise ValueError("鍋忓樊鏄庣粏宸ヤ綔琛ㄤ负绌?)
        
        # 娓呯悊鍒楀悕锛堝幓闄ょ┖鏍硷級
        dev_df.columns = [str(col).strip().replace(' ', '') for col in dev_df.columns]
        _dprint(f"[DEBUG] 鍔犺浇鏁版嵁鍒楀悕: {list(dev_df.columns)}", flush=True)'''

if old_read in content:
    content = content.replace(old_read, new_read)
    print('OK: Added column name cleaning')
else:
    print('SKIP: Read pattern not found')

# 淇2: 鍦?_on_load_done 涓坊鍔犵┖鏁版嵁妫€鏌?old_done = '''    def _on_load_done(self, result_df):
        """寮傛鍔犺浇鎴愬姛鍥炶皟锛氬鐞嗘墍鏈塙I鏇存柊"""
        try:
            self.audit_data = result_df'''

new_done = '''    def _on_load_done(self, result_df):
        """寮傛鍔犺浇鎴愬姛鍥炶皟锛氬鐞嗘墍鏈塙I鏇存柊"""
        try:
            # 妫€鏌ユ暟鎹槸鍚︿负绌?            if result_df is None or result_df.empty:
                self.log("[WARN] 鍔犺浇鐨勬暟鎹负绌?, "warn")
                messagebox.showwarning("鎻愮ず", "鍔犺浇鐨勬暟鎹负绌猴紝璇锋鏌ュ垎鏋愮粨鏋滄枃浠?)
                return
            
            self.audit_data = result_df
            _dprint(f"[DEBUG _on_load_done] 鍔犺浇 {len(result_df)} 琛屾暟鎹?, flush=True)'''

if old_done in content:
    content = content.replace(old_done, new_done)
    print('OK: Added empty data check')
else:
    print('SKIP: Done pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
