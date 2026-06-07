import pandas as pd, os

file = 'E:/zpp011_dev/ZPP011导出文件原数据/ZPP01120260501-20260531.xlsx'
xl = pd.ExcelFile(file)
with open('sheet_info.txt', 'w', encoding='utf-8') as f:
    f.write('共%d个Sheet\n' % len(xl.sheet_names))
    for name in xl.sheet_names:
        try:
            df = pd.read_excel(file, sheet_name=name)
            f.write('[%s] 行数=%d, 列数=%d\n' % (name, len(df), len(df.columns)))
            f.write('  列名: %s\n' % list(df.columns))
        except Exception as e:
            f.write('[%s] 读取失败: %s\n' % (name, e))
print('done')
