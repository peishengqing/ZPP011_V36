# -*- coding: utf-8 -*-
"""ZPP011-EXEC-v37.2-002 PPT鍋囨垚鍔熶慨澶?""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇 worker 鍑芥暟
old_worker = '''        def worker():
            try:
                import ppt_generator
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log)
                self.root.after(0, lambda: self._on_ppt_done(output_path))
            except ImportError as e:
                self.root.after(0, lambda e=e: self._on_ppt_error(f"缂哄皯渚濊禆 python-pptx锛歿e}"))
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                self.root.after(0, lambda e=e, err=err: self._on_ppt_error(f"鐢熸垚澶辫触锛歿e}\\n{err}"))'''

new_worker = '''        def worker():
            try:
                import ppt_generator
                # 纭繚杈撳嚭鐩綍瀛樺湪
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                self.log(f"[PPT] 寮€濮嬬敓鎴愶紝杈撳嚭璺緞: {output_path}", "info")
                # 璋冪敤鐢熸垚鍑芥暟
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log)
                # 楠岃瘉鏂囦欢鏄惁鐪熺殑鐢熸垚
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    self.log(f"[PPT] 鏂囦欢宸茬敓鎴愶紝澶у皬: {file_size} 瀛楄妭", "info")
                    self.root.after(0, lambda: self._on_ppt_done(output_path))
                else:
                    raise RuntimeError(f"PPT 鏂囦欢鏈敓鎴愶細{output_path}")
            except ImportError as e:
                self.root.after(0, lambda e=e: self._on_ppt_error(f"缂哄皯 python-pptx 搴擄細{e}"))
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                self.log(f"[PPT] 鐢熸垚澶辫触璇︽儏: {err}", "error")
                self.root.after(0, lambda e=e: self._on_ppt_error(f"鐢熸垚澶辫触锛歿e}"))'''

if old_worker in content:
    content = content.replace(old_worker, new_worker)
    print('1. OK: Enhanced PPT worker with file validation')
else:
    print('1. SKIP: worker pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

# 淇 ppt_generator.py
fp2 = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝ppt_generator.py'
with open(fp2, 'r', encoding='utf-8') as f:
    c2 = f.read()

# 鍦?prs.save 鍚庢坊鍔犻獙璇?old_save = '''    prs.save(output_path)
    _log(f"[PPT] 璇︾粏姹囨姤 PPT 宸蹭繚瀛? {output_path} (鍏眥len(prs.slides)}椤?")'''

new_save = '''    prs.save(output_path)
    # 楠岃瘉鏂囦欢鏄惁鐪熺殑淇濆瓨鎴愬姛
    if not os.path.exists(output_path):
        raise RuntimeError(f"PPT 淇濆瓨澶辫触锛屾枃浠朵笉瀛樺湪锛歿output_path}")
    file_size = os.path.getsize(output_path)
    _log(f"[PPT] 璇︾粏姹囨姤 PPT 宸蹭繚瀛? {output_path} (鍏眥len(prs.slides)}椤? {file_size}瀛楄妭)")'''

if old_save in c2:
    c2 = c2.replace(old_save, new_save)
    print('2. OK: Added file validation in ppt_generator')
else:
    print('2. SKIP: save pattern not found')

with open(fp2, 'w', encoding='utf-8') as f:
    f.write(c2)

print('Done!')
