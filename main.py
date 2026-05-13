#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 偏差分析器（v36 模块化入口）
"""

import os, sys, traceback

def main():
    _dbg = os.path.join(os.path.expanduser('~'), 'Desktop', 'main_entered.txt')
    try:
        with open(_dbg, 'w', encoding='utf-8') as f:
            f.write('main() called\n')
        from gui.app import run_app
        with open(_dbg, 'a', encoding='utf-8') as f:
            f.write('run_app imported\n')
        run_app()
    except Exception as e:
        with open(_dbg, 'a', encoding='utf-8') as f:
            f.write(f'CRASH: {type(e).__name__}: {e}\n{traceback.format_exc()}')


if __name__ == "__main__":
    main()
