import sys, os

# 先打开日志，确保即使崩溃也有记录
log = open('fix_log.txt', 'w', encoding='utf-8')
log.write('脚本启动\n')

try:
    filepath = 'gui_pyside6/main_window.py'
    log.write('读取文件: %s\n' % filepath)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    log.write('读取成功，共 %d 行\n' % len(lines))
    
    # 找 _update_summary 的起止行（0-indexed）
    start = -1
    end = -1
    for i, line in enumerate(lines):
        if line.rstrip() == '    def _update_summary(self):':
            start = i
            log.write('找到方法起始: 行 %d\n' % (i+1))
            break
    
    if start < 0:
        log.write('ERROR: 找不到方法\n')
        sys.exit(1)
    
    for i in range(start + 1, len(lines)):
        if lines[i].startswith('    def ') and i > start:
            end = i
            break
    if end < 0:
        end = len(lines)
    log.write('方法结束: 行 %d (共 %d 行)\n' % (end, end-start))
    
    # 新方法体（单行合计栏）
    new_body = [
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
    
    log.write('替换 %d 行为 %d 行新方法\n' % (end - start - 1, len(new_body)))
    
    # 执行替换
    lines[start+1:end] = new_body
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    log.write('OK: _update_summary 已还原\n')
    log.write('已完成\n')

except Exception as e:
    log.write('EXCEPTION: %s\n' % str(e))
    import traceback
    log.write(traceback.format_exc() + '\n')

log.close()
print('done')
