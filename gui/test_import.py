import sys
sys.path.append('.')
from stock_summary_standalone import parse_zmm062_excel

file_path = input("请输入 Excel 完整路径: ")
df = parse_zmm062_excel(file_path)
print(f"解析行数: {len(df)}")
if len(df) > 0:
    print("前两行:\n", df.head(2))
    print("列名:", list(df.columns))