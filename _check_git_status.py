#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check git status and log (avoid PowerShell encoding issues)"""

import subprocess
import sys

def run_git(cmd_list):
    """Run git command, return stdout"""
    try:
        result = subprocess.run(cmd_list, capture_output=True, text=True, encoding='utf-8')
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

if __name__ == '__main__':
    print("=== Git Status Check ===")
    print()
    
    # 1. Git status
    code, stdout, stderr = run_git(['git', 'status'])
    print("[Git Status]")
    print(stdout)
    print()
    
    # 2. Git log (last 3 commits)
    code, stdout, stderr = run_git(['git', 'log', '--oneline', '-3'])
    print("[Git Log (last 3 commits)]")
    print(stdout)
    print()
    
    # 3. Check if local is ahead of remote
    code, stdout, stderr = run_git(['git', 'rev-list', '--count', 'HEAD', '^origin/dev/v39-refactor'])
    if code == 0 and stdout.strip() != '0':
        print(f"[Warning] Local is {stdout.strip()} commits ahead of remote")
        print("Push may have failed!")
    else:
        print("[OK] Local is in sync with remote (push succeeded)")
