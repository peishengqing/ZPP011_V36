#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行 v39.3 打包
"""
import os
import sys
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\模块化脚本'
build_script = os.path.join(root, 'build_exe.py')

print('=' * 60)
print('v39.3 打包执行')
print('=' * 60)

print(f'\n工作目录：{root}')
print(f'打包脚本：{build_script}')

# 执行打包
print('\n开始打包...\n')
result = subprocess.run(
    ['python', build_script],
    cwd=root,
    capture_output=True,
    text=True,
    encoding='utf-8'
)

# 输出日志
print(result.stdout)
if result.stderr:
    print('STDERR:')
    print(result.stderr)

print(f'\n返回码：{result.returncode}')

if result.returncode == 0:
    print('\n✓ 打包成功！')
    
    # 查找最新生成的 exe
    dist_dir = os.path.join(root, 'dist')
    if os.path.exists(dist_dir):
        exes = [f for f in os.listdir(dist_dir) if f.endswith('.exe') and 'v39.3' in f]
        if exes:
            latest_exe = max(exes)
            print(f'\n生成文件：{latest_exe}')
            print(f'文件路径：{os.path.join(dist_dir, latest_exe)}')
            file_size = os.path.getsize(os.path.join(dist_dir, latest_exe))
            print(f'文件大小：{file_size / (1024*1024):.2f} MB')
        else:
            print('\n⚠ 未找到 v39.3 的 exe 文件')
else:
    print('\n✗ 打包失败！')
    print('请查看错误信息并修复')
