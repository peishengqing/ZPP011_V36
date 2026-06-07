import pandas as pd
import os

file = 'E:/zpp011_dev/ZPP011导出文件原数据/ZPP01120260501-20260531.xlsx'
out = open('column_output.txt', 'w', encoding='utf-8')

out.write(f"文件存在: {os.path.exists(file)}\n")

try:
    df = pd.read_excel(file, sheet_name=0, nrows=200)
    out.write(f"\n共 {len(df.columns)} 列:\n")
    for i, col in enumerate(df.columns):
        out.write(f"  [{i}] {repr(col)}\n")

    # 查找分类相关列
    type_cols = [col for col in df.columns if any(kw in str(col) for kw in ['类型', '分类', '类别'])]
    out.write(f"\n分类相关列: {type_cols}\n")

    if type_cols:
        for col in type_cols[:5]:
            vals = [str(v) for v in df[col].dropna().unique()[:50]]
            out.write(f"\n【{col}】唯一值（前50个）:\n")
            for v in vals:
                if '食品' in v or '饮料' in v or '辅' in v or '原' in v or '包' in v or '成' in v:
                    out.write(f"  ★ {v}\n")
                else:
                    out.write(f"    {v}\n")
    else:
        # 尝试在所有列的值里搜索 食品/饮料
        out.write("\n在所有列的值中搜索 食品/饮料...\n")
        for col in df.columns:
            for v in df[col].dropna().unique()[:20]:
                s = str(v)
                if '食品' in s or '饮料' in s:
                    out.write(f"  找到：列[{col}] 值={s}\n")
                    break
except Exception as e:
    out.write(f"错误: {e}\n")
    import traceback
    traceback.print_exc(file=out)

out.close()
print("输出已写入 column_output.txt")
