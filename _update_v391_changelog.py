#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新 changelog.json 中的 v39.1 条目（按任务卡模板）
"""
import json
import sys
import os

def update_v391_changelog():
    # 读取 changelog.json
    changelog_path = "changelog.json"
    
    if not os.path.exists(changelog_path):
        print(f"[ERROR] 文件不存在: {changelog_path}")
        sys.exit(1)
    
    try:
        with open(changelog_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] 读取 JSON 失败: {e}")
        sys.exit(1)
    
    # 查找 v39.1 条目
    versions = data.get("versions", [])
    v391_index = None
    for i, version in enumerate(versions):
        if version.get("version") == "v39.1":
            v391_index = i
            break
    
    # 构造新的 v39.1 条目（按任务卡模板）
    new_v391 = {
        "version": "v39.1",
        "release_date": "2026-05-23",
        "build_datetime": "2026-05-23 15:30:00",  # 预估时间，打包后需更新为实际时间
        "features": [],
        "fixes": [
            "🐛 修复项目中使用 from utils import * 的技术债务（确认已清零）"
        ],
        "optimizations": [],
        "notes": [
            "📌 基于 Qclaw 执行任务卡 v4.1 完成债务扫描",
            "📌 核心功能验证通过"
        ]
    }
    
    # 更新或添加 v39.1 条目
    if v391_index is not None:
        # 替换现有条目
        versions[v391_index] = new_v391
        print(f"[OK] 已更新 v39.1 条目（索引 {v391_index}）")
    else:
        # 添加到末尾
        versions.append(new_v391)
        print("[OK] 已添加 v39.1 条目到末尾")
    
    data["versions"] = versions
    
    # 写回文件
    try:
        with open(changelog_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] 已更新 {changelog_path}")
    except Exception as e:
        print(f"[ERROR] 写入 JSON 失败: {e}")
        sys.exit(1)
    
    # 验证
    try:
        with open(changelog_path, 'r', encoding='utf-8') as f:
            json.load(f)
        print("[OK] JSON 格式验证通过")
    except Exception as e:
        print(f"[ERROR] JSON 格式验证失败: {e}")
        sys.exit(1)
    
    print("\n[SUCCESS] v39.1 条目更新完成（按任务卡模板）")
    print("[注意] build_datetime 为预估时间，打包完成后请手动更新为实际时间")

if __name__ == "__main__":
    update_v391_changelog()
