#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新 changelog.json 中的 v39.1 build_datetime 为实际打包时间
"""
import json
import sys
import os

def update_build_datetime():
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
    
    if v391_index is None:
        print("[ERROR] 未找到 v39.1 条目")
        sys.exit(1)
    
    # 更新 build_datetime 为实际打包时间
    actual_build_time = "2026-05-23 03:46:30"  # 从输出文件时间戳推断
    versions[v391_index]["build_datetime"] = actual_build_time
    print(f"[OK] 已更新 v39.1 build_datetime: {actual_build_time}")
    
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
    
    print("\n[SUCCESS] build_datetime 更新完成")
    print("[注意] 需要重新打包，使 changelog.json 更改生效")

if __name__ == "__main__":
    update_build_datetime()
