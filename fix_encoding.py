#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
鎵归噺淇缂栫爜鎹熷潖鐨勬枃浠?"""
import os
import sys
import re

root = r'E:\zpp011_dev\妯″潡鍖栬剼鏈?

# 闇€瑕佷慨澶嶇殑鏂囦欢
files_to_fix = [
    'gui/events.py',
    'widgets.py',
]

# 甯歌涔辩爜妯″紡鏄犲皠
mojibake_map = {
    '娴?: '浜?,
    '銏?: '涓€',
    '閿?: '鏂?,
    '娴?: '浠?,
    '': '',  # 鏃犳硶璇嗗埆鐨勫瓧绗︾洿鎺ュ垹闄?    # 娣诲姞鏇村鏄犲皠...
}

for rel_path in files_to_fix:
    full_path = os.path.join(root, rel_path)
    if not os.path.exists(full_path):
        print(f'SKIP: {rel_path} not found')
        continue
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 妫€鏌ユ槸鍚︽湁涔辩爜
        has_mojibake = any(c in content for c in mojibake_map.keys())
        
        if has_mojibake:
            # 灏濊瘯绠€鍗曟浛鎹?            for old, new in mojibake_map.items():
                content = content.replace(old, new)
            
            # 淇濆瓨淇鍚庣殑鏂囦欢
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'FIXED: {rel_path}')
        else:
            print(f'OK: {rel_path}')
    except Exception as e:
        print(f'ERROR: {rel_path} - {e}')

print('\nDone. Try running python main.py again.')
