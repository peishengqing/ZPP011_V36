import sys

# 读入文件
with open('gui_pyside6/main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找 _update_summary 的起止行（0-indexed）
start = -1
end = -1
for i, line in enumerate(lines):
    if line.rstrip() == '    def _update_summary(self):':
        start = i
        break

if start < 0:
    print('ERROR: 找不到方法')
    sys.exit(1)

for i in range(start + 1, len(lines)):
    if lines[i].startswith('    def ') and i > start:
        end = i
        break
if end < 0:
    end = len(lines)

print(f'找到方法: 行{start+1} ~ 行{end}')

# 新方法体（单行合计栏）
new_body = []
new_body.append('        if self.view_model.df is None or self.view_model.df.empty:\n')
new_body.append('            self.summary_quota.setText("定额: 0.00")\n')
new_body.append('            self.summary_actual.setText("实际: 0.00")\n')
new_body.append('            self.summary_amount.setText("偏差金额: 0.00")\n')
new_body.append('            self.summary_qty.setText("偏差数量: 0.00")\n')
new_body.append('            return\n')
new_body.append('        df = self.view_model.df\n')
new_body.append('        quota_col = next((c for c in ["定额", "数量-定额", "quota"] if c in df.columns), None)\n')
new_body.append('        actual_col = next((c for c in ["实际", "数量-实际", "actual"] if c in df.columns), None)\n')
new_body.append('        amount_col = next((c for c in ["净偏差金额", "净偏差", "偏差金额(含税)", "偏差金额", "deviation_amount"] if c in df.columns), None)\n')
new_body.append('        qty_col = next((c for c in ["偏差数量", "数量偏差", "dev_qty"] if c in df.columns), None)\n')
new_body.append('        quota_sum = df[quota_col].fillna(0).sum() if quota_col else 0\n')
new_body.append('        actual_sum = df[actual_col].fillna(0).sum() if actual_col else 0\n')
new_body.append('        amount_sum = df[amount_col].fillna(0).sum() if amount_col else 0\n')
new_body.append('        qty_sum = df[qty_col].fillna(0).sum() if qty_col else (df[actual_col] - df[quota_col]).fillna(0).sum() if actual_col and quota_col else 0\n')
new_body.append('        self.summary_quota.setText(f"定额: {quota_sum:,.2f}")\n')
new_body.append('        self.summary_actual.setText(f"实际: {actual_sum:,.2f}")\n')
new_body.append('        self.summary_amount.setText(f"偏差金额: {amount_sum:,.2f}")\n')
new_body.append('        self.summary_qty.setText(f"偏差数量: {qty_sum:,.2f}")\n')

print(f'替换: 原{end - start - 1}行 -> 新{len(new_body)}行')

# 执行替换
lines[start+1:end] = new_body

# 写回
with open('gui_pyside6/main_window.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('OK: _update_summary 已还原为单行合计栏')
