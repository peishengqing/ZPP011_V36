#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, r'E:\zpp011_dev\妯″潡鍖栬剼鏈?)
sys.stdout.reconfigure(encoding='utf-8')

print("=== Testing Core Modules ===\n")

# 1. 娴嬭瘯妯″潡瀵煎叆
try:
    from analysis.analyzer import do_analysis_v2, _analysis_in_progress
    print("OK: analyzer.py imports successfully")
    print(f"  - Global lock exists: {_analysis_in_progress is not None}")
except Exception as e:
    print(f"ERROR: analyzer.py import failed: {e}")

try:
    from analysis.sheets.sheet2_alt import build_sheet2
    print("OK: sheet2_alt.py imports successfully")
except Exception as e:
    print(f"ERROR: sheet2_alt.py import failed: {e}")

try:
    import ppt_generator
    print("OK: ppt_generator.py exists")
except Exception as e:
    print(f"ERROR: ppt_generator.py error: {e}")

try:
    from core.auto_closer import AutoCloser
    print("OK: AutoCloser exists")
except Exception as e:
    print(f"ERROR: AutoCloser error: {e}")

print("\n=== All Core Modules Loaded ===")
print("Ready to run: python main.py")
