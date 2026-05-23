#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""添加 v39.1 条目到 version_history.py"""

import re
from datetime import datetime

# 读取文件
with open(r'E:\zpp011_dev\模块化脚本\utils\version_history.py', 'r', encoding='utf-8') as f:
    content = f.read()

# v39.1 新条目
new_entry = """    {
        "version": "v39.1",
        "date": "2026-05-23",
        "build_datetime": "%s",
        "features": [
            "✨ 修复 load_audit_data 缺失（AuditPresenter 可正常加载审核记录）",
            "✨ 规则文件自动创建（RuleEngine 初始化时生成默认 rules.json）"
        ],
        "fixes": [
            "🐛 修复 AuditPresenter.load_audit_data 方法缺失（AttributeError）",
            "🐛 修复规则文件不存在警告（控制台不再报错）"
        ],
        "optimizations": [
            "⚡ 规则引擎增强：文件缺失时自动创建默认配置，无需手动创建"
        ],
        "notes": [
            "📌 测试版，请裴哥手动测试验证修复效果",
            "📌 若测试通过，可发布为正式版 v39.1"
        ]
    },""" % datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 在 VERSION_HISTORY = [ 后面插入新条目
pattern = r'(VERSION_HISTORY = \[)'
replacement = r'\1\n' + new_entry
new_content = re.sub(pattern, replacement, content, count=1)

# 写回文件
with open(r'E:\zpp011_dev\模块化脚本\utils\version_history.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("[OK] v39.1 条目已添加到 version_history.py")
print(f"[INFO] 构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
