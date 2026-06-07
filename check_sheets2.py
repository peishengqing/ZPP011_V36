import pandas as pd, os, json

file = 'E:/zpp011_dev/ZPP011导出文件原数据/ZPP01120260501-20260531.xlsx'
out = open('sheet_info.txt', 'w', encoding='utf-8')

try:
    xl = pd.ExcelFile(file)
    out.write('共 %d 个 Sheet\n' % len(xl.sheet_names))
    for name in xl.sheet_names:
        try:
            df = pd.read_excel(file, sheet_name=name, nrows=3)
            row_count = len(pd.read_excel(file, sheet_name=name))
            out.write('[%s] 列数=%d, 总行数=%d\n' % (name, len(df.columns), row_count))
            out.write('  列名: %s\n' % list(df.columns))
        except Exception as e:
            out.write('[%s] 读取失败: %s\n' % (name, e))
except Exception as e:
    out.write('错误: %s\n' % e)

out.close()
print('done')
