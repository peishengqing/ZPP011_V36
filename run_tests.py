#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行 PPT 生成测试
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

# 运行测试
import subprocess
result = subprocess.run(
    ['python', '-m', 'pytest', 'tests/test_ppt_generation.py', '-v'],
    cwd=os.path.dirname(os.path.abspath(__file__)),
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
