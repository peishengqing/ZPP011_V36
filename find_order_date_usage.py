#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
淇璁㈠崟寮€濮嬫棩鏈熷垪鍚嶉棶棰?"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# 鏌ユ壘鎵€鏈変娇鐢?'璁㈠崟寮€濮嬫棩鏈? 鐨勫湴鏂?print("=== Searching for '璁㈠崟寮€濮嬫棩鏈? usage ===\n")

for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath or '.git' in dirpath:
        continue
    for filename in filenames:
        if filename.endswith('.py'):
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 鏌ユ壘甯﹀紩鍙风殑鍒楀悕寮曠敤
                if "'璁㈠崟寮€濮嬫棩鏈?" in content or '"璁㈠崟寮€濮嬫棩鏈?' in content:
                    lines = [(i, l.strip()) for i, l in enumerate(content.split('\n'), 1) 
                            if "'璁㈠崟寮€濮嬫棩鏈?" in l or '"璁㈠崟寮€濮嬫棩鏈?' in l]
                    if lines:
                        print(f"FOUND in {filepath}:")
                        for i, line in lines[:5]:  # 鍙樉绀哄墠 5 琛?                            print(f"  Line {i}: {line[:80]}")
                        print()
            except Exception as e:
                pass

print("=== Check Complete ===")
print("\nRecommendation:")
print("1. Check data loading code (not analysis code)")
print("2. The error occurs BEFORE analysis, during data preview/validation")
print("3. Look for files like: data_loader.py, preview.py, validator.py")
