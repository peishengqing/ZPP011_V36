# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'r', encoding='utf-8') as f:
    ev = f.read()
with open(r'E:\zpp011_dev\模块化脚本\gui\app.py', 'r', encoding='utf-8') as f:
    app = f.read()
with open(r'E:\zpp011_dev\模块化脚本\gui\ui_builder.py', 'r', encoding='utf-8') as f:
    ui = f.read()

checks = []
checks.append(("task2: app.py all methods in class", 
    all('def ' in l and len(l)-len(l.lstrip())==4 for l in app.split('\n') if l.strip().startswith('def '))))

# Check events.py indent
ev_methods = [l for l in ev.split('\n') if l.strip().startswith('def ') and not l.strip().startswith('def run_app')]
ev_indents = [len(l)-len(l.lstrip()) for l in ev_methods]
checks.append(("task2: events.py all def indent==4", all(i==4 for i in ev_indents)))
checks.append(("task2: events.py no _apply_row_colors", 
    ev.count('def _apply_row_colors') == 0))
checks.append(("task2: events.py no placeholder", '功能开发中' not in ev))
checks.append(("task2: ui_builder no _refresh_alt_view", 'def _refresh_alt_view' not in ui))

checks.append(("task3: 偏差金额(含税) mapped at line 1740", 
    "audit_df['偏差金额'] = audit_df['偏差金额(含税)']" in ev))
checks.append(("task3: audit_tree deviation_amount from 含税", 
    "f\"{row.get('偏差金额(含税)'" in ev))

checks.append(("task4: admin from 车间", 
    "str(row.get('车间', '')),  # admin" in ev))

checks.append(("task5: audit_result position corrected", 
    "str(row.get('audit_result', ''))[:30],  # audit_result" in ev))
checks.append(("task5: _refresh last cols AI建议 before audit_result", 
    "str(row.get('AI建议', '')),\n                str(row.get('audit_result', ''))," in ev))

checks.append(("extra: save_audit_btn enabled", 
    "'save_audit_btn'" in ev))

print("=== 修复验证报告 ===")
for name, result in checks:
    status = "✅" if result else "❌"
    print(f"  {status} {name}")

all_ok = all(r for _, r in checks)
print()
print("全部通过!" if all_ok else "有失败项!")