#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
content = open(path, 'r', encoding='utf-8').read()

# 鏌ユ壘鎵€鏈変娇鐢?'鍋忓樊閲戦 (鍚◣)' 鐨勫湴鏂癸紙绗?125 琛屼箣鍚庡簲璇ユ槸閿欒浣跨敤锛?lines = [(i, l.strip()) for i, l in enumerate(content.split('\n'), 1) if '鍋忓樊閲戦 (鍚◣)' in l]
print(f"Found {len(lines)} lines with '鍋忓樊閲戦 (鍚◣)':")
for i, l in lines:
    status = "OK (rename logic)" if i < 125 else "CHECK (usage after rename)"
    print(f"  Line {i}: {status}")
    print(f"    {l[:120]}")

# 楠岃瘉锛?25 琛屽悗鏄惁杩樻湁浣跨敤
bad_lines = [i for i, _ in lines if i > 125]
if bad_lines:
    print(f"\nWARNING: {len(bad_lines)} lines use '鍋忓樊閲戦 (鍚◣)' after rename logic!")
else:
    print("\nOK: All usages are correct (only in rename logic)")

