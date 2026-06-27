import sys

# 用二进制模式
with open('gui_pyside6/main_window.py', 'rb') as f:
    data = f.read()

print('文件大小:', len(data))

# 找方法起始和结束的字节位置
start_marker = b'    def _update_summary(self):\n'
end_marker = b'    def _update_stat_cards'

start_idx = data.find(start_marker)
end_idx = data.find(end_marker, start_idx)

print('start_idx:', start_idx)
print('end_idx:', end_idx)

if start_idx < 0 or end_idx < 0:
    print('ERROR: 找不到方法边界')
    sys.exit(1)

# 新方法（二进制）
new_method = b'''    def _update_summary(self):
        if self.view_model.df is None or self.view_model.df.empty:
            self.summary_quota.setText("\xe5\xae\x9a\xe9\xa2\x9d: 0.00")
            self.summary_actual.setText("\xe5\xae\x9e\xe9\x99\x85: 0.00")
            self.summary_amount.setText("\xe5\x81\x8f\xe5\xb7\xae\xe9\x87\x91\xe9\xa2\x9d: 0.00")
            self.summary_qty.setText("\xe5\x81\x8f\xe5\xb7\xae\xe6\x95\xb0\xe9\x87\x8f: 0.00")
            return
        df = self.view_model.df
        quota_col = next((c for c in ["\xe5\xae\x9a\xe9\xa2\x9d", "\xe6\x95\xb0\xe9\x87\x8f-\xe5\xae\x9a\xe9\xa2\x9d", "quota"] if c in df.columns), None)
        actual_col = next((c for c in ["\xe5\xae\x9e\xe9\x99\x85", "\xe6\x95\xb0\xe9\x87\x8f-\xe5\xae\x9e\xe9\x99\x85", "actual"] if c in df.columns), None)
        amount_col = next((c for c in ["\xe5\x87\x80\xe5\x81\x8f\xe5\xb7\xae\xe9\x87\x91\xe9\xa2\x9d", "\xe5\x87\x80\xe5\x81\x8f\xe5\xb7\xae", "\xe5\x81\x8f\xe5\xb7\xae\xe9\x87\x91\xe9\x87\x91\xe7\xa8\x8e)", "\xe5\x81\x8f\xe5\xb7\xae\xe9\x87\x91\xe9\xa2\x9d", "deviation_amount"] if c in df.columns), None)
        qty_col = next((c for c in ["\xe5\x81\x8f\xe5\xb7\xae\xe6\x95\xb0\xe9\x87\x8f", "\xe6\x95\xb0\xe9\x87\x8f\xe5\x81\x8f\xe5\xb7\xae", "dev_qty"] if c in df.columns), None)
        quota_sum = df[quota_col].fillna(0).sum() if quota_col else 0
        actual_sum = df[actual_col].fillna(0).sum() if actual_col else 0
        amount_sum = df[amount_col].fillna(0).sum() if amount_col else 0
        qty_sum = df[qty_col].fillna(0).sum() if qty_col else (df[actual_col] - df[quota_col]).fillna(0).sum() if actual_col and quota_col else 0
        self.summary_quota.setText(f"\xe5\xae\x9a\xe9\xa2\x9d: {quota_sum:,.2f}")
        self.summary_actual.setText(f"\xe5\xae\x9e\xe9\x99\x85: {actual_sum:,.2f}")
        self.summary_amount.setText(f"\xe5\x81\x8f\xe5\xb7\xae\xe9\x87\x91\xe9\xa2\x9d: {amount_sum:,.2f}")
        self.summary_qty.setText(f"\xe5\x81\x8f\xe5\xb7\xae\xe6\x95\xb0\xe9\x87\x8f: {qty_sum:,.2f}")
'''

print('原方法长度:', end_idx - start_idx)
print('新方法长度:', len(new_method))

# 替换
new_data = data[:start_idx] + new_method + data[end_idx:]

with open('gui_pyside6/main_window.py', 'wb') as f:
    f.write(new_data)

print('OK: _update_summary 已还原')
