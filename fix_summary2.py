import sys

with open('gui_pyside6/main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# _update_summary 从第1038行开始（0-indexed: 1037）
# 找到方法结束位置（下一个 def 或文件结束）
start = 1037  # 0-indexed
end = None
for i in range(start + 1, len(lines)):
    # 方法定义的正则：行首有4个空格然后 def 
    if lines[i].startswith('    def ') and i > start:
        end = i
        break
if end is None:
    end = len(lines)

print(f'方法范围: 行{start+1} ~ 行{end}')
print('=== 当前内容 ===')
for i in range(start, min(end, start+70)):
    print(f'{i+1}: {lines[i]}', end='')

# 新内容
new_method = '''    def _update_summary(self):
        if self.view_model.df is None or self.view_model.df.empty:
            self.summary_quota.setText("定额: 0.00")
            self.summary_actual.setText("实际: 0.00")
            self.summary_amount.setText("偏差金额: 0.00")
            self.summary_qty.setText("偏差数量: 0.00")
            return
        df = self.view_model.df
        quota_col = next((c for c in ["定额", "数量-定额", "quota"] if c in df.columns), None)
        actual_col = next((c for c in ["实际", "数量-实际", "actual"] if c in df.columns), None)
        amount_col = next((c for c in ["净偏差金额", "净偏差", "偏差金额(含税)", "偏差金额", "deviation_amount"] if c in df.columns), None)
        qty_col = next((c for c in ["偏差数量", "数量偏差", "dev_qty"] if c in df.columns), None)
        quota_sum = df[quota_col].fillna(0).sum() if quota_col else 0
        actual_sum = df[actual_col].fillna(0).sum() if actual_col else 0
        amount_sum = df[amount_col].fillna(0).sum() if amount_col else 0
        qty_sum = df[qty_col].fillna(0).sum() if qty_col else (df[actual_col] - df[quota_col]).fillna(0).sum() if actual_col and quota_col else 0
        self.summary_quota.setText(f"定额: {quota_sum:,.2f}")
        self.summary_actual.setText(f"实际: {actual_sum:,.2f}")
        self.summary_amount.setText(f"偏差金额: {amount_sum:,.2f}")
        self.summary_qty.setText(f"偏差数量: {qty_sum:,.2f}")
'''

new_lines = new_method.split('\n')
# 确保每行后面有换行符
new_lines = [line + '\n' if not line.endswith('\n') else line for line in new_lines]

# 替换
lines[start:end] = new_lines

with open('gui_pyside6/main_window.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('\nOK: _update_summary 已还原为单行合计栏版本')
