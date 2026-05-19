# -*- coding: utf-8 -*-
"""淇 ppt_generator.py 淇濆瓨楠岃瘉"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝ppt_generator.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇淇濆瓨浠ｇ爜
old_save = '''        prs.save(output_path)
        _log(f"[PPT] 璇︾粏姹囨姤 PPT 宸蹭繚瀛? {output_path} (鍏眥len(prs.slides)}椤?")
        _log_error("PPT 鐢熸垚鎴愬姛")
        return True'''

new_save = '''        prs.save(output_path)
        # 楠岃瘉鏂囦欢鏄惁鐪熺殑淇濆瓨鎴愬姛
        if not os.path.exists(output_path):
            raise RuntimeError(f"PPT 淇濆瓨澶辫触锛屾枃浠朵笉瀛樺湪锛歿output_path}")
        file_size = os.path.getsize(output_path)
        _log(f"[PPT] 璇︾粏姹囨姤 PPT 宸蹭繚瀛? {output_path} (鍏眥len(prs.slides)}椤? {file_size}瀛楄妭)")
        _log_error("PPT 鐢熸垚鎴愬姛")
        return True'''

if old_save in content:
    content = content.replace(old_save, new_save)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: Added file validation in ppt_generator.py')
else:
    print('SKIP: pattern not found')
