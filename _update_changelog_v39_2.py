#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Update changelog.json with v39.2 entry"""

import json
import re

def update_changelog():
    filepath = r'E:\zpp011_dev\模块化脚本\changelog.json'
    
    print("[1/2] Reading changelog.json...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("[2/2] Inserting v39.2 entry...")
    
    # v39.2 entry to insert (before the closing ] of "versions" array)
    v39_2_entry = """
    {
      "version": "v39.2",
      "release_date": "2026-05-24",
      "features": [
        "✨ 备注校验引擎：自动检查空备注、无定额（非替代料）、偏差>10%且呆滞>90天",
        "✨ 偏差表格新增「校验提示」列，显示红/黄行背景色，辅助审核",
        "✨ 侧边栏筛选面板完整可用（8个筛选条件，实时刷新）"
      ],
      "fixes": [
        "🐛 修复筛选后备注校验颜色丢失问题",
        "🐛 修复 tag 覆盖导致奇偶行颜色丢失",
        "🐛 修复定额字段 None 判断与 actual 变量未定义",
        "🐛 修复侧边栏展开/折叠卡顿",
        "🐛 修复替代料在偏差原因汇总中被归为「其他」"
      ],
      "optimizations": [
        "⚡ 筛选引擎独立（FilterEngine），与 UI 解耦",
        "⚡ 代码仓库清理（删除临时脚本、备份文件）",
        "⚡ 特性开关支持新旧筛选栏切换"
      ],
      "notes": [
        "📌 备注校验规则依赖 S01 接口（呆滞检测需 last_outbound_date，本次 MVP 未启用）",
        "📌 侧边栏展开时仍会遮挡表格右侧，表格平移优化留待 v39.3"
      ]
    }"""
    
    # Find the position of "  ]," that closes the "versions" array
    # Pattern: newline + 2 spaces + ] + comma + newline + 2 spaces + "run_logs"
    pattern = r'\n  \],\n  "run_logs"'
    replacement = ',\n' + v39_2_entry + '\n  ],\n  "run_logs"'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == content:
        print("  [ERROR] Could not find insertion point!")
        return False
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("  [OK] v39.2 entry inserted successfully")
    return True

if __name__ == '__main__':
    print("=== Update changelog.json with v39.2 ===")
    print()
    
    if update_changelog():
        print()
        print("=== Success ===")
        print("changelog.json updated with v39.2 entry")
    else:
        print()
        print("=== Failed ===")
        print("Could not update changelog.json")
