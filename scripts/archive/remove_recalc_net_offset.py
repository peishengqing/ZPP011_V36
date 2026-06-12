#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""移除 data_service.py 中的二次净偏差修正（避免重复计算）"""

fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\services\data_service.py"

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# ========== 步骤1：注释掉 preprocess_audit_data 中的调用 ==========
# 找到 preprocess_audit_data 方法
start = None
for i, line in enumerate(lines):
    if line.strip() == 'def preprocess_audit_data(self, df: pd.DataFrame, previous_df: pd.DataFrame = None) -> pd.DataFrame:':
        start = i
        break

if start is None:
    print("ERROR: preprocess_audit_data method not found!")
    exit(1)

print(f"Found preprocess_audit_data at line {start+1}")

# 找到方法结束的位置
end = None
for i in range(start + 1, len(lines)):
    if lines[i].strip().startswith('def ') or lines[i].strip().startswith('class '):
        end = i
        break

if end is None:
    end = len(lines)

print(f"preprocess_audit_data ends at line {end+1}")

# 在方法体内查找并注释掉调用 _recalc_net_offset 的代码
modified = []
for i in range(start, end):
    stripped = lines[i].strip()
    if "self.alt_controller:" in stripped and i+1 < end and "self._recalc_net_offset" in lines[i+1]:
        # 注释掉这两行
        modified.append(lines[i].rstrip() + "  # 已注释：净偏差计算已在 analyzer.py 中完成\n")
        modified.append("# " + lines[i+1])
        modified.append("\n")  # 添加空行保持格式
        print(f"Commented out lines {i+1}-{i+2}")
        # 跳过下一行（已注释）
        i += 1
    else:
        modified.append(lines[i])

# 重建 lines（只包含 preprocess_audit_data 方法）
lines[start:end] = modified

# ========== 步骤2：删除整个 _recalc_net_offset 方法 ==========
# 重新读取文件（因为 lines 已修改）
# 找到 _recalc_net_offset 方法
start2 = None
for i, line in enumerate(lines):
    if line.strip() == 'def _recalc_net_offset(self, df: pd.DataFrame) -> pd.DataFrame:':
        start2 = i
        break

if start2 is None:
    print("WARNING: _recalc_net_offset method not found (may already be deleted)")
else:
    print(f"Found _recalc_net_offset at line {start2+1}")
    
    # 找到方法结束的位置
    end2 = None
    for i in range(start2 + 1, len(lines)):
        if lines[i].strip().startswith('def ') or lines[i].strip().startswith('class '):
            end2 = i
            break
    
    if end2 is None:
        end2 = len(lines)
    
    print(f"_recalc_net_offset ends at line {end2+1}")
    print(f"Deleting lines {start2+1}-{end2+1} ({end2-start2} lines)")
    
    # 删除方法
    lines = lines[:start2] + lines[end2:]
    print(f"Deleted _recalc_net_offset method")

# 写入文件
with open(fp, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"\nDone! File saved to: {fp}")
print(f"Total lines: {len(lines)}")
