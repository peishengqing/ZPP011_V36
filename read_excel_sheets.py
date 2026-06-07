import pandas as pd, json, os

file = r'E:\zpp011_dev\模块化脚本\ZPP01120260501-20260531.xlsx'
xl = pd.ExcelFile(file)
result = []
for name in xl.sheet_names:
    try:
        df = pd.read_excel(file, sheet_name=name)
        cols = list(df.columns)[:12]
        result.append({
            'sheet': name,
            'rows': int(len(df)),
            'cols': int(len(df.columns)),
            'sample_cols': cols
        })
    except: pass

with open(r'E:\zpp011_dev\模块化脚本\sheet_info.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('done', len(result))
