#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""添加 v39.1 条目到 changelog.json"""

import json
from datetime import datetime

# 读取 changelog.json
with open(r'E:\zpp011_dev\模块化脚本\changelog.json', 'r', encoding='utf-8') as f:
    changelog = json.load(f)

# v39.1 新条目
new_entry = {
    "version": "v39.1",
    "release_date": "2026-05-23",
    "build_datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "features": [
        "【修复】AuditPresenter.load_audit_data 方法缺失（AttributeError）",
        "【修复】规则文件不存在警告（RuleEngine 自动创建默认配置）"
    ],
    "fixes": [
        "修复 load_audit_data 缺失导致程序启动报错",
        "修复规则文件缺失导致控制台警告"
    ],
    "optimizations": [
        "规则引擎增强：文件缺失时自动创建默认 rules.json"
    ],
    "notes": [
        "测试版，请裴哥手动测试验证修复效果",
        "若测试通过，可发布为正式版 v39.1"
    ]
}

# 插入到 versions 数组开头
changelog['versions'].insert(0, new_entry)

# 写回文件
with open(r'E:\zpp011_dev\模块化脚本\changelog.json', 'w', encoding='utf-8') as f:
    json.dump(changelog, f, indent=2, ensure_ascii=False)

print("[OK] v39.1 条目已添加到 changelog.json")
print(f"[INFO] 构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
