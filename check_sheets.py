import pandas as pd

file = 'E:/zpp011_dev/ZPP011导出文件原数据/ZPP01120260501-20260531.xlsx'
xl = pd.ExcelFile(file)
print('Sheet列表（共%d个）:' % len(xl.sheet_names))
for i, name in enumerate(xl.sheet_names):
    try:
        df = pd.read_excel(file, sheet_name=name, nrows=2)
        print('  [%d] %s  （行数>=%d, 列数:%d）' % (i, name, len(df), len(df.columns)))
    except Exception as e:
        print('  [%d] %s  （读取失败: %s）' % (i, name, e))
