#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" 审核数据库存储模块 — SQLite 持久化、备份导入导出
    v37.44 重大升级：从 "原表行号" 改为业务主键 (订单日期, 流程订单, 物料编码)
"""
import os
import sqlite3
import zipfile
import shutil
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
            shutil.copy2(old_db, new_db)
        except Exception:
            pass  # 迁移失败不影响启动
    return new_dir


def get_audit_db_path():
    return os.path.join(_get_app_dir(), "audit_log.db")


# ── 列名候选列表 ──────────────────────────────────────────────────────────────

_DATE_COLS   = ["订单日期", "订单开始日期", "工单日期", "日期"]
_ORDER_COLS  = ["流程订单", "订单号", "订单编号", "订单号码", "订单No", "Order No"]
_MAT_COLS    = ["组件物料号", "物料编码", "物料号", "零件号", "组件号"]
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


# ── 备份 ─────────────────────────────────────────────────────────────────────

def _backup_db(log_cb=None):
    """在写入前备份数据库文件（时间戳命名），最多保留 10 份"""
    db_path = get_audit_db_path()
    if not os.path.exists(db_path):
        return
    app_dir = _get_app_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"audit_log_{ts}.db"
    backup_path = os.path.join(app_dir, backup_name)
    try:
        shutil.copy2(db_path, backup_path)
        if log_cb:
            log_cb(f"📦 数据库已备份：{backup_name}", "info")
        # 清理旧备份，只保留最近 10 份
        backups = sorted([f for f in os.listdir(app_dir) if f.startswith("audit_log_") and f.endswith(".db")])
        while len(backups) > 10:
            old = backups.pop(0)
            try:
                os.remove(os.path.join(app_dir, old))
            except Exception:
                pass
    except Exception as e:
        if log_cb:
            log_cb(f"⚠ 备份失败：{e}", "warn")


# ── 新表初始化 ───────────────────────────────────────────────────────────────

def _init_audit_db():
    """创建新的 audit_records 表（带 UNIQUE 约束，主键为业务三元组）"""
    conn = sqlite3.connect(get_audit_db_path())
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_records (
                order_date   TEXT NOT NULL,
                order_no     TEXT NOT NULL,
                material_code TEXT NOT NULL,
                status       TEXT DEFAULT '',
                remark       TEXT DEFAULT '',
                source       TEXT DEFAULT '',
                auditor      TEXT DEFAULT '',
                saved_at     TEXT DEFAULT '',
                PRIMARY KEY (order_date, order_no, material_code)
            )
        """)
        conn.commit()
    finally:
        conn.close()


