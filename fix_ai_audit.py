# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = []

# Fix 1: 在 _run_ai_audit 循环内，将审核结论写回 audit_data
# 找到 results.append 之前，追加写回代码
old1 = "            results.append({\n                '物料': str(row.get('组件物料描述', ''))[:25],\n                '偏差率': f\"{row.get('偏差率(%)', 0):.2f}%\",\n                '备注': remark[:50],\n                '审核结果': status\n            })"
new1 = "            # 写回 audit_data（同步到表格状态和颜色）\n            self.audit_data.at[idx, '备注来源'] = note_src\n            self.audit_data.at[idx, '原备注'] = remark\n            self.audit_data.at[idx, 'AI建议'] = status\n            self.audit_data.at[idx, 'audit_result'] = status\n            self.audit_data.at[idx, '备注原因'] = status  # ← 五段式：写回状态列\n            results.append({\n                '物料': str(row.get('组件物料描述', ''))[:25],\n                '偏差率': f\"{row.get('偏差率(%)', 0):.2f}%\",\n                '备注': remark[:50],\n                '审核结果': status\n            })"
if old1 in content:
    content = content.replace(old1, new1, 1)
    changes.append("Fix1: 写回 audit_data")
else:
    changes.append("Fix1 FAILED - exact text not found")

# Fix 2: 循环结束后刷新表格和颜色
# 找到 log 输出之前，插入刷新调用
old2 = "        self.log(f\"AI审核完成：系统无定额{no_quota_count}条 | 替代料{alt_mat_count}条 | 普通{normal_ok_count}条 | 需改进{warn_count}条\", \"success\")"
new2 = "        # 刷新主审核表格和颜色\n        self._refresh_audit_tree(self.audit_data)\n        self._apply_row_colors()\n        self._update_audit_stats()\n        self.log(f\"AI审核完成：系统无定额{no_quota_count}条 | 替代料{alt_mat_count}条 | 普通{normal_ok_count}条 | 需改进{warn_count}条\", \"success\")"
if old2 in content and "self._refresh_audit_tree(self.audit_data)" not in content:
    content = content.replace(old2, new2, 1)
    changes.append("Fix2: 刷新表格")
else:
    changes.append("Fix2 FAILED or already applied")

print("Changes:", changes)
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("done")