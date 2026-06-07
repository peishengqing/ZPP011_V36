import pandas as pd, json, os

file = r'E:\zpp011_dev\模块化脚本\ZPP01120260501-20260531.xlsx'
xl = pd.ExcelFile(file)
info = []
for name in xl.sheet_names:
    try:
        df = pd.read_excel(file, sheet_name=name)
        info.append({'sheet': name, 'rows': int(len(df)), 'cols': int(len(df.columns))})
    except: pass
with open(r'E:\zpp011_dev\模块化脚本\sheet_info.json', 'w', encoding='utf-8') as f:
    json.dump(info, f, ensure_ascii=False)
print('done', len(info))
