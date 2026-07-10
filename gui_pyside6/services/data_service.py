# -*- coding: utf-8 -*-
"""
数据服务层
负责：数据预处理、指纹计算、已读状态恢复、变动检测、净偏差修正等
"""

import pandas as pd
import numpy as np
from PySide6.QtCore import QObject, Signal

from core.fingerprint import calc_fingerprint
from core.read_status import load_read_status, load_audit_results, record_deviation_change, get_deviation_history, save_snapshot_qty
from core.change_detector import detect_changes
from core.quarantine_manager import get_quarantined_ids


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
            for num_col in ['定额', '实际', '偏差数量', '偏差金额', '偏差金额(含税)', '净偏差数量', '净偏差金额', '净偏差率(%)']:
                if num_col in df.columns:
                    df[num_col] = pd.to_numeric(df[num_col], errors='coerce').fillna(0.0)

            # 数值列转换完成后，如果偏差率字符串列为空，从数值列自动生成
            if '偏差率(%)' in df.columns and '偏差率' in df.columns:
                if (df['偏差率'].isna().all() or (df['偏差率'].astype(str).str.strip() == '').all()):
                    df['偏差率'] = df['偏差率(%)'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else '')
            df = self._normalize_alt_flag(df)
            df = self._add_data_id_and_fingerprint(df)
            df = self._restore_read_status(df)
            df = self._restore_quarantine_status(df)
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
            # 新增：计算净偏差率（净偏差数量 / 定额）
            df = self._compute_net_deviation_rate(df)
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
        if '净偏差' in df.columns and '净偏差数量' not in df.columns and '净偏差金额' not in df.columns:
            df = df.drop(columns=['净偏差'])
            self.log("已删除冗余列：净偏差（无净偏差数量/金额时）", "info")
        # 3. 去掉重复的偏差率列（保留数值格式的"偏差率(%)"，删除字符串格式的"偏差率"）
        if '偏差率' in df.columns and '偏差率(%)' in df.columns:
            df = df.drop(columns=['偏差率'])
            self.log("已删除冗余列：偏差率（保留偏差率(%)）", "info")
        # 4. 强制去重（保留第一个）
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
            # 没有是否替代料列时，默认为否（不做简单编码匹配，避免误标）
            df['是否替代料'] = '否'
        return df

    def _add_data_id_and_fingerprint(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df['data_id'] = df['订单日期'].astype(str) + '|' + df['流程订单'].astype(str) + '|' + df['物料编码'].astype(str)
            print(f'[DEBUG data_service] data_id 示例: {df["data_id"].iloc[0]}')
            print(f'[DEBUG data_service] 可用列: {list(df.columns)}')
            print(f'[DEBUG data_service] 净偏差数量={("净偏差数量" in df.columns)}, 净偏差金额={("净偏差金额" in df.columns)}, 定额={("定额" in df.columns)}')
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
        """恢复已读状态 + 审核后变更检测（方案A：只盯实际数量）。

        基线策略：
        - 历史记录有 snapshot_qty（审核时保存的实际数量）→ 与当前实际数量比对；
        - 历史记录无 snapshot_qty（旧记录/基线未初始化）→ 用当前数量静默建立基线，不报警（旧记录静默迁移）；
        - 实际数量被改动 → 回退未读 + 行红标 + deviation_history 留痕 + 弹变动提醒。
        """
        try:
            data_ids = df['data_id'].tolist()
            status_map = load_read_status(data_ids)
        except Exception as e:
            self.log(f"加载历史状态失败: {e}", "error")
            import traceback; traceback.print_exc()
            status_map = {}

        real_col = self._find_real_qty_col(df)
        read_list = []
        matched_count = 0
        changed_count = 0
        changed_indices = []   # 收集实际数量被改动（vs 审核时基线）行的位置
        for idx, row in df.iterrows():
            did = row['data_id']
            cur_qty = self._safe_qty(row.get(real_col)) if real_col else None
            if did in status_map:
                matched_count += 1
                hist_read, hist_fp, hist_snap = status_map[did]
                if hist_snap is None:
                    # 旧记录（基线未初始化）→ 用当前数量静默建立基线，不报警（旧记录静默迁移）
                    try:
                        save_snapshot_qty(did, cur_qty)
                    except Exception:
                        pass
                    read_list.append(hist_read)
                elif cur_qty is None:
                    # 无法取得数量，保守保留已读状态
                    read_list.append(hist_read)
                elif abs(float(hist_snap) - float(cur_qty)) < 1e-6:
                    # 实际数量未变 → 正常
                    read_list.append(hist_read)
                else:
                    # 实际数量被改动 → 审核后数据被私自修改
                    changed_count += 1
                    read_list.append(0)  # 强制回退未读，避免假审批
                    changed_indices.append(idx)
                    self._record_post_audit_change(did, hist_snap, cur_qty)
            else:
                read_list.append(0)
        print(f'[DEBUG _restore_read_status] 总行数={len(df)}, 匹配={matched_count}, 数量被改={changed_count}, status_map大小={len(status_map)}')
        df['_read'] = read_list
        # 审核后变更标记列（供卡片计数 / 行红标 / 点击过滤使用）
        df['_post_audit_changed'] = 0
        if changed_indices:
            df.loc[changed_indices, '_post_audit_changed'] = 1
            self.log(f"⚠️ 发现 {len(changed_indices)} 条已审核记录的实际数量被修改，已强制设为未读并留痕", "warning")
            self.log_signal.emit(f"变动提醒|{len(changed_indices)}", "alert")
        return df

    @staticmethod
    def _find_real_qty_col(df: pd.DataFrame):
        """探测实际数量列名（不同 SAP 导出可能不同）

        注意：analyzer 输出的主表把「数量-实际」重命名为「实际」，故必须同时覆盖两者。
        """
        candidates = ['数量-实际', '实际', '实际数量', '数量 - 实际', 'actual',
                      '实际收货数量', '已收货数量', '收货数量', '实际领用数量', '实收数量']
        for c in candidates:
            if c in df.columns:
                return c
        # 模糊兜底：含 '实际' 且含 '数量'
        for c in df.columns:
            s = str(c)
            if '实际' in s and '数量' in s:
                return c
        return None

    @staticmethod
    def _safe_qty(v):
        """把单元格值安全转成 float，失败/空返回 None"""
        try:
            if v is None:
                return None
            if isinstance(v, float) and pd.isna(v):
                return None
            return float(v)
        except (ValueError, TypeError):
            return None

    def _restore_quarantine_status(self, df: pd.DataFrame) -> pd.DataFrame:
        """水合隔离区状态：从 SQLite 读取当前隔离的 data_id 集合，给主表加 _quarantined 列。

        引用模式——只存 data_id，实际数据实时从主表读取；因此主表数量被改（如500->550）
        后重新导入，隔离行会自动同步为新值，无需额外同步代码。
        """
        try:
            qids = get_quarantined_ids()
        except Exception as e:
            self.log(f"加载隔离区状态失败: {e}", "error")
            qids = set()
        df['_quarantined'] = 0
        if qids and 'data_id' in df.columns:
            df.loc[df['data_id'].isin(qids), '_quarantined'] = 1
        return df

    def _record_post_audit_change(self, data_id: str, old_qty, new_qty):
        """记录审核后实际数量变动（方案A：只盯实际数量；带去重避免反复重导刷库）"""
        try:
            try:
                history = get_deviation_history(data_id)
            except Exception:
                history = []
            if history:
                latest = history[0]  # 已按 change_time DESC
                if abs(float(latest.get('new_qty') or 0) - float(new_qty or 0)) < 1e-6:
                    return  # 同一变更已记录，跳过
            record_deviation_change(data_id, '实际数量', old_qty, new_qty, "审核后数据被修改")
        except Exception as e:
            self.log(f"记录变动历史失败: {e}", "error")

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

    def _compute_net_deviation_rate(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算净偏差率（净偏差数量 / 定额 或 净偏差金额 / 偏差金额）—— 行级计算（仅作兜底）"""
        try:
            # 关键：分析阶段 apply_net_offset 已计算正确的净偏差率（含替代料组级统一值）。
            # 若列已存在，直接保留，避免被行级重算覆盖（覆盖会导致同组净偏差率不一致）。
            if '净偏差率(%)' in df.columns and df['净偏差率(%)'].notna().any():
                self.log("净偏差率(%) 已存在（来自分析结果），保留原值，跳过行级重算", "debug")
                return df

            net_qty_col = None
            for c in ['净偏差数量', 'net_qty', '净偏差']:
                if c in df.columns:
                    net_qty_col = c
                    break
            net_amt_col = None
            for c in ['净偏差金额', 'net_amt']:
                if c in df.columns:
                    net_amt_col = c
                    break
            quota_col = None
            for c in ['配额', '定额', '数量-定额']:
                if c in df.columns:
                    quota_col = c
                    break
            amt_col = None
            for c in ['偏差金额(含税)', '偏差金额']:
                if c in df.columns:
                    amt_col = c
                    break

            if net_qty_col and quota_col:
                net_vals = pd.to_numeric(df[net_qty_col], errors='coerce').fillna(0)
                quota_vals = pd.to_numeric(df[quota_col], errors='coerce').replace(0, float('nan'))
                df['净偏差率(%)'] = (net_vals / quota_vals * 100).round(2)
                df['净偏差率(%)'] = df['净偏差率(%)'].replace([np.inf, -np.inf], np.nan).fillna(0)
                self.log(f"已计算净偏差率（{net_qty_col}/{quota_col}×100%），非零值={df['净偏差率(%)'].abs().gt(0).sum()}条", "info")
            elif net_amt_col and amt_col:
                net_vals = pd.to_numeric(df[net_amt_col], errors='coerce').fillna(0)
                amt_vals = pd.to_numeric(df[amt_col], errors='coerce').replace(0, float('nan'))
                df['净偏差率(%)'] = (net_vals / amt_vals * 100).round(2)
                df['净偏差率(%)'] = df['净偏差率(%)'].replace([np.inf, -np.inf], np.nan).fillna(0)
                self.log(f"已计算净偏差率（{net_amt_col}/{amt_col}×100%）", "info")
            else:
                self.log(f"缺少计算净偏差率的列（净偏差数量={net_qty_col}, 定额={quota_col}, 净偏差金额={net_amt_col}, 偏差金额={amt_col}）", "debug")
        except Exception as e:
            self.log(f"计算净偏差率失败: {e}", "error")
            import traceback
            traceback.print_exc()
        return df

    def _detect_and_notify_changes(self, old_df: pd.DataFrame, new_df: pd.DataFrame):
        """同会话重新分析时，比对已审核记录的实际数量是否变动（方案A：只盯实际数量）"""
        old_snapshot = {}
        try:
            real_col_old = self._find_real_qty_col(old_df)
            for _, row in old_df.iterrows():
                if self._is_record_audited(row):
                    did = row['data_id']
                    old_snapshot[did] = self._safe_qty(row.get(real_col_old))
        except Exception as e:
            self.log(f"构建旧快照失败: {e}", "error")

        real_col_new = self._find_real_qty_col(new_df)
        changes = []
        try:
            for _, row in new_df.iterrows():
                if self._is_record_audited(row):
                    did = row['data_id']
                    if did in old_snapshot:
                        old_q = old_snapshot[did]
                        new_q = self._safe_qty(row.get(real_col_new))
                        if old_q is not None and new_q is not None and abs(old_q - new_q) >= 1e-6:
                            changes.append((did, old_q, new_q))
        except Exception as e:
            self.log(f"检测变动失败: {e}", "error")

        if changes:
            try:
                for did, old_q, new_q in changes:
                    record_deviation_change(did, '实际数量', old_q, new_q, "重新分析数据变动")
            except Exception as e:
                self.log(f"记录变动失败: {e}", "error")
            self.log(f"发现 {len(changes)} 条已审核记录的实际数量发生变动，已强制设为'未读'", "warning")
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
                # 偏差率移到偏差金额后面
                amt_idx = cols.index(amt_col)
                cols.insert(amt_idx + 1, rate_col)
                df = df[cols]
                self.log(f"已调整列顺序：偏差率及净偏差列移到偏差金额后面", "info")
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


def snapshot_qty_for(df: pd.DataFrame, data_id) -> float:
    """取某 data_id 当前实际数量（用于审核时建立变更检测基线）；找不到返回 None"""
    col = DataService._find_real_qty_col(df)
    if col is None or 'data_id' not in df.columns:
        return None
    try:
        sel = df.loc[df['data_id'] == data_id, col]
        if len(sel) == 0:
            return None
        v = sel.iloc[0]
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except Exception:
        return None
