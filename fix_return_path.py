# -*- coding: utf-8 -*-
"""淇 do_analysis_v2 纭繚杩斿洖璺緞"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝analysis\analyzer.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 鍦?return final_output_path 涔嬪墠娣诲姞鏈€缁堟鏌?old_return = '''    report_progress(11, "鐢熸垚Excel", 100)
    # 杩斿洖瀹為檯淇濆瓨鐨勮矾寰?    _dprint(f"[DEBUG do_analysis_v2] 淇濆瓨瀹屾垚锛岃繑鍥烇細{final_output_path}", flush=True)
    return final_output_path'''

new_return = '''    report_progress(11, "鐢熸垚Excel", 100)
    
    # 鏈€缁堟鏌ワ細纭繚璺緞鏈夋晥
    if final_output_path is None:
        raise RuntimeError("final_output_path is None锛屾枃浠朵繚瀛樺け璐?)
    
    if not os.path.exists(final_output_path):
        # 灏濊瘯鍐嶆淇濆瓨
        _dprint(f"[DEBUG] 鏂囦欢涓嶅瓨鍦紝灏濊瘯鍐嶆淇濆瓨锛歿final_output_path}", flush=True)
        try:
            wb.save(final_output_path)
        except Exception as e:
            raise RuntimeError(f"鏂囦欢淇濆瓨澶辫触锛歿final_output_path}锛岄敊璇細{e}")
    
    # 杩斿洖瀹為檯淇濆瓨鐨勮矾寰?    _dprint(f"[DEBUG do_analysis_v2] 淇濆瓨瀹屾垚锛岃繑鍥烇細{final_output_path}", flush=True)
    return final_output_path'''

if old_return in content:
    content = content.replace(old_return, new_return)
    print('OK: Added final path validation')
else:
    print('SKIP: Return pattern not found')

# 鍚屾椂淇 events.py 涓殑寮傚父澶勭悊锛岀‘淇濋敊璇姝ｇ‘璁板綍
fp2 = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
with open(fp2, 'r', encoding='utf-8') as f:
    content2 = f.read()

# 鍦ㄨ皟鐢?do_analysis_v2 鏃舵坊鍔犳洿璇︾粏鐨勬棩蹇?old_call = '''            self.output_path = do_analysis_v2(
                input_file=self.input_file.get(),
                output_dir=temp_dir,
                alt_pairs=self.alt_pairs,
                progress_callback=self._on_progress,
                cancel_check=lambda: self.cancel_req,
                start_date=self.start_date.get() or None,
                end_date=self.end_date.get() or None,
                material_search=self.material_search.get() or None,
            )'''

new_call = '''            _result = do_analysis_v2(
                input_file=self.input_file.get(),
                output_dir=temp_dir,
                alt_pairs=self.alt_pairs,
                progress_callback=self._on_progress,
                cancel_check=lambda: self.cancel_req,
                start_date=self.start_date.get() or None,
                end_date=self.end_date.get() or None,
                material_search=self.material_search.get() or None,
            )
            _f.write(f"do_analysis_v2 returned: {_result}\\n")
            self.output_path = _result
            if self.output_path is None:
                raise RuntimeError("do_analysis_v2 returned None")'''

if old_call in content2:
    content2 = content2.replace(old_call, new_call)
    with open(fp2, 'w', encoding='utf-8') as f:
        f.write(content2)
    print('OK: Added detailed logging in events.py')
else:
    print('SKIP: Call pattern not found in events.py')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
