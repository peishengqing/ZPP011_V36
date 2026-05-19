# -*- coding: utf-8 -*-
"""淇 analyzer.py 娣诲姞 _get_column 鍑芥暟"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'

with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 妫€鏌ユ槸鍚﹀凡瀛樺湪
if 'def _get_column(' in content:
    print('宸插瓨鍦紝璺宠繃')
else:
    # 鍦?_dprint 鍑芥暟涔嬪墠娣诲姞
    old = '''def _dprint(*args, **kwargs):
    """Safe debug print'''
    
    new = '''# ========== 鍔ㄦ€佸垪鍚嶆煡鎵?==========
ORDER_COL_CANDIDATES = ['娴佺▼璁㈠崟', '璁㈠崟鍙?, '璁㈠崟缂栧彿', 'Order No', '鐢熶骇璁㈠崟']

def _get_column(df, candidates, default=None):
    """浠?DataFrame 涓煡鎵剧涓€涓瓨鍦ㄧ殑鍒楀悕"""
    for col in candidates:
        if col in df.columns:
            return col
    return default


def _dprint(*args, **kwargs):
    """Safe debug print'''
    
    if old in content:
        content = content.replace(old, new)
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        print('淇瀹屾垚')
    else:
        print('鏈壘鍒版彃鍏ヤ綅缃?)
