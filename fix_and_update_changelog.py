#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复 changelog.json 中的引号问题并添加 v40.1
"""
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\模块化脚本'
changelog_path = os.path.join(root, 'changelog.json')

print('=' * 60)
print('修复 changelog.json 并添加 v40.1')
print('=' * 60)

# 读取并修复
with open(changelog_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复未转义的引号（中文引号内的内容）
content = content.replace('"已审核"', '已审核')
content = content.replace('"已备注"', '已备注')
content = content.replace('"需补备注"', '需补备注')

# 写回
with open(changelog_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('\n✓ 已修复引号问题')

# 验证 JSON
try:
    with open(changelog_path, 'r', encoding='utf-8') as f:
        changelog = json.load(f)
    print('✓ JSON 格式现在有效')
except Exception as e:
    print(f'✗ 仍有错误：{e}')
    sys.exit(1)

# 添加 v40.1
versions = changelog.get('versions', [])
print(f'\n当前版本数：{len(versions)}')

# 检查 v40.1 是否已存在
v401_exists = any(v.get('version') == 'v40.1' for v in versions)

if v401_exists:
    print('⚠ v40.1 已存在，跳过添加')
else:
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

# 显示最新版本
print('\n最新版本条目:')
for i, v in enumerate(versions[:3], 1):
    print(f'  {i}. {v["version"]} - {v["release_date"]}')
