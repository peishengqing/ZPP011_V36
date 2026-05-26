#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""推送 PPT 图表修改到远程仓库"""
import subprocess
import os

os.chdir(r'E:\zpp011_dev\模块化脚本')

# 1. 检查状态
result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
print("Git status:")
print(result.stdout if result.stdout else "  (干净)")

# 2. 添加文件
print("\n添加 ppt_generator.py...")
result = subprocess.run(['git', 'add', 'ppt_generator.py'], capture_output=True, text=True)
print(result.stdout if result.stdout else "  OK")

# 3. 提交
print("\n提交...")
commit_msg = """feat: 添加多耗/少耗环形饼图（PPT）

- 实现 _add_doughnut_chart 函数（DOUGHNUT 图表）
- 多耗红色 #E74C3C，少耗绿色 #2ECC71
- 在 run_ppt_generation 中集成环形饼图
- 空数据容错（总额均为0时跳过）
"""
with open('_commit_msg.txt', 'w', encoding='utf-8') as f:
    f.write(commit_msg)
result = subprocess.run(['git', 'commit', '-F', '_commit_msg.txt'], capture_output=True, text=True)
print(result.stdout if result.stdout else "  " + (result.stderr if result.stderr else "未知错误"))

# 4. 推送
print("\n推送到 origin/main...")
result = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True)
print(result.stdout if result.stdout else "  " + result.stderr)

# 5. 验证
print("\n验证远程状态...")
result = subprocess.run(['git', 'log', '--oneline', '-1'], capture_output=True, text=True)
print("  最新提交: " + result.stdout.strip())

print("\n完成！")
