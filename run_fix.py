import sys

with open('gui_pyside6/main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 _update_summary 的开始和结束行（0-indexed）
start = None
end = None
for i, line in enumerate(lines):
    if '    def _update_summary(self):' in line:
        start = i
    elif start is not None and end is None:
        if line.startswith('    def ') and i > start:
            end = i
            break

if start is None:
    with open('fix_log.txt', 'w') as f:
        f.write('ERROR: 找不到 _update_summary 方法\n')
    sys.exit(1)

if end is None:
    end = len(lines)

print(f'找到方法: 行{start+1} ~ 行{end}', file=open('fix_log.txt', 'w'))

# 新方法内容（单行合计栏，定额/实际/偏差金额/偏差数量）
new_method = [
    '    def _update_summary(self):\n',
    '        if self.view_model.df is None or self.view_model.df.empty:\n',
    '            self.summary_quota.setText("定额: 0.00")\n',
    '            self.summary_actual.setText("实际: 0.00")\n',
    '            self.summary_amount.setText("偏差金额: 0.00")\n',
    '            self.summary_qty.setText("偏差数量: 0.00")\n',
    '            return\n',
    '        df = self.view_model.df\n',
    '        quota_col = next((c for c in ["定额", "数量-定额", "quota"] if c in df.columns), None)\n',
    '        actual_col = next((c for c in ["实际", "数量-实际", "actual"] if c in df.columns), None)\n',
    '        amount_col = next((c for c in ["净偏差金额", "净偏差", "偏差金额(含税)", "偏差金额", "deviation_amount"] if c in df.columns), None)\n',
    '        qty_col = next((c for c in ["偏差数量", "数量偏差", "dev_qty"] if c in df.columns), None)\n',
    '        quota_sum = df[quota_col].fillna(0).sum() if quota_col else 0\n',
    '        actual_sum = df[actual_col].fillna(0).sum() if actual_col else 0\n',
    '        amount_sum = df[amount_col].fillna(0).sum() if amount_col else 0\n',
    '        qty_sum = df[qty_col].fillna(0).sum() if qty_col else (df[actual_col] - df[quota_col]).fillna(0).sum() if actual_col and quota_col else 0\n',
    '        self.summary_quota.setText(f"定额: {quota_sum:,.2f}")\n',
    '        self.summary_actual.setText(f"实际: {actual_sum:,.2f}")\n',
    '        self.summary_amount.setText(f"偏差金额: {amount_sum:,.2f}")\n',
    '        self.summary_qty.setText(f"偏差数量: {qty_sum:,.2f}")\n',
]

# 替换
lines[start:end] = new_method

with open('gui_pyside6/main_window.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

with open('fix_log.txt', 'a') as f:
    f.write('OK: _update_summary 已还原为单行合计栏版本\n')
