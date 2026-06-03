"""
审计表格列配置（黄金模板）
新增列只需在此文件加一行，ui_builder.py 和 table_events.py 自动生效。
"""

AUDIT_COLS_CONFIG = [
    # (key,               heading,     width, anchor)
    ("idx",                "序号",        35,   "center"),
    ("excel_row",          "原表行号",     60,   "center"),
    ("factory",            "工厂名称",     70,   "w"),
    ("admin",              "车间",        70,   "w"),
    ("order_date",         "订单日期",     70,   "center"),
    ("order_type",         "订单类型",     70,   "center"),
    ("order_no",           "流程订单",    100,   "center"),
    ("material_category",  "物料大类",     90,   "center"),
    ("code",              "物料号",       70,   "center"),
    ("name",              "物料描述",    100,   "w"),
    ("unit",              "单位",        45,   "center"),
    ("quota",             "定额",        50,   "e"),
    ("actual",            "实际",        50,   "e"),
    ("dev_rate",          "偏差率%",     55,   "center"),
    ("is_alt",           "替代料",      50,   "center"),
    ("status",            "状态",        55,   "center"),
    ("remark",            "备注",        80,   "w"),
    ("remark_source",     "备注来源",     70,   "center"),
    ("batch_remark",      "批量备注",     90,   "w"),
    ("audit_result",       "审核结果",     80,   "center"),
    ("AI建议",            "AI建议",     120,   "w"),
    ("audit_status",       "审核状态",     60,   "center"),
    ("audit_source",       "审核来源",     70,   "center"),
    ("deviation_amount",   "偏差金额",     90,   "e"),
    ("remark_check_msg",   "校验提示",    150,   "w"),
]


def get_cols():
    return tuple(c[0] for c in AUDIT_COLS_CONFIG)


def get_heading_map():
    return {c[0]: c[1] for c in AUDIT_COLS_CONFIG}


def get_column_map():
    return {c[0]: (c[2], c[3]) for c in AUDIT_COLS_CONFIG}