def init_audit_db():
    """兼容旧入口：初始化数据库（同时兼容旧 audit_log 和新 audit_records）"""
    # 旧表初始化（如果存在）
    conn = sqlite3.connect(get_audit_db_path())
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                work_date TEXT NOT NULL,
                order_no  TEXT NOT NULL,
                mat_code  TEXT NOT NULL,
                status    TEXT,
                remark    TEXT,
                auditor   TEXT,
                saved_at  TEXT,
                PRIMARY KEY (work_date, order_no, mat_code)
            )
        """)
        conn.commit()
    finally:
        conn.close()
    # 新表初始化
    _init_audit_db()


# ── 升级检测与执行 ────────────────────────────────────────────────────────────

def needs_upgrade():
    """
    检测旧 audit_log 表是否缺少 order_date 列（即需要升级）。
    返回 True  if 需要升级，旧表有数据
    返回 False if 不需要升级（新表结构已就绪或旧表为空）
    """
    db_path = get_audit_db_path()
    if not os.path.exists(db_path):
        return False
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(audit_log)")
        columns = {row[1] for row in cursor.fetchall()}
        has_order_date = "order_date" in columns
        if has_order_date:
            return False
        # 检查旧表是否有数据
        cursor2 = conn.execute("SELECT COUNT(*) FROM audit_log")
        count = cursor2.fetchone()[0]
        return count > 0
    finally:
        conn.close()


def upgrade_audit_db(clear_old=False, log_cb=None):
    """
    执行数据库升级：
      1. 备份当前 .db 文件
      2. 将旧 audit_log 数据迁移到 audit_records（新表结构）
      3. 若 clear_old=True 则删除旧表，否则保留旧表

    clear_old=True  适合"清空旧历史"场景
    clear_old=False 适合"归档保留"场景（开发调试用）
    """
    _backup_db(log_cb=log_cb)
    db_path = get_audit_db_path()
    conn = sqlite3.connect(db_path)
    try:
        # 确保新表存在
        _init_audit_db()
        # 迁移旧表数据（如果有）
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        if cursor.fetchone():
            cursor2 = conn.execute("SELECT COUNT(*) FROM audit_log")
            old_count = cursor2.fetchone()[0]
            if old_count > 0:
                conn.execute("""
                    INSERT OR REPLACE INTO audit_records
                    (order_date, order_no, material_code, status, remark, auditor, saved_at)
                    SELECT
                        work_date AS order_date,
                        order_no,
                        mat_code AS material_code,
                        COALESCE(status, '') AS status,
                        COALESCE(remark, '') AS remark,
                        COALESCE(auditor, '') AS auditor,
                        COALESCE(saved_at, '') AS saved_at
                    FROM audit_log
                """)
                conn.commit()
                if log_cb:
                    log_cb(f"📦 已迁移 {old_count} 条旧记录到新表", "info")
            if clear_old:
                conn.execute("DROP TABLE IF EXISTS audit_log")
                conn.commit()
                if log_cb:
                    log_cb("🗑️ 已删除旧 audit_log 表", "info")
        if log_cb:
            log_cb("✅ 数据库升级完成", "success")
    finally:
        conn.close()


# ── 保存 ─────────────────────────────────────────────────────────────────────

def save_audit_to_db(audit_data, auditor=None, log_cb=None):
    """
    用业务主键 (订单日期, 流程订单, 物料编码) 保存审核记录。
    写入前自动备份数据库，新表采用 INSERT OR REPLACE 实现幂等写入。
    """
    if audit_data is None or audit_data.empty:
        return
    if auditor is None:
        auditor = os.getlogin()

    date_col = _safe_col_name(audit_data.columns, _DATE_COLS) or "订单日期"
    order_col = _safe_col_name(audit_data.columns, _ORDER_COLS) or "流程订单"
    mat_col = _safe_col_name(audit_data.columns, _MAT_COLS) or "组件物料号"
    remark_col = _safe_col_name(audit_data.columns, _REMARK_COLS)
    batch_remark_col = _safe_col_name(audit_data.columns, _BATCH_REMARK_COLS)

    # 写入前备份（避免覆盖历史）
    _backup_db(log_cb=log_cb)

    conn = sqlite3.connect(get_audit_db_path())
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows_saved = 0
        for _, row in audit_data.iterrows():
            order_date = str(row.get(date_col, ""))[:10]
            order_no = str(row.get(order_col, ""))
            mat_code = str(row.get(mat_col, ""))
            if not order_date or not order_no or not mat_code:
                continue
            remark = str(row.get(remark_col, "")).strip() if remark_col else ""
            if not remark and batch_remark_col:
                remark = str(row.get(batch_remark_col, "")).strip()
            status = "已备注" if remark else "未审核"
            source = str(row.get("备注来源", "")) if "备注来源" in audit_data.columns else ""
            conn.execute("""
                INSERT OR REPLACE INTO audit_records
                (order_date, order_no, material_code, status, remark, source, auditor, saved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (order_date, order_no, mat_code, status, remark, source, auditor, now))
            rows_saved += 1
        conn.commit()
        if log_cb:
            log_cb(f"✅ 审核记录已同步到本地数据库（{rows_saved} 条）", "success")
    finally:
        conn.close()


# ── 加载回填 ─────────────────────────────────────────────────────────────────

