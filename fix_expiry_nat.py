import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\inventory_loader.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the else branch to handle NaT values
old_else = '''    else:
        # 根据保质期计算
        today = datetime.now().date()
        df["保质期_date"] = pd.to_datetime(df["保质期"]).dt.date
        df["剩余天数"] = (df["保质期_date"] - today).apply(lambda x: x.days)
        df = df.drop(columns=["保质期_date"])'''

new_else = '''    else:
        # 根据保质期计算
        today = datetime.now().date()
        df["保质期_date"] = pd.to_datetime(df["保质期"]).dt.date
        # Handle NaT: convert to timedelta, extract days safely
        _td = (df["保质期_date"] - today).dt.days
        df["剩余天数"] = _td.where(_td.notna(), None)
        df = df.drop(columns=["保质期_date"])'''

if old_else in content:
    content = content.replace(old_else, new_else)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("FIXED: NaT handling in expiry calculation")
else:
    print("Pattern not found for else branch")