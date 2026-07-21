# -*- coding: utf-8 -*-
"""
数据服务层
负责：数据预处理、指纹计算、已读状态恢复、变动检测、净偏差修正等
"""

import pandas as pd
import numpy as np
from PySide6.QtCore import QObject, Signal

from core.read_status import (
    load_read_status, load_audit_results,
    record_deviation_change, record_deviation_change_batch,
    get_deviation_history, save_snapshot_batch,
)
from core.change_detector import detect_changes
from core.quarantine_manager import get_quarantined_ids


class DataService(QObject):
    """数据处理服务，与界面解耦"""

    log_signal = Signal(str, str)  # (msg, level)

    def __init__(self, alt_controller=None, parent=None):
        super().__init__(parent)
        self.alt_controller = alt_controller
        self.last_audit_changes = []  # 审核后变更详情，供弹窗展示/导出

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
        # 2. 去掉冗余的"净偏差"列（已废弃，净偏差数量/金额/率仍保留）
        if '净偏差' in df.columns and '净偏差金额' in df.columns:
            df = df.drop(columns=['净偏差'])
            self.log("已删除冗余列：净偏差（净偏差金额已存在）", "info")
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
            # 向量化计算指纹，避免 df.apply(..., axis=1) 的 Python 级逐行开销
            amount_col = '偏差金额(含税)' if '偏差金额(含税)' in df.columns else '偏差金额'
            amount = pd.to_numeric(df[amount_col], errors='coerce').fillna(0.0) if amount_col in df.columns else pd.Series(0.0, index=df.index)
            rate = pd.to_numeric(df['偏差率(%)'], errors='coerce').fillna(0.0) if '偏差率(%)' in df.columns else pd.Series(0.0, index=df.index)
            df['fingerprint'] = amount.round(2).astype(str) + '|' + rate.round(1).astype(str)
        except Exception as e:
            self.log(f"计算指纹失败: {e}", "error")
            df['fingerprint'] = "0.00|0.0"
        return df

    def _restore_read_status(self, df: pd.DataFrame) -> pd.DataFrame:
        """恢复已读状态 + 审核后变更检测（方案A：只盯实际数量 + 备注原因）。

        基线策略：
        - 历史记录有 snapshot_qty / snapshot_note（审核时保存的基线）→ 与当前比对；
        - 历史记录无基线（旧记录/基线未初始化）→ 用当前值静默建立基线，不报警（旧记录静默迁移）；
        - 实际数量 或 备注原因 被改动 → 回退未读 + 行红标 + deviation_history 留痕 + 弹变动提醒。

        性能：改用向量化 + 批量 SQLite，避免万行级 Python 循环和逐条开库。
        """
        try:
            data_ids = df['data_id'].tolist()
            status_map = load_read_status(data_ids)
        except Exception as e:
            self.log(f"加载历史状态失败: {e}", "error")
            import traceback; traceback.print_exc()
            status_map = {}

        real_col = self._find_real_qty_col(df)
        remark_col = self._find_remark_col(df)
        self.last_audit_changes = []  # 每次重新加载都重置变更详情

        # 没有历史状态：直接全部未读
        if not status_map:
            df['_read'] = 0
            df['_post_audit_changed'] = 0
            return df

        # 1. 把历史状态对齐到 df（避免 Python 级逐行查找）
        status_df = pd.DataFrame.from_dict(
            status_map, orient='index',
            columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note']
        )
        df = df.join(status_df, on='data_id')

        has_status = df['_hist_read'].notna()
        missing_baseline = has_status & (df['_hist_snap'].isna() | df['_hist_note'].isna())
        has_baseline = has_status & ~missing_baseline

        # 2. 当前实际数量 / 备注原因
        if real_col:
            cur_qty = pd.to_numeric(df[real_col], errors='coerce')
        else:
            cur_qty = pd.Series([np.nan] * len(df), index=df.index)
        if remark_col:
            cur_note = df[remark_col].apply(self._norm_note)
        else:
            cur_note = pd.Series([''] * len(df), index=df.index)

        # 3. 旧记录无基线 → 批量静默建立基线（不报警）
        if missing_baseline.any():
            init_records = list(zip(
                df.loc[missing_baseline, 'data_id'],
                cur_qty[missing_baseline],
                cur_note[missing_baseline],
            ))
            save_snapshot_batch(init_records)

        # 4. 两基线都已初始化 → 向量化比对
        hist_snap = pd.to_numeric(df['_hist_snap'], errors='coerce')
        hist_note = df['_hist_note'].apply(self._norm_note)
        qty_changed = has_baseline & cur_qty.notna() & (abs(hist_snap - cur_qty) >= 1e-6)
        note_changed = has_baseline & (hist_note != cur_note)
        changed = qty_changed | note_changed

        # 5. 组装 _read / _post_audit_changed
        hist_read_int = df['_hist_read'].fillna(0).astype(int)
        df['_read'] = np.where(changed, 0, np.where(has_status, hist_read_int, 0))
        df['_post_audit_changed'] = changed.astype(int)

        # 6. 批量记录变动历史 + 收集弹窗详情
        if changed.any():
            changes_records = []
            qty_changed_idx = df.index[qty_changed]
            for idx in qty_changed_idx:
                changes_records.append((
                    df.at[idx, 'data_id'], '实际数量',
                    df.at[idx, '_hist_snap'], cur_qty.at[idx]
                ))
                self.last_audit_changes.append({
                    'data_id': df.at[idx, 'data_id'], 'field': '实际数量',
                    'workshop': df.at[idx, '车间'] if '车间' in df.columns else None,
                    'material_name': df.at[idx, '物料名称'] if '物料名称' in df.columns else (
                        df.at[idx, '物料描述'] if '物料描述' in df.columns else ''),
                    'old_value': float(df.at[idx, '_hist_snap']) if pd.notna(df.at[idx, '_hist_snap']) else None,
                    'new_value': cur_qty.at[idx],
                })
            note_changed_idx = df.index[note_changed]
            for idx in note_changed_idx:
                changes_records.append((
                    df.at[idx, 'data_id'], '备注原因',
                    df.at[idx, '_hist_note'], cur_note.at[idx]
                ))
                self.last_audit_changes.append({
                    'data_id': df.at[idx, 'data_id'], 'field': '备注原因',
                    'workshop': df.at[idx, '车间'] if '车间' in df.columns else None,
                    'material_name': df.at[idx, '物料名称'] if '物料名称' in df.columns else (
                        df.at[idx, '物料描述'] if '物料描述' in df.columns else ''),
                    'old_value': self._norm_note(df.at[idx, '_hist_note']),
                    'new_value': cur_note.at[idx],
                })
            record_deviation_change_batch(changes_records)
            changed_count = int(changed.sum())
            self.log(f"⚠️ 发现 {changed_count} 条已审核记录的实际数量/备注原因被修改，已强制设为未读并留痕", "warning")
            self.log_signal.emit(f"变动提醒|{changed_count}", "alert")

        # 清理临时历史列
        df = df.drop(columns=['_hist_read', '_hist_fp', '_hist_snap', '_hist_note'], errors='ignore')
        print(f'[DEBUG _restore_read_status] 总行数={len(df)}, 匹配={int(has_status.sum())}, 基线被改={int(changed.sum())}, status_map大小={len(status_map)}')
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

    @staticmethod
    def _find_remark_col(df: pd.DataFrame):
        """探测备注原因列名（不同 SAP 导出可能不同）"""
        candidates = ['备注原因', '备注', '审核备注', '偏差备注', 'remark']
        for c in candidates:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _norm_note(v):
        """把备注值规范化为可比对的字符串；空/NaN/None → ''"""
        if v is None:
            return ''
        if isinstance(v, float) and pd.isna(v):
            return ''
        s = str(v).strip()
        if s.lower() in ('nan', 'none', 'nat', ''):
            return ''
        return s

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

    def _record_post_audit_change(self, data_id: str, old_val, new_val, field: str):
        """记录审核后变动（方案A：实际数量 或 备注原因；带去重避免反复重导刷库）"""
        try:
            try:
                history = get_deviation_history(data_id)
            except Exception:
                history = []
            for h in history:
                if h.get('field') == field and str(h.get('new_value')) == str(new_val):
                    return  # 同一字段同一变更已记录，跳过
            record_deviation_change(data_id, field, old_val, new_val, "审核后数据被修改")
        except Exception as e:
            self.log(f"记录变动历史失败: {e}", "error")

    def mark_changes_as_read(self, changes: list, df: pd.DataFrame):
        """
        把本次弹窗里的变动记录一次性标记为已读，并用当前主表最新值重建 snapshot 基线，
        避免下次重新加载时再次弹窗提醒。
        """
        if not changes:
            return 0
        try:
            from core.read_status import mark_read_batch
            qty_col = self._find_real_qty_col(df)
            note_col = self._find_remark_col(df)
            dids = set()
            snapshot_map = {}
            for c in changes:
                did = str(c.get('data_id', ''))
                if not did or did in dids:
                    continue
                dids.add(did)
                rows = df[df['data_id'].astype(str) == did]
                if rows.empty:
                    snap_qty = None
                    snap_note = ''
                else:
                    row = rows.iloc[0]
                    snap_qty = row.get(qty_col) if qty_col else None
                    snap_note = self._norm_note(row.get(note_col)) if note_col else ''
                snapshot_map[did] = (snap_qty, snap_note)
            mark_read_batch(list(dids), snapshot_map)
            self.last_audit_changes = []  # 当前会话不再重复弹窗
            return len(dids), dids
        except Exception as e:
            self.log(f"批量标记已读失败: {e}", "error")
            return 0, set()

    def _restore_audit_results(self, df: pd.DataFrame) -> pd.DataFrame:
        """从 DB 恢复审核结果（审核结果、AI建议、备注来源），使用向量化赋值替代逐行 iloc。"""
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
            # 把 audit_map 对齐成 Series，只在当前值为空（NaN/空字符串）时回填
            mapped = df['data_id'].map(lambda did: audit_map.get(did, {}).get(key, ''))
            current = df[col].astype(str).replace('nan', '').replace('None', '')
            is_empty = df[col].isna() | (current.str.strip() == '')
            if is_empty.any():
                df.loc[is_empty, col] = mapped[is_empty]
                if key == 'audit_result':
                    restored += int((is_empty & (mapped != '')).sum())

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
            for c in ['净偏差数量', 'net_qty']:
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
        """同会话重新分析时，比对已审核记录的实际数量 与 备注原因 是否变动（方案A）"""
        old_qty = {}
        old_note = {}
        try:
            real_col_old = self._find_real_qty_col(old_df)
            remark_col_old = self._find_remark_col(old_df)
            for _, row in old_df.iterrows():
                if self._is_record_audited(row):
                    did = row['data_id']
                    old_qty[did] = self._safe_qty(row.get(real_col_old))
                    old_note[did] = self._norm_note(row.get(remark_col_old)) if remark_col_old else ''
        except Exception as e:
            self.log(f"构建旧快照失败: {e}", "error")

        real_col_new = self._find_real_qty_col(new_df)
        remark_col_new = self._find_remark_col(new_df)
        new_wk = {}  # did -> 车间
        new_name = {}  # did -> 物料名称
        changes = []  # (did, old_val, new_val, field)
        self.last_audit_changes = []  # 重置
        try:
            for _, row in new_df.iterrows():
                if self._is_record_audited(row):
                    did = row['data_id']
                    new_wk[did] = row.get('车间')
                    new_name[did] = row.get('物料名称') or row.get('物料描述') or ''
                    if did in old_qty:
                        old_q = old_qty[did]
                        new_q = self._safe_qty(row.get(real_col_new))
                        if old_q is not None and new_q is not None and abs(old_q - new_q) >= 1e-6:
                            changes.append((did, old_q, new_q, '实际数量'))
                    if did in old_note:
                        new_n = self._norm_note(row.get(remark_col_new)) if remark_col_new else ''
                        if old_note[did] != new_n:
                            changes.append((did, old_note[did], new_n, '备注原因'))
        except Exception as e:
            self.log(f"检测变动失败: {e}", "error")

        if changes:
            try:
                for did, old_v, new_v, field in changes:
                    record_deviation_change(did, field, old_v, new_v, "重新分析数据变动")
            except Exception as e:
                self.log(f"记录变动失败: {e}", "error")
            self.log(f"发现 {len(changes)} 条已审核记录的实际数量/备注原因发生变动，已强制设为'未读'", "warning")
            # 把同会话检测到的变更也统一格式存入 last_audit_changes
            for did, old_v, new_v, field in changes:
                self.last_audit_changes.append({
                    'data_id': did, 'field': field,
                    'workshop': new_wk.get(did),
                    'material_name': new_name.get(did) or '',
                    'old_value': old_v, 'new_value': new_v})
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


def snapshot_note_for(df: pd.DataFrame, data_id) -> str:
    """取某 data_id 当前备注原因（用于审核时建立变更检测基线）；找不到返回 ''"""
    col = DataService._find_remark_col(df)
    if col is None or 'data_id' not in df.columns:
        return ''
    try:
        sel = df.loc[df['data_id'] == data_id, col]
        if len(sel) == 0:
            return ''
        return DataService._norm_note(sel.iloc[0])
    except Exception:
        return ''
