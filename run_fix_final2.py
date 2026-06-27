import sys

with open('gui_pyside6/main_window.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# _update_summary 方法体起始行（0-indexed）
# 行1038 = def _update_summary
# 行1039-1044 = 空数据检查（已正确）
# 行1045 = df = self.view_model.df
# 我们需要替换 行1045 到 行1086（方法体结束）
body_start = 1045  # df = self.view_model.df
body_end   = 1087  # 方法结束后的空行

# 新 method body（原始单行版本）
new_body = [
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

print('替换行 %d~%d，共 %d 行' % (body_start+1, body_end, body_end-body_start))
print('新内容 %d 行' % len(new_body))

lines[body_start:body_end] = new_body

with open('gui_pyside6/main_window.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('OK: _update_summary 已完全还原为单行合计栏')
