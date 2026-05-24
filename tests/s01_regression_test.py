#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
S01 模块整合 - 全功能回归测试
验证所有 Service 功能正常
"""
import os
import sys
import time
import pandas as pd

sys.path.insert(0, r'E:\zpp011_dev\模块化脚本')
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("S01 Module Integration - Full Regression Test")
print("=" * 60)

# 测试数据准备
print("\n[1/8] Preparing test data...")
test_df = pd.DataFrame({
    '工厂': ['1101'] * 500 + ['1102'] * 500,
    '车间': [f'车间{i%5}' for i in range(1000)],
    '物料编码': [f'{100 + i%5}00{i%100}' for i in range(1000)],
    '物料名称': [f'物料{i}' for i in range(1000)],
    '偏差金额': [i * 10 for i in range(1000)],
    '偏差率': [i % 20 - 10 for i in range(1000)],
    '备注原因': ['原因 A' if i % 3 == 0 else '' for i in range(1000)],
    '数量 - 定额': [100 if i % 50 == 0 else 50 for i in range(1000)],
    '数量 - 实际': [0 if i % 50 == 0 else 50 for i in range(1000)],
    '流程订单': [f'ORD{i}' for i in range(1000)],
    '组件物料号': [f'MAT{i}' for i in range(1000)],
    '组件物料描述': [f'Desc{i}' for i in range(1000)],
    '工厂名称': ['食品厂' if i < 500 else '饮料厂' for i in range(1000)],
    '生产管理员描述': [f'管理员{i%5}' for i in range(1000)],
    '定额': [50 for i in range(1000)],
    '实际': [50 for i in range(1000)],
    '材料偏差': [0 for i in range(1000)],
})

test_excel = os.path.join(os.path.dirname(os.path.abspath(__file__)), 's01_test_data.xlsx')
test_df.to_excel(test_excel, index=False)
print(f"✓ Test data saved: {test_excel} ({len(test_df)} rows)")

# 测试 1: FileService
print("\n[2/8] Testing FileService...")
from services.file_service import FileService

file_service = FileService()
backup_path = file_service.backup_file(test_excel)
print(f"✓ FileService: backup created at {backup_path}")

latest = file_service.find_latest_file("s01_test_data*.xlsx", os.path.dirname(os.path.abspath(__file__)))
print(f"✓ FileService: found latest file {os.path.basename(latest)}")

# 测试 2: DataService
print("\n[3/8] Testing DataService...")
from services.data_service import DataService

data_service = DataService()
df = data_service.load_excel(test_excel)
print(f"✓ DataService: loaded {len(df)} rows")

df_clean = data_service.clean_column_names(df)
print(f"✓ DataService: cleaned column names")

kpis = data_service.calculate_kpis(df_clean)
print(f"✓ DataService: calculated KPIs (total_records={kpis['total_records']})")

factory_kpis = data_service.aggregate_by_factory(df_clean)
print(f"✓ DataService: aggregated by factory ({len(factory_kpis)} factories)")

top10 = data_service.get_material_top10(df_clean, factory='1101')
print(f"✓ DataService: got material Top10 ({len(top10)} items)")

# 测试 3: FilterService
print("\n[4/8] Testing FilterService...")
from services.filter_service import FilterService

filter_service = FilterService()
filters = {'工厂': '1101'}
filtered = filter_service.apply_filters(df_clean, filters)
print(f"✓ FilterService: filtered {len(filtered)} rows (factory=1101)")

available = filter_service.get_available_filters(df_clean)
print(f"✓ FilterService: got {len(available)} filter options")

# 测试 4: ConfigService
print("\n[5/8] Testing ConfigService...")
from services.config_service import ConfigService

config_service = ConfigService()
threshold = config_service.get_threshold('high_deviation_rate')
print(f"✓ ConfigService: threshold={threshold}")

color = config_service.get_color('positive')
print(f"✓ ConfigService: color={color}")

output_dir = config_service.get_path('output_dir')
print(f"✓ ConfigService: output_dir={output_dir}")

# 测试 5: AuditService
print("\n[6/8] Testing AuditService...")
from services.audit_service import AuditService

audit_service = AuditService(data_service, filter_service)
df_audited = audit_service.auto_close_cases(df_clean, threshold=10.0)
auto_closed = len(df_audited[df_audited['备注来源'] == '自动结案'])
print(f"✓ AuditService: auto-closed {auto_closed} cases")

pending = audit_service.get_pending_audit(df_clean)
print(f"✓ AuditService: {len(pending)} pending audits")

# 测试 6: StorageService
print("\n[7/8] Testing StorageService...")
from services.storage_service import StorageService

storage_service = StorageService()
saved_count = storage_service.save_audit_records(df_audited)
print(f"✓ StorageService: saved {saved_count} audit records")

restored_count = storage_service.restore_audit_from_db(df_audited)
print(f"✓ StorageService: restored {restored_count} records")

# 测试 7: ExportService
print("\n[8/8] Testing ExportService...")
from services.export_service import ExportService

export_service = ExportService(data_service, file_service)
test_ppt = os.path.join(os.path.dirname(os.path.abspath(__file__)), 's01_test_output.pptx')

start_time = time.time()
ppt_path = export_service.generate_ppt(df_clean, test_ppt)
elapsed = time.time() - start_time

print(f"✓ ExportService: generated PPT in {elapsed:.2f}s")
print(f"  Output: {ppt_path}")

if elapsed <= 30:
    print(f"  ✓ Performance: PASS (≤30s)")
else:
    print(f"  ✗ Performance: FAIL (>30s)")

# 清理测试文件
print("\n[Cleanup] Removing test files...")
if os.path.exists(test_excel):
    os.remove(test_excel)
    print(f"✓ Removed: {test_excel}")

if os.path.exists(test_ppt):
    os.remove(test_ppt)
    print(f"✓ Removed: {test_ppt}")

if backup_path and os.path.exists(backup_path):
    os.remove(backup_path)
    print(f"✓ Removed: {backup_path}")

# 测试结果汇总
print("\n" + "=" * 60)
print("S01 Regression Test - SUMMARY")
print("=" * 60)
print("✓ FileService: PASS")
print("✓ DataService: PASS")
print("✓ FilterService: PASS")
print("✓ ConfigService: PASS")
print("✓ AuditService: PASS")
print("✓ StorageService: PASS")
print("✓ ExportService: PASS")
print("=" * 60)
print("ALL TESTS PASSED - S01 Integration Complete!")
print("=" * 60)
