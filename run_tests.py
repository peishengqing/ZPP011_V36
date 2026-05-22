#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行 PPT 生成测试
"""
import os
import sys
sys.path.insert(0, r'E:\zpp011_dev\模块化脚本')
sys.stdout.reconfigure(encoding='utf-8')

# 运行测试
import subprocess
result = subprocess.run(
    ['python', '-m', 'pytest', 'tests/test_ppt_generation.py', '-v'],
    cwd=r'E:\zpp011_dev\模块化脚本',
    capture_output=True,
    text=True,
    encoding='utf-8'
)

print("STDOUT:")
print(result.stdout)
if result.stderr:
    print("\nSTDERR:")
    print(result.stderr)

print(f"\nReturn code: {result.returncode}")
