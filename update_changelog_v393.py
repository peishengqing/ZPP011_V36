#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新 changelog.json 中的 v39.3 版本日志
"""
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

changelog_path = r'E:\zpp011_dev\模块化脚本\changelog.json'

with open(changelog_path, 'r', encoding='utf-8') as f:
    changelog = json.load(f)

# 检查 v39.3 是否已存在
versions = changelog.get('versions', [])
v393_idx = None
for i, v in enumerate(versions):
    if v.get('version') == 'v39.3':
        v393_idx = i
        break

# 更新或添加 v39.3
build_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
v393_entry = {
    'version': 'v39.3',
    'release_date': '2026-05-25',
    'build_datetime': build_time,
    'features': [
        '✨ 右键复制物料编码：选中行右键菜单，复制物料编码到剪贴板（反查数据源，不依赖列顺序）',
        '✨ 预检报告弹窗改为非模态：显示系统检查与数据统计，不再阻塞主窗口操作'
    ],
    'fixes': [
        '🐛 修复表格排序崩溃（补全 _COL_TO_DF 映射及排序方法）',
        '🐛 修复侧边栏筛选全部失效（替代料列名探测 + 布尔/字符串类型清洗）',
        '🐛 修复调试 print 残留及 @with_feedback 装饰器冗余弹窗',
        '🐛 修复右键菜单覆盖原有功能（追加「复制物料编码」而非替换）'
    ],
    'optimizations': [
        '⚡ 预检报告窗口独立关闭，不干扰审核流程',
        '⚡ 代码整洁：移除调试输出与冗余装饰器'
    ],
    'notes': [
        '📌 v39.3 建议所有用户升级，提升筛选与排序稳定性'
    ]
}

if v393_idx is not None:
    # 更新现有条目
    versions[v393_idx] = v393_entry
    print(f'✓ 更新 changelog.json 中的 v39.3 条目')
else:
    # 添加到最前面
    versions.insert(0, v393_entry)
    print(f'✓ 添加 v39.3 到 changelog.json')

changelog['versions'] = versions

with open(changelog_path, 'w', encoding='utf-8') as f:
    json.dump(changelog, f, ensure_ascii=False, indent=2)

print(f'✓ changelog.json 已更新 (build_datetime={build_time})')
print(f'✓ 当前共 {len(versions)} 个版本')
