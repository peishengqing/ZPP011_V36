#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复 changelog.json 语法错误 + 添加 v39.1 条目（无 emoji 版本）"""

import json
import re
import sys
from datetime import datetime

file_path = r'E:\zpp011_dev\模块化脚本\changelog.json'

# 1. 读取文件为文本
print("[INFO] 读取 changelog.json...")
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 2. 修复语法错误：在 } 后面跟 { 的地方添加逗号
# 具体问题：第 513 行 `    }` 后面缺少逗号，第 514 行是 `    {`
print("[INFO] 修复语法错误（缺少逗号）...")

# 方法：找到最后一个 `}\n    {\n` 并替换为 `},\n    {\n`
# 更精确的方法：在 versions 数组内，找到对象结束 `}` 后面紧跟新对象 `{` 的地方
# 使用正则：转义括号，匹配换行和空格
pattern = r'(\})\s*\n\s*(\{)'
replacement = r'},\n    {'
fixed_content = re.sub(pattern, replacement, content)

# 3. 解析修复后的 JSON
print("[INFO] 验证 JSON 格式...")
try:
    data = json.loads(fixed_content)
    print("[OK] JSON 语法错误修复成功")
except json.JSONDecodeError as e:
    print(f"[ERROR] JSON 语法错误修复失败: {e}")
    print(f"  错误位置: 第 {e.lineno} 行，第 {e.colno} 列")
    sys.exit(1)

# 4. 添加 v39.1 条目到 versions 数组末尾
print("[INFO] 添加 v39.1 条目到 versions 数组末尾...")
new_entry = {
    "version": "v39.1",
    "release_date": "2026-05-23",
    "build_datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "features": [],
    "fixes": [
        "修复 AuditPresenter.load_audit_data 缺失（自动加载审核数据 AttributeError）",
        "修复规则文件缺失告警，自动创建默认 config/system/rules.json"
    ],
    "optimizations": [],
    "notes": [
        "v39.1 为稳定预览版修复版本，核心功能已验证"
    ]
}

# 追加到末尾
data['versions'].append(new_entry)

# 5. 写回文件
print("[INFO] 写回 changelog.json...")
with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("[OK] v39.1 条目已添加到 changelog.json")
print(f"[INFO] 版本数量: {len(data['versions'])}")
print(f"[INFO] build_datetime: {new_entry['build_datetime']}")

# 6. 最终验证：重新读取并解析
print("[INFO] 最终验证...")
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        validated_data = json.load(f)
    print("[OK] 最终验证通过")
    print(f"[INFO] 第一个版本: {validated_data['versions'][0]['version']}")
    print(f"[INFO] 最后一个版本: {validated_data['versions'][-1]['version']}")
except Exception as e:
    print(f"[ERROR] 最终验证失败: {e}")
    sys.exit(1)

print("\n=== 全部完成 ===")