def restore_audit_from_db(audit_data, log_cb=None):
    """
    用 SQL LEFT JOIN 将历史审核记录回填到 audit_data。
    匹配键：订单日期 + 流程订单 + 物料编码（原表行号仅用于显示，不参与匹配）。
    """
    if audit_data is None or audit_data.empty:
        return

    conn = sqlite3.connect(get_audit_db_path())
    try:
        db_records = pd.read_sql_query("SELECT * FROM audit_records", conn)
    finally:
        conn.close()

    if db_records.empty:
        return

    date_col = _safe_col_name(audit_data.columns, _DATE_COLS) or "订单日期"
    order_col = _safe_col_name(audit_data.columns, _ORDER_COLS) or "流程订单"
    mat_col = _safe_col_name(audit_data.columns, _MAT_COLS) or "组件物料号"
    remark_col = _safe_col_name(audit_data.columns, _REMARK_COLS) or "备注原因"

    # 构建业务主键列（用于 JOIN）
    audit_data = audit_data.copy()
    audit_data["_key_date"] = audit_data[date_col].astype(str).str[:10]
    audit_data["_key_order"] = audit_data[order_col].astype(str)
    audit_data["_key_mat"] = audit_data[mat_col].astype(str)

    # SQL LEFT JOIN 替代 Python 循环
    merged = audit_data.merge(
        db_records.rename(columns={
            "order_date": "_key_date",
            "order_no": "_key_order",
            "material_code": "_key_mat",
        }),
        on=["_key_date", "_key_order", "_key_mat"],
        how="left"
    )

    # 回填逻辑：优先保留当前 DataFrame 中的备注（人工填写 > 批量填写 > 历史数据库）
    current_remark = audit_data[remark_col].fillna("").astype(str)
    db_remark = merged["remark"].fillna("").astype(str)
    # 当前备注为空时，用数据库备注填充
    audit_data[remark_col] = current_remark.where(current_remark.str.strip() != "", db_remark)

    # 回填审核状态
    if "audit_status" not in audit_data.columns:
        audit_data["audit_status"] = "未审核"
    merged_status = merged["status"].fillna("未审核").where(
        audit_data[remark_col].str.strip() != "", "未审核"
    )
    # 优先用数据库状态
    has_current = audit_data[remark_col].astype(str).str.strip() != ""
    audit_data["audit_status"] = merged_status.where(~has_current, audit_data.get("audit_status", "未审核"))

    # 回填备注来源
    if "备注来源" not in audit_data.columns:
        audit_data["备注来源"] = ""
    if "source" in merged.columns and merged["source"].notna().any():
        merged_source = merged["source"].fillna("")
        audit_data["备注来源"] = merged_source.where(
            audit_data["备注来源"].astype(str).str.strip() == "", audit_data["备注来源"]
        )

    # 清理临时列
    for col in ["_key_date", "_key_order", "_key_mat"]:
        if col in audit_data.columns:
            audit_data.drop(columns=[col], inplace=True)

    if log_cb:
        restored_count = (db_remark.str.strip() != "").sum()
        if restored_count > 0:
            log_cb(f"✅ 已从历史记录恢复 {restored_count} 条审核匹配", "success")


# ── 导入导出 ─────────────────────────────────────────────────────────────────

def export_audit_backup(file_path, log_cb=None):
    """导出审核记录为 ZIP 压缩包（包含 audit_records + audit_log 两表）"""
    db_path = get_audit_db_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError("审核数据库不存在，无法导出")
    with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, arcname="audit_log.db")
    if log_cb:
        log_cb(f"✅ 审核记录已导出：{file_path}", "success")


def import_audit_backup(file_path, log_cb=None):
    """从 ZIP 备份恢复（解压覆盖 db 文件）"""
    db_path = get_audit_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with zipfile.ZipFile(file_path, "r") as zf:
        zf.extract("audit_log.db", os.path.dirname(db_path))
    if log_cb:
        log_cb("✅ 审核记录已从备份恢复，下次加载时生效", "success")
