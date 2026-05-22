#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接运行 PPT 生成测试（不使用 pytest）
"""
import os
import sys
import time
sys.path.insert(0, r'E:\zpp011_dev\模块化脚本')
sys.stdout.reconfigure(encoding='utf-8')

print("=== PPT Generation Test ===\n")

# 1. 导入模块
try:
    from modules.audit.presenters.audit_presenter import AuditPresenter
    print("✓ AuditPresenter imported")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# 2. 创建测试数据
import pandas as pd

print("\nCreating test data (9889 rows)...")
test_df = pd.DataFrame({
    '工厂': ['1101'] * 5000 + ['1102'] * 4889,
    '车间': [f'车间{i%10}' for i in range(9889)],
    '物料编码': [f'{100 + i%5}00{i%100}' for i in range(9889)],
    '物料名称': [f'物料{i}' for i in range(9889)],
    '偏差金额': [i * 100 for i in range(9889)],
    '偏差率': [i % 20 - 10 for i in range(9889)],
    '备注原因': ['原因 A' if i % 3 == 0 else '' for i in range(9889)],
    '数量 - 定额': [100 if i % 50 == 0 else 50 for i in range(9889)],
    '数量 - 实际': [0 if i % 50 == 0 else 50 for i in range(9889)],
})

# 3. 保存测试 Excel
test_excel = r'E:\zpp011_dev\模块化脚本\tests\test_data.xlsx'
test_df.to_excel(test_excel, index=False)
print(f"✓ Test Excel saved: {test_excel}")

# 4. 创建 Presenter
class MockModel:
    def run_analysis(self, **kwargs):
        return "/tmp/test"

class MockView:
    def __init__(self):
        self.logs = []
    def log(self, msg, level="info"):
        self.logs.append((level, msg))

model = MockModel()
view = MockView()
presenter = AuditPresenter(model, view)
print("✓ AuditPresenter created")

# 5. 测试物料分类
print("\n=== Testing Material Classification ===")
test_cases = [
    ('100001', '原材料'),
    ('400123', '原材料'),
    ('200456', '包材'),
    ('600789', '包材'),
    ('300999', '其他'),
]

for code, expected in test_cases:
    result = presenter._classify_material_type(code)
    status = "✓" if result == expected else "✗"
    print(f"{status} {code} -> {result} (expected: {expected})")

# 6. 测试数据预处理
print("\n=== Testing Data Pre-aggregation ===")
pre_data = presenter._pre_aggregate_data(test_df)
print(f"✓ Pre-aggregation complete")
print(f"  Total records: {pre_data['total_kpis']['total_records']:,}")
print(f"  Factories: {list(pre_data['factory_kpis'].keys())}")
print(f"  Material types: {list(pre_data.get('material_type_net', pd.DataFrame()).index)}")

# 7. 测试 PPT 生成性能
print("\n=== Testing PPT Generation Performance ===")
test_ppt = r'E:\zpp011_dev\模块化脚本\tests\test_output.pptx'

progress_values = []
def progress_cb(pct):
    progress_values.append(pct)
    if len(progress_values) % 3 == 0:  # 每 3 次打印一次
        print(f"  Progress: {pct:.1f}%")

start_time = time.time()
try:
    output_path = presenter.generate_ppt(test_excel, test_ppt, progress_callback=progress_cb)
    elapsed = time.time() - start_time
    
    print(f"\n✓ PPT generated successfully")
    print(f"  Output: {output_path}")
    print(f"  Time: {elapsed:.2f} seconds")
    print(f"  Pages: {len(progress_values)}")
    
    if elapsed <= 30:
        print(f"  ✓ PASS: Performance requirement met (≤30s)")
    else:
        print(f"  ✗ FAIL: Performance requirement not met (>30s)")
    
    if os.path.exists(test_ppt):
        size_mb = os.path.getsize(test_ppt) / (1024 * 1024)
        print(f"  File size: {size_mb:.2f} MB")
    
except Exception as e:
    print(f"\n✗ PPT generation failed: {e}")
    import traceback
    traceback.print_exc()

# 8. 测试数据超限
print("\n=== Testing Data Limit (50k+) ===")
large_df = pd.DataFrame({
    '工厂': ['1101'] * 50001,
    '偏差金额': [100] * 50001,
})
large_excel = test_excel.replace('.xlsx', '_large.xlsx')
large_df.to_excel(large_excel, index=False)

try:
    presenter.generate_ppt(large_excel, test_ppt)
    print("✗ FAIL: Should have raised exception for >50k rows")
except Exception as e:
    if "5 万" in str(e) or "50000" in str(e):
        print(f"✓ PASS: Correctly rejected large dataset")
    else:
        print(f"✗ FAIL: Wrong exception: {e}")

if os.path.exists(large_excel):
    os.remove(large_excel)

# 9. 清理
print("\n=== Cleanup ===")
if os.path.exists(test_excel):
    os.remove(test_excel)
    print(f"✓ Removed: {test_excel}")

if os.path.exists(test_ppt):
    print(f"✓ Kept: {test_ppt} (for manual inspection)")

print("\n=== Test Complete ===")
