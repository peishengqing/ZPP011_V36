# -*- coding: utf-8 -*-
"""
版本更新工具 — 修改 utils/version_history.py 中的最新版本号

用法：修改下方 NEW_VERSION 后运行此脚本
"""
import json, datetime, re, os

# ── 配置 ──
NEW_VERSION = "v36.32.0"  # ← 修改此处
RELEASE_NOTES = "版本号管理集中化"

# ── 更新 utils/version_history.py ──
project_root = os.path.dirname(os.path.abspath(__file__))
vh_path = os.path.join(project_root, 'utils', 'version_history.py')

if os.path.exists(vh_path):
    with open(vh_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 更新 VERSION_HISTORY 第一条的 version
    # 找到第一个 "version": "v..." 并替换
    content = re.sub(
        r'("version"\s*:\s*)"v[\d.]+"',
        rf'\1"{NEW_VERSION}"',
        content,
        count=1
    )
    # 更新日期
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    content = re.sub(
        r'("date"\s*:\s*)"[^"]+"',
        rf'\1"{now_str}"',
        content,
        count=1
    )

    with open(vh_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[OK] utils/version_history.py updated to {NEW_VERSION}")

# ── 同步更新 config/version.json ──
ver_path = os.path.join(project_root, 'config', 'version.json')
if os.path.exists(ver_path):
    with open(ver_path, 'r', encoding='utf-8') as f:
        ver = json.load(f)
    ver['version'] = NEW_VERSION
    ver['last_build'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ver['release_notes'] = RELEASE_NOTES
    with open(ver_path, 'w', encoding='utf-8') as f:
        json.dump(ver, f, ensure_ascii=False, indent=2)
    print(f"[OK] config/version.json updated to {NEW_VERSION}")

# ── 更新 build_log.md ──
log_path = os.path.join(project_root, 'build_log.md')
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
entry = (
    f"\n{'='*50}\n"
    f"📥 {NEW_VERSION} | {now} | 成功\n"
    f"📤 打包人：裴盛清\n"
    f"{'-'*50}\n"
    f" {RELEASE_NOTES}\n"
    f"{'='*50}\n"
)
with open(log_path, 'a', encoding='utf-8') as f:
    f.write(entry)
print(f"[OK] build_log.md updated")
