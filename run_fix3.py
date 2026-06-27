import sys

log = open('fix_log.txt', 'w', encoding='utf-8')

with open('gui_pyside6/main_window.py', 'r', encoding='utf-8') as f:
    content = f.read()

log.write('文件读取成功，长度: %d\n' % len(content))

# 找方法起始位置
idx = content.find('    def _update_summary(self):\n')
log.write('方法起始 idx: %d\n' % idx)

if idx < 0:
    log.write('ERROR: 找不到方法\n')
    log.close()
    sys.exit(1)

# 找方法结束位置（下一个 def ）
# 从起始位置之后找下一个 '    def '
rest = content[idx+1:]
next_def = rest.find('\n    def ')
if next_def >= 0:
    end_idx = idx + 1 + next_def
else:
    end_idx = len(content)

log.write('方法结束 idx: %d (行约 %d)\n' % (end_idx, end_idx // 80))

# 原方法字符串
old = content[idx:end_idx]
log.write('原方法长度: %d\n' % len(old))
log.write('原方法前200字符: %s\n' % repr(old[:200]))

# 新方法
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

if old in content:
    content = content.replace(old, new_method, 1)
    with open('gui_pyside6/main_window.py', 'w', encoding='utf-8') as f:
        f.write(content)
    log.write('OK: _update_summary 已还原\n')
else:
    log.write('ERROR: 原方法字符串匹配失败\n')
    # 尝试找差异
    # 检查制表符
    if '\t' in old:
        log.write('警告: 原方法包含制表符\\t\n')
    # 检查换行符
    crlf = old.count('\r\n')
    lf = old.count('\n') - crlf
    log.write('换行符: CRLF=%d, LF=%d\n' % (crlf, lf))

log.close()
print('done')
