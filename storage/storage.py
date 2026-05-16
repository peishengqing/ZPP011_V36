#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" 审核数据库存储模块 — SQLite 持久化、备份导入导出 """
import os
import sqlite3
import zipfile
from datetime import datetime
import pandas as pd


def _get_app_dir():
    """返回应用数据目录（优先 E:\zpp011_dev\.zpp011_audit，兼容旧版 ~/.zpp011_audit）"""
    new_dir = r"E:\zpp011_dev\.zpp011_audit"
    old_dir = os.path.join(os.path.expanduser("~"), ".zpp011_audit")
    os.makedirs(new_dir, exist_ok=True)
    # 一次性迁移：旧目录存在且新目录数据库不存在时，复制过去
    old_db = os.path.join(old_dir, "audit_log.db")
    new_db = os.path.join(new_dir, "audit_log.db")
    if os.path.exists(old_db) and not os.path.exists(new_db):
        try:
            import shutil
            shutil.copy2(old_db, new_db)
        except Exception:
            pass  # 迁移失败不影响启动
    return new_dir


def get_audit_db_path():
    return os.path.join(_get_app_dir(), "audit_log.db")


def init_audit_db():
    conn = sqlite3.connect(get_audit_db_path())
    conn.execute("CREATE TABLE IF NOT EXISTS audit_log (work_date TEXT NOT NULL, order_no TEXT NOT NULL, mat_code TEXT NOT NULL, status TEXT, remark TEXT, auditor TEXT, saved_at TEXT, PRIMARY KEY (work_date, order_no, mat_code))")
    conn.commit()
    conn.close()


_DATE_COLS = ["订单日期", "订单开始日期", "工单日期", "日期"]
_ORDER_COLS = ["流程订单", "订单号", "订单编号", "订单号码", "订单No", "Order No"]
_MAT_COLS = ["组件物料号", "物料编码", "物料号", "零件号", "组件号"]
_REMARK_COLS = ["备注原因", "备注", "审核备注", "偏差备注"]
_BATCH_REMARK_COLS = ["批量备注原因", "批量备注", "备注"]


def _safe_col(df, candidates):
    """从候选列名列表中找到第一个存在于 DataFrame 的列，返回 Series 或全空 Series"""
    for c in candidates:
        if c in df.columns:
            return df[c]
    return pd.Series("", index=df.index)


def _safe_col_name(columns, candidates):
    """从候选列名列表中找到第一个存在于列名列表中的，返回列名或 None"""
    cols_set = set(columns)
    for c in candidates:
        if c in cols_set:
            return c
    return None


def save_audit_to_db(audit_data, auditor=None, log_cb=None):
    if audit_data is None or audit_data.empty:
        return
    if auditor is None:
        auditor = os.getlogin()
    date_col = _safe_col_name(audit_data.columns, _DATE_COLS) or "订单日期"
    order_col = _safe_col_name(audit_data.columns, _ORDER_COLS) or "订单号"
    mat_col = _safe_col_name(audit_data.columns, _MAT_COLS) or "组件物料号"
    remark_col = _safe_col_name(audit_data.columns, _REMARK_COLS)
    batch_remark_col = _safe_col_name(audit_data.columns, _BATCH_REMARK_COLS)
    conn = sqlite3.connect(get_audit_db_path())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _, row in audit_data.iterrows():
        work_date = str(row.get(date_col, ""))[:10]
        order_no  = str(row.get(order_col, ""))
        mat_code  = str(row.get(mat_col, ""))
        if not work_date or not order_no or not mat_code:
            continue
        remark = str(row.get(remark_col, "")).strip() if remark_col else ""
        if not remark and batch_remark_col:
            remark = str(row.get(batch_remark_col, "")).strip()
        status = "已备注" if remark else "未审核"
        conn.execute("INSERT OR REPLACE INTO audit_log (work_date, order_no, mat_code, status, remark, auditor, saved_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (work_date, order_no, mat_code, status, remark, auditor, now))
    conn.commit()
    conn.close()
    if log_cb:
        log_cb("✅ 审核记录已同步到本地数据库", "success")


def restore_audit_from_db(audit_data, log_cb=None):
    if audit_data is None or audit_data.empty:
        return
    conn = sqlite3.connect(get_audit_db_path())
    try:
        db_records = pd.read_sql_query("SELECT * FROM audit_log", conn)
    finally:
        conn.close()
    if db_records.empty:
        return
    date_col = _safe_col_name(audit_data.columns, _DATE_COLS) or "订单日期"
    order_col = _safe_col_name(audit_data.columns, _ORDER_COLS) or "订单号"
    mat_col = _safe_col_name(audit_data.columns, _MAT_COLS) or "组件物料号"
    remark_col = _safe_col_name(audit_data.columns, _REMARK_COLS) or "备注"
    audit_data["_work_date"] = audit_data[date_col].astype(str).str[:10]
    audit_data["_order_no"]  = audit_data[order_col].astype(str)
    audit_data["_mat_code"]  = audit_data[mat_col].astype(str)
    merged = audit_data.merge(db_records, left_on=["_work_date", "_order_no", "_mat_code"],
                              right_on=["work_date", "order_no", "mat_code"], how="left")
    current_remark = audit_data[remark_col].fillna("")
    db_remark      = merged["remark"].fillna("")
    audit_data[remark_col] = current_remark.where(current_remark != "", db_remark)
    audit_data["_audit_status"] = merged["status"].fillna("未审核")
    audit_data.drop(["_work_date", "_order_no", "_mat_code"], axis=1, inplace=True)
    if log_cb:
        log_cb("✅ 已从历史记录恢复审核匹配", "info")


def export_audit_backup(file_path, log_cb=None):
    db_path = get_audit_db_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError("审核数据库不存在，无法导出")
    with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, arcname="audit_log.db")
    if log_cb:
        log_cb(f"✅ 审核记录已导出：{file_path}", "success")


def import_audit_backup(file_path, log_cb=None):
    db_path = get_audit_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with zipfile.ZipFile(file_path, "r") as zf:
        zf.extract("audit_log.db", os.path.dirname(db_path))
    if log_cb:
        log_cb("✅ 审核记录已从备份恢复，下次加载时生效", "success")
