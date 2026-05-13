import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\inventory_loader.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_func = '''def calc_expiry_warning(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算剩余有效天数，并添加'过期状态'列。
    返回的DataFrame会增加两列：
    - 剩余天数：距离保质期的天数（过期时为负数）
    - 过期状态：'已过期' / '即将过期(30天内)' / '正常'
    """
    today = datetime.now().date()
    # 去掉时间部分，仅保留日期
    df["保质期_date"] = pd.to_datetime(df["保质期"]).dt.date
    df["剩余天数"] = (df["保质期_date"] - today).apply(lambda x: x.days)

    def label(days):
        if days <= 0:
            return "已过期"
        elif days <= 30:
            return "即将过期(30天内)"
        else:
            return "正常"

    df["过期状态"] = df["剩余天数"].apply(label)
    # 删除辅助列
    df = df.drop(columns=["保质期_date"])
    return df'''

new_func = '''def calc_expiry_warning(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算剩余有效天数，并添加'过期状态'列。
    返回的DataFrame会增加两列：
    - 剩余天数：距离保质期的天数（过期时为负数）
    - 过期状态：'已过期' / '即将过期(30天内)' / '正常'

    如果表格已有"过期提醒"列（数值=剩余天数），直接使用；
    否则根据"保质期"列自动计算。
    """
    # 检查是否已有现成的过期提醒列
    expiry_col = None
    for col in df.columns:
        if col.strip() in ("过期提醒", "剩余天数", "过期预警", "有效期提醒"):
            expiry_col = col.strip()
            break

    if expiry_col is not None and expiry_col in df.columns:
        # 直接使用表格中的天数数据
        df["剩余天数"] = pd.to_numeric(df[expiry_col], errors="coerce")
    else:
        # 根据保质期计算
        today = datetime.now().date()
        df["保质期_date"] = pd.to_datetime(df["保质期"]).dt.date
        df["剩余天数"] = (df["保质期_date"] - today).apply(lambda x: x.days)
        df = df.drop(columns=["保质期_date"])

    def label(days):
        if pd.isna(days):
            return "未知"
        days_val = float(days)
        if days_val <= 0:
            return "已过期"
        elif days_val <= 30:
            return "即将过期(30天内)"
        else:
            return "正常"

    df["过期状态"] = df["剩余天数"].apply(label)
    return df'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("FIXED: calc_expiry_warning now handles existing '过期提醒' column")
else:
    print("Pattern not found!")
    idx = content.find('def calc_expiry_warning')
    print(f"Context: {content[idx:idx+100]}")