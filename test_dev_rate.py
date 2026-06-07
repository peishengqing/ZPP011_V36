import pandas as pd

path = r'C:\Users\Administrator\AppData\Local\Temp\zpp011_analysis\ZPP011偏差分析最终版_20260501-20260531_v02.xlsx'
df = pd.read_excel(path, sheet_name='完整偏差明细')

print('=== 列名 ===')
for c in df.columns:
    print(repr(c))

print('\n=== 偏差率列前5行 ===')
if '偏差率' in df.columns:
    col = df['偏差率']
    print('原始值:', col.head(5).tolist())
    # 尝试转换
    converted = pd.to_numeric(col.astype(str).str.replace('%', '', regex=False), errors='coerce')
    print('转换后:', converted.head(5).tolist())
else:
    print('未找到 偏差率 列')
    # 找相似列名
    for c in df.columns:
        if '偏差' in str(c):
            print(f'  找到相似列: {repr(c)}')
