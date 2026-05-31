#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新 changelog.json 添加 v40.1 版本条目
"""
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\模块化脚本'
changelog_path = os.path.join(root, 'changelog.json')

print('=' * 60)
print('更新 changelog.json - v40.1')
print('=' * 60)

# 读取 changelog.json
with open(changelog_path, 'r', encoding='utf-8') as f:
    changelog = json.load(f)

versions = changelog.get('versions', [])
print(f'\n当前版本数：{len(versions)}')

# 检查 v40.1 是否已存在
v401_idx = None
for i, v in enumerate(versions):
    if v.get('version') == 'v40.1':
        v401_idx = i
        print(f'⚠ v40.1 已存在 (索引 {i})，将更新')
        break

# 构建 v40.1 条目
build_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
v401_entry = {
    'version': 'v40.1',
    'release_date': '2026-05-30',
    'build_datetime': build_time,
    'features': [
        '✨ 管理看板增强：图表导出为 PNG（白底、高 DPI），支持同比/环比（上月/去年同期）',
        '✨ 智能小结：基于统计生成自然语言报告，一键复制，含免责声明',
        '✨ 批量操作增强：多历史记录导出为多 Sheet Excel；批量导入备注（预演模式 + 自动备份）',
        '✨ 合计行：表格底部动态显示定额、实际、偏差金额合计（随筛选更新）'
    ],
    'fixes': [],
    'optimizations': [],
    'notes': [
        '📌 导出 PNG 需安装 Pillow，已加入 requirements.txt',
        '📌 同比/环比查询依赖历史数据库，需至少一次历史记录',
        '📌 看板下钻功能暂未包含，计划 v40.2 重新设计'
    ]
}

if v401_idx is not None:
    # 更新现有条目
    versions[v401_idx] = v401_entry
    print(f'✓ 更新 v40.1 条目')
else:
    # 添加到最前面（v40.0 之后）
    # 找到 v40.0 的位置
    v400_idx = None
    for i, v in enumerate(versions):
        if v.get('version') == 'v40.0':
            v400_idx = i
            break
    
    if v400_idx is not None:
        # 插入到 v40.0 之后
        versions.insert(v400_idx + 1, v401_entry)
        print(f'✓ 添加 v40.1 到 v40.0 之后 (索引 {v400_idx + 1})')
    else:
        # 添加到最前面
        versions.insert(0, v401_entry)
        print(f'✓ 添加 v40.1 到最前面')

changelog['versions'] = versions

# 写回文件
with open(changelog_path, 'w', encoding='utf-8') as f:
    json.dump(changelog, f, ensure_ascii=False, indent=2)

print(f'✓ changelog.json 已更新')
print(f'  build_datetime: {build_time}')
print(f'  当前版本总数：{len(versions)}')

# 验证 JSON 有效性
print('\n验证 JSON 格式...')
try:
    with open(changelog_path, 'r', encoding='utf-8') as f:
        json.load(f)
    print('✓ JSON 格式有效')
except json.JSONDecodeError as e:
    print(f'✗ JSON 格式错误：{e}')

# 显示最新版本
print('\n最新版本条目:')
print(f'  {versions[0]["version"]} - {versions[0]["release_date"]}')
if len(versions) > 1:
    print(f'  {versions[1]["version"]} - {versions[1]["release_date"]}')
