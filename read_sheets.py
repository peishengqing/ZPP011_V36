import pandas as pd, json

file = r'E:\zpp011_dev\模块化脚本\ZPP01120260501-20260531.xlsx'
xl = pd.ExcelFile(file)
info = []
for name in xl.sheet_names:
    try:
        df = pd.read_excel(file, sheet_name=name)
        cols = list(df.columns)[:15]  # 只看前15列
        sample = {}
        for c in cols[:8]:
            vals = df[c].dropna().unique()
            sample[c] = str(list(vals[:5]))[:60]
        info.append({'sheet': name, 'rows': len(df), 'cols': len(df.columns), 'sample': sample})
    except: pass

with open(r'E:\zpp011_dev\模块化脚本\sheet_info.json', 'w', encoding='utf-8') as f:
    json.dump(info, f, ensure_ascii=False, indent=2)
print('done')
