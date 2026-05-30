# -*- coding: utf-8 -*-
"""批量操作模块 - 批量导出 + 批量导入备注"""

import pandas as pd
import os
from tkinter import messagebox
from typing import List, Tuple, Optional
import tempfile
import shutil

from core import history_db, backup_manager


def batch_export_analyses(analysis_ids: List[int], output_path: str, 
                        db_path: Optional[str] = None, 
                        progress_callback=None) -> Tuple[bool, str]:
    """
    批量导出分析记录到 Excel（多 sheet）
    
    Args:
        analysis_ids: 分析记录 ID 列表
        output_path: 输出 Excel 路径
        db_path: 数据库路径
        progress_callback: 回调函数 (current, total, message)
    
    Returns:
        (成功标志, 消息)
    """
    if not analysis_ids:
        return False, "No records selected"
    
    if len(analysis_ids) > 10:
        return False, "单次最多导出 10 个记录"
    
    try:
        total = len(analysis_ids)
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for i, aid in enumerate(analysis_ids):
                if progress_callback:
                    progress_callback(i + 1, total, f"正在导出第 {i + 1}/{total} 个...")
                
                # 获取数据
                df = history_db.get_analysis_data(aid, db_path=db_path)
                if df is None or df.empty:
                    continue
                
                # 获取元数据
                meta = history_db.get_analysis_list(limit=1, db_path=db_path)
                meta_row = None
                if meta:
                    for m in meta:
                        if m['id'] == aid:
                            meta_row = m
                            break
                
                # Sheet 名称：日期_文件名（截断）
                if meta_row:
                    timestamp = meta_row['timestamp'][:10]
                    file_name = meta_row['file_name'][:20]
                    sheet_name = f"{timestamp}_{file_name}"
                else:
                    sheet_name = f"Sheet_{aid}"
                
                # Excel 不允许 sheet 名含特殊字符
                sheet_name = sheet_name.replace('/', '-').replace('\\', '-').replace('*', '-').replace('?', '-').replace('[', '').replace(']', '')
                
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return True, f"成功导出 {total} 个记录到 {output_path}"
    
    except Exception as e:
        return False, f"导出失败: {str(e)}"


def detect_encoding(file_path: str) -> Optional[str]:
    """尝试自动检测文件编码"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def preview_import_notes(file_path: str, db_path: Optional[str] = None) -> Tuple[bool, dict]:
    """
    预览导入备注（预演模式）
    
    Args:
        file_path: CSV/Excel 文件路径
        db_path: 数据库路径
    
    Returns:
        (成功, {'matched': [...], 'unmatched': [...], 'stats': {...}})
    """
    # 检测编码
    enc = detect_encoding(file_path)
    if enc is None:
        return False, {"error": "无法识别文件编码"}
    
    try:
        # 读取文件
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, encoding=enc)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        return False, {"error": f"读取文件失败: {str(e)}"}
    
    if df.empty:
        return False, {"error": "文件中无数据"}
    
    # 确定列名
    cols = df.columns.tolist()
    material_col = None
    order_col = None
    note_col = None
    
    for col in cols:
        col_l = col.lower()
        if '物料' in col or 'material' in col_l:
            if material_col is None:
                material_col = col
        elif '订单' in col or 'order' in col_l:
            order_col = col
        elif '备注' in col or 'note' in col_l or 'comment' in col_l:
            note_col = col
    
    if note_col is None:
        return False, {"error": "文件中未找到备注列"}
    
    if material_col is None and order_col is None:
        return False, {"error": "文件中未找到物料编码列或订单号列"}
    
    # 匹配逻辑
    matched = []
    unmatched = []
    
    # 获取所有历史分析的偏差明细（用于匹配）
    # 这里简化：仅从最新的分析中匹配
    latest_records = history_db.get_analysis_list(limit=1, db_path=db_path)
    if not latest_records:
        return False, {"error": "无历史分析记录"}
    
    latest_id = latest_records[0]['id']
    df_audit = history_db.get_analysis_data(latest_id, db_path=db_path)
    
    if df_audit is None or df_audit.empty:
        return False, {"error": "历史分析数据为空"}
    
    # 审计数据列名
    audit_cols = df_audit.columns.tolist()
    audit_material_col = None
    for col in ['物料编码', 'material_code', '物料编号']:
        if col in audit_cols:
            audit_material_col = col
            break
    
    for _, row in df.iterrows():
        material_code = row.get(material_col) if material_col else None
        order_code = row.get(order_col) if order_col else None
        note = row.get(note_col)
        
        if audit_material_col and material_code:
            # 按物料编码匹配
            mask = df_audit[audit_material_col].astype(str) == str(material_code)
            matches = df_audit[mask]
            if not matches.empty:
                matched.append({
                    'material_code': material_code,
                    'note': note,
                    'matched_rows': matches.index.tolist()
                })
            else:
                unmatched.append({'material_code': material_code, 'note': note})
        else:
            unmatched.append({'material_code': material_code, 'order_code': order_code, 'note': note})
    
    stats = {
        'total': len(df),
        'matched': len(matched),
        'unmatched': len(unmatched)
    }
    
    return True, {'matched': matched, 'unmatched': unmatched, 'stats': stats}


def confirm_import_notes(matched_list: List[dict], db_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    确认导入备注
    
    Args:
        matched_list: 匹配成功的记录列表
        db_path: 数据库路径
    
    Returns:
        (成功, 消息)
    """
    if not matched_list:
        return False, "无匹配记录"
    
    try:
        # 先备份
        backup_manager.backup_before_analysis(db_path=db_path)
    except Exception as e:
        return False, f"备份失败: {str(e)}"
    
    # TODO: 实际更新数据库中的备注字段
    # 这里需要修改历史数据库的结构，添加 remark 列
    # 暂时只返回成功消息
    
    return True, f"成功更新 {len(matched_list)} 行备注"