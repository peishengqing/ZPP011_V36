# -*- coding: utf-8 -*-
"""修复 ppt_generator.py 列名清理"""
import os

fp = r'E:\zpp011_dev\模块化脚本\ppt_generator.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 在 safe_read 函数中添加列名清理
old_safe = '''        def safe_read(name, default_cols=None):
            if name in sheets:
                return pd.read_excel(excel_path, sheet_name=name)
            for s in sheets:
                if name in s:
                    return pd.read_excel(excel_path, sheet_name=s)
            _log(f"  [PPT] 未找到 Sheet「{name}」，将跳过相关内容")
            return pd.DataFrame(columns=default_cols or [])'''

new_safe = '''        def safe_read(name, default_cols=None):
            if name in sheets:
                df = pd.read_excel(excel_path, sheet_name=name)
            else:
                for s in sheets:
                    if name in s:
                        df = pd.read_excel(excel_path, sheet_name=s)
                        break
                else:
                    _log(f"  [PPT] 未找到 Sheet「{name}」，将跳过相关内容")
                    return pd.DataFrame(columns=default_cols or [])
            # 清理列名（去除空格）
            df.columns = [str(col).strip().replace(' ', '') for col in df.columns]
            return df'''

if old_safe in content:
    content = content.replace(old_safe, new_safe)
    print('1. OK: Added column cleaning in safe_read')
else:
    print('1. SKIP: safe_read pattern not found')

# 同时修改 _create_bar_chart_image 使用清理后的列名
old_chart = "    df_f = df_summary[df_summary['工厂名称'] == factory_name].copy()"
new_chart = "    factory_col = _get_column(df_summary, ['工厂名称', '工厂'], '工厂名称')\n    df_f = df_summary[df_summary[factory_col] == factory_name].copy()"

if old_chart in content:
    content = content.replace(old_chart, new_chart)
    print('2. OK: Fixed factory column lookup')
else:
    print('2. SKIP: chart pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
