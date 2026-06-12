# -*- coding: utf-8 -*-
"""
数据服务层
负责：数据预处理、指纹计算、已读状态恢复、变动检测、净偏差修正等
"""

import pandas as pd
import numpy as np
from PySide6.QtCore import QObject, Signal

from core.fingerprint import calc_fingerprint
from core.read_status import load_read_status, load_audit_results, record_deviation_change
from core.change_detector import detect_changes


class DataService(QObject):
    """数据处理服务，与界面解耦"""

    log_signal = Signal(str, str)  # (msg, level)

    def __init__(self, alt_controller=None, parent=None):
        super().__init__(parent)
        self.alt_controller = alt_controller

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def preprocess_audit_data(self, df: pd.DataFrame, previous_df: pd.DataFrame = None) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        try:
            # ── 首步：清理脏列 ──
            df = self._clean_columns(df)

            # 确保数值列是数值类型（防止字符串导致聚合报错）
            rate_col = None
            for c in ['偏差率(%)', '偏差率']:
                if c in df.columns:
                    rate_col = c
                    break
            if rate_col:
                # 如果值含百分号，先去掉再转数值
                if df[rate_col].dtype == object:
                    df[rate_col] = df[rate_col].astype(str).str.replace('%', '', regex=False)
                df[rate_col] = pd.to_numeric(df[rate_col], errors='coerce').fillna(0.0)
            for num_col in ['定额', '实际', '偏差数量', '偏差金额', '偏差金额(含税)', '净偏差金额']:
                if num_col in df.columns:
                    df[num_col] = pd.to_numeric(df[num_col], errors='coerce').fillna(0.0)

            # 数值列转换完成后，如果偏差率字符串列为空，从数值列自动生成
            if '偏差率(%)' in df.columns and '偏差率' in df.columns:
                if (df['偏差率'].isna().all() or (df['偏差率'].astype(str).str.strip() == '').all()):
                    df['偏差率'] = df['偏差率(%)'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else '')
            df = self._normalize_alt_flag(df)
            df = self._add_data_id_and_fingerprint(df)
            df = self._restore_read_status(df)
            if previous_df is not None and not previous_df.empty:
                self._detect_and_notify_changes(previous_df, df)
            df = self._reorder_columns(df)
            # 统一审核结果列名
            if '审核结果' in df.columns and 'audit_result' in df.columns:
                # 两列都有 → 用新数据(audit_result)覆盖旧列(审核结果)，删英文列
                df = df.drop(columns=['审核结果'])
                df = df.rename(columns={'audit_result': '审核结果'})
            elif '审核结果' in df.columns:
                # 只有中文列，删掉英文列（如果有残留）
                df = df.drop(columns=['audit_result'], errors='ignore')
            elif 'audit_result' in df.columns:
                df = df.rename(columns={'audit_result': '审核结果'})
            # 再次确保没有重复列名
            dup = df.columns[df.columns.duplicated(keep='first')]
            if len(dup) > 0:
                df = df.loc[:, ~df.columns.duplicated(keep='first')]
            # 从 DB 恢复审核结果（覆盖重新分析产生的空值）
            df = self._restore_audit_results(df)
            if self.alt_controller:
                pass  # 净偏差计算已在 analyzer.py 中完成
            return df
        except Exception as e:
            self.log(f"数据预处理失败: {e}", "error")
            import traceback
            traceback.print_exc()
            return df

    def _clean_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理重复列：保留第一个出现的，删除后续同名列"""
        # 1. 去掉空的替代料组列（保留 _替代料组）
        if '替代料组' in df.columns and '_替代料组' in df.columns:
            df = df.drop(columns=['替代料组'])
        # 2. 去掉冗余的净偏差列（如果有单独的"净偏差"列，保留净偏差数量和净偏差金额）
        if '净偏差' in df.columns:
            df = df.drop(columns=['净偏差'])
            self.log("已删除冗余列：净偏差", "info")
        # 3. 强制去重（保留第一个）
        dup_cols = df.columns[df.columns.duplicated()].unique()
        if len(dup_cols) > 0:
            df = df.loc[:, ~df.columns.duplicated(keep='first')]
            self.log(f"已清理重复列: {list(dup_cols)}", "warning")
        return df

    def _normalize_alt_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        if "是否替代料" in df.columns:
            def _norm_alt(v):
                if pd.isna(v):
                    return "否"
                s = str(v).strip().lower()
                if s in ("是", "true", "1", "yes", "y"):
                    return "是"
                if "替代" in s or "alt" in s:
                    return "是"
                return "否"
            df["是否替代料"] = df["是否替代料"].apply(_norm_alt)
        else:
            if self.alt_controller and self.alt_controller.get_pairs():
                alt_codes = set()
                for a, b in self.alt_controller.get_pairs():
                    if isinstance(a, (list, tuple)) and len(a) > 1:
                        alt_codes.add(str(a[1]).strip())
                    if isinstance(b, (list, tuple)) and len(b) > 1:
                        alt_codes.add(str(b[1]).strip())
                code_col = None
                for c in ['物料号', '物料编码', 'code', '组件物料号']:
                    if c in df.columns:
                        code_col = c
                        break
                if code_col:
                    df['是否替代料'] = df[code_col].astype(str).str.strip().isin(alt_codes)
                    df['是否替代料'] = df['是否替代料'].map({True: '是', False: '否'})
                else:
                    df['是否替代料'] = '否'
            else:
                df['是否替代料'] = '否'
        return df

    def _add_data_id_and_fingerprint(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['data_id'] = df['订单日期'].astype(str) + '|' + df['流程订单'].astype(str) + '|' + df['物料编码'].astype(str)
            print(f'[DEBUG data_service] data_id 示例: {df["data_id"].iloc[0]}')
            print(f'[DEBUG data_service] 可用列: {list(df.columns)[:20]}')
        except Exception as e:
            self.log(f"创建data_id失败: {e}", "error")
            import traceback; traceback.print_exc()
            df['data_id'] = df.index.astype(str)
            print(f'[DEBUG data_service] data_id 创建失败，用索引回退')

        try:
            df['fingerprint'] = df.apply(
                lambda r: calc_fingerprint(
                    r.get('偏差金额(含税)', r.get('偏差金额', 0)),
                    r.get('偏差率(%)', 0)
                ), axis=1
            )
        except Exception as e:
            self.log(f"计算指纹失败: {e}", "error")
            df['fingerprint'] = "0.00|0.0"
        return df

    def _restore_read_status(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            data_ids = df['data_id'].tolist()
            status_map = load_read_status(data_ids)
        except Exception as e:
            self.log(f"加载历史状态失败: {e}", "error")
            import traceback; traceback.print_exc()
            status_map = {}

        read_list = []
        matched_count = 0
        fp_mismatch_count = 0
        for _, row in df.iterrows():
            did = row['data_id']
            fp = row['fingerprint']
            if did in status_map:
                matched_count += 1
                hist_read, hist_fp = status_map[did]
                if str(hist_fp) == str(fp):
                    read_list.append(hist_read)
                else:
                    fp_mismatch_count += 1
                    read_list.append(0)
            else:
                read_list.append(0)
        print(f'[DEBUG _restore_read_status] 总行数={len(df)}, 匹配={matched_count}, 指纹不匹配={fp_mismatch_count}, status_map大小={len(status_map)}')
        if matched_count > 0:
            print(f'[DEBUG _restore_read_status] 示例 data_id: {data_ids[0]}')
            print(f'[DEBUG _restore_read_status] DB中有该ID: {data_ids[0] in status_map}')
        df['_read'] = read_list
        return df

    def _restore_audit_results(self, df: pd.DataFrame) -> pd.DataFrame:
        """从 DB 恢复审核结果（审核结果、AI建议、备注来源）"""
        try:
            data_ids = df['data_id'].tolist()
            audit_map = load_audit_results(data_ids)
        except Exception as e:
            self.log(f"加载审核结果失败: {e}", "error")
            return df

        if not audit_map:
            return df

        restored = 0
        for col, key in [('审核结果', 'audit_result'), ('AI建议', 'ai_suggestion'), ('备注来源', 'note_source')]:
            if col not in df.columns:
                df[col] = ''
            col_idx = df.columns.get_loc(col)
            # 处理重复列名（get_loc 可能返回数组）
            if isinstance(col_idx, (list, slice, np.ndarray)):
                col_idx = col_idx[0] if hasattr(col_idx, '__getitem__') else int(col_idx)
            for i in range(len(df)):
                did = df.iloc[i].get('data_id', '')
                if did in audit_map:
                    saved_val = audit_map[did].get(key, '')
                    current_val = df.iloc[i, col_idx]
                    try:
                        is_empty = pd.isna(current_val) or str(current_val).strip() == ''
                    except Exception:
                        is_empty = False
                    if is_empty and saved_val:
                        df.iloc[i, col_idx] = saved_val
                        if key == 'audit_result' and saved_val:
                            restored += 1

        if restored > 0:
            self.log(f"从数据库恢复了 {restored} 条审核结果", "info")
        return df

    def _detect_and_notify_changes(self, old_df: pd.DataFrame, new_df: pd.DataFrame):
        old_snapshot = {}
        try:
            for _, row in old_df.iterrows():
                if self._is_record_audited(row):
                    did = f"{row['订单日期']}|{row['流程订单']}|{row['物料编码']}"
                    old_snapshot[did] = (
                        row.get('偏差金额(含税)', row.get('偏差金额', 0)),
                        row.get('偏差率(%)', 0)
                    )
        except Exception as e:
            self.log(f"构建旧快照失败: {e}", "error")

        new_audited = []
        try:
            for _, row in new_df.iterrows():
                if self._is_record_audited(row):
                    new_audited.append({
                        'data_id': row['data_id'],
                        'amount': row.get('偏差金额(含税)', row.get('偏差金额', 0)),
                        'rate': row.get('偏差率(%)', 0)
                    })
        except Exception as e:
            self.log(f"构建新快照失败: {e}", "error")

        changes = []
        try:
            changes = detect_changes(old_snapshot, new_audited)
        except Exception as e:
            self.log(f"检测变动失败: {e}", "error")

        if changes:
            try:
                for ch in changes:
                    record_deviation_change(
                        ch['data_id'], ch['old_amount'], ch['new_amount'],
                        ch['old_rate'], ch['new_rate'], "重新分析数据变动"
                    )
            except Exception as e:
                self.log(f"记录变动失败: {e}", "error")
            self.log(f"发现 {len(changes)} 条已审核记录发生数值变动，已强制设为'未读'", "warning")
            self.log_signal.emit(f"变动提醒|{len(changes)}", "alert")

    def _is_record_audited(self, row):
        try:
            if '审核状态' in row and row['审核状态'] == '已审核':
                return True
            if '备注来源' in row and row['备注来源'] not in ('', 'AI审核', None):
                return True
        except Exception:
            pass
        return False

    def _reorder_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            cols = list(df.columns)
            amt_col = None
            for col in ['偏差金额(含税)', '偏差金额']:
                if col in cols:
                    amt_col = col
                    break
            rate_col = None
            for col in ['偏差率(%)', '偏差率']:
                if col in cols:
                    rate_col = col
                    break
            if amt_col and rate_col:
                cols = [c for c in cols if c != rate_col]
                amt_idx = cols.index(amt_col)
                cols.insert(amt_idx + 1, rate_col)
                df = df[cols]
                self.log(f"已调整列顺序：{rate_col} 移到 {amt_col} 后面", "info")
        except Exception as e:
            self.log(f"列重排序失败: {e}", "error")
        return df

    def update_summary_stats(self, df: pd.DataFrame):
        total = len(df)
        high = 0
        need_note = 0
        ok = 0
        if '偏差率(%)' in df.columns:
            high = (df['偏差率(%)'].abs() > 10).sum()
        if '备注原因' in df.columns:
            need_note = (df['备注原因'].isna() | (df['备注原因'] == '')).sum()
        ok = total - need_note
        return total, high, need_note, ok
