# -*- coding: utf-8 -*-
"""隔离区管理控制器（ARC-003 第七刀，v43.203）。

隔离区 读写 / 已读对账 / 失效复核 / 自动移入 相关职责从 MainWindow 切出，
避免 God Object 持续膨胀。

模式：组合式。本控制器持有 MainWindow 引用（self.mw），方法体从 MainWindow
原样搬迁、逻辑零改动（仅 self.→self.mw.）；MainWindow 侧保留同名薄壳转发，
保证外部既有调用签名不变：
  - 工具栏按钮 self.action_btn_auto_q.triggered → self._auto_move_to_quarantine(manual=True)
  - 分析完成 self._scan_expired_quarantine_after_analysis()
  - 上下文菜单 / 偏差告警 dialog → self._set_quarantine(rows, flag)
  - 隔离区 dialog 修库按钮 → self.main_window._repair_quarantine_consistency()

方法清单（8 个）：
  _auto_read_by_rules                    自动已读规则中心
  _reconcile_quarantine_read_status      隔离区已读对账（v43.200）
  _set_quarantine                        手动移入/移出隔离区
  _repair_quarantine_consistency         修复界面标记但库内缺失的孤儿
  _auto_move_to_quarantine               按规则自动移入
  _update_quarantine_badge               角标刷新
  _scan_expired_quarantine_after_analysis 失效扫描入口
  _notify_expired_quarantine             失效弹窗

import 来源说明：原方法体依赖 main_window.py 顶部的 pd / QMessageBox /
toast / core.auto_quarantine / core.quarantine_manager，本模块自行 import
同名对象，行为完全一致。
"""

from typing import Any

import pandas as pd
from PySide6.QtWidgets import QMessageBox

from gui_pyside6.widgets.toast import toast
from core.auto_quarantine import (
    build_all_summary,
    compute_auto_quarantine_ids,
    load_auto_quarantine_config,
)
from core.quarantine_manager import (
    add_quarantine_batch,
    get_quarantined_ids,
    remove_quarantine,
    scan_expired_quarantine,
)


class QuarantineManagerController:
    """隔离区管理控制器（自动已读 / 读写 / 失效复核 / 自动移入）。"""

    def __init__(self, mw: Any):
        self.mw = mw

    # ═══════════════ 自动已读 ═══════════════

    def _auto_read_by_rules(self, df):
        """分析完成后：按「自动已读规则中心」配置，把命中任意启用规则的未读行自动标为已读，
        并逐条规则报告命中数（清晰 toast + 状态栏，解决「自动已读没告诉我」的盲区）。

        判定：多条规则 OR 并存；命中行若已读过则跳过（不重复打扰，数据变动会自动翻回未读）。
        落库：复用与手动标已读同一套 snapshot + mark_read_batch。
        """
        try:
            if df is None or df.empty or '_read' not in df.columns or 'data_id' not in df.columns:
                return
            from core.auto_read_rules import load_auto_read_rules_config, compute_auto_read_mask
            cfg = load_auto_read_rules_config()
            if not cfg.get('enabled', True):
                toast("ℹ️ 自动已读已关闭（规则中心总开关）", "info", parent=self.mw, duration=6000)
                return
            union_mask, per_rule = compute_auto_read_mask(df, cfg)
            unread = (df['_read'] == 0)
            # 隔离区记录由「隔离区已读对账」(_reconcile_quarantine_read_status) 专门管理，
            # 自动已读规则中心绝不触碰隔离区——防止负损隔离记录被误标已读（v43.200 根因修复）
            _q = pd.to_numeric(
                df.get('_quarantined', pd.Series(0, index=df.index)),
                errors='coerce',
            ).fillna(0).astype(int)
            not_quarantined = ~(_q == 1)
            target = union_mask & unread & not_quarantined
            n_auto = int(target.sum())
            n_would = int(union_mask.sum())
            if n_auto == 0:
                if n_would == 0:
                    toast("ℹ️ 本次无符合自动已读规则的行", "info", parent=self.mw, duration=6000)
                else:
                    excluded = int((union_mask & unread & ~not_quarantined).sum())
                    if excluded:
                        toast(
                            f"ℹ️ 符合自动已读规则 {n_would} 条，其中 {excluded} 条在隔离区（按规则不自动已读），其余均已读过",
                            "info", parent=self.mw, duration=6000,
                        )
                    else:
                        toast(f"ℹ️ 符合自动已读规则共 {n_would} 条，均已读过，无需自动已读", "info", parent=self.mw, duration=6000)
                return

            # —— 建立变更检测基线（向量化 dict(zip)，避免逐行 df.loc 的 O(n²)）——
            from core.read_status import mark_read_batch
            qty_col = self.mw.data_service._find_real_qty_col(df)
            note_col = self.mw.data_service._find_remark_col(df)
            yield_col = self.mw.data_service._find_yield_col(df)
            qty_lookup = {str(k): v for k, v in zip(df['data_id'], df[qty_col])} if qty_col else {}
            note_lookup = {str(k): str(v) for k, v in zip(df['data_id'], df[note_col].astype(str))} if note_col else {}
            yield_lookup = {str(k): v for k, v in zip(df['data_id'], df[yield_col])} if yield_col else {}

            dids = [str(x) for x in df.loc[target, 'data_id'].tolist()]
            snapshot_map = {}
            for did in dids:
                q = qty_lookup.get(did)
                n = note_lookup.get(did, '')
                y = yield_lookup.get(did)
                snapshot_map[did] = (
                    self.mw.data_service._safe_qty(q) if qty_col else None,
                    self.mw.data_service._norm_note(n) if note_col else '',
                    self.mw.data_service._safe_qty(y) if yield_col else None,
                )
            if dids:
                mark_read_batch(dids, snapshot_map, read_source='auto')
                df.loc[target, '_read'] = 1
                df.loc[target, '_read_source'] = 'auto'
                self.mw._auto_read_count += n_auto
                self.mw._update_read_counter()

            # —— 逐规则命中数（仅在未读且非隔离区范围内统计，供反馈）——
            parts = []
            for rule, m in per_rule:
                cnt = int((m & unread & not_quarantined).sum())
                if cnt > 0:
                    parts.append("「%s」%d" % (rule.get('name', '未命名'), cnt))

            toast(
                f"✅ 自动已读 {n_auto} 条｜" + "｜".join(parts),
                "success", parent=self.mw, duration=6000,
            )
            self.mw.statusBar().showMessage(
                f"自动已读 {n_auto} 条（" + "；".join(parts)
                + f"）｜符合规则共 {n_would} 条",
                6000,
            )
        except Exception as e:
            print(f"[WARN] 自动已读失败(不影响主流程): {e}", flush=True)

    # ═══════════════ 隔离区已读对账 ═══════════════

    def _reconcile_quarantine_read_status(self, df):
        """分析完成后：按隔离区记录当前偏差，对账其已读状态（v43.200 新功能）。

        隔离区记录由本函数专门管理，与「自动已读规则中心」互斥（规则中心不再碰隔离区）：
        - 已解决（实际≥定额，或实际≤0 已归零）→ 自动标已读（仅当当前未读；已读的手动/自动均不动，保留来源）
        - 仍负损（0<实际<定额）→ 若此前是「自动已读」则翻回未读；手动已读不动（尊重人工判断）

        这样「补投后偏差归零/转正」的隔离记录自动收口为已读，仍负损的重新回到未读待复核。
        偏差口径与 scan_expired_quarantine 的 neg_loss 判定同源（actual vs quota），保证一致。
        落库复用 mark_read_batch / save_read_status_batch，并同步内存 _read / _read_source 供 UI 刷新。
        """
        try:
            if df is None or df.empty or 'data_id' not in df.columns:
                return
            from core.read_status import (load_read_status, save_read_status_batch,
                                         mark_read_batch)
            from core.quarantine_manager import get_quarantined_ids

            uids = get_quarantined_ids()
            if not uids:
                return

            # 实际 / 定额 / 备注 / 产量 列（与 scan_expired_quarantine、_auto_read_by_rules 同源）
            actual_col = self.mw.data_service._find_real_qty_col(df)
            quota_col = None
            for c in ('数量-定额', '定额', '定额数量', '数量 - 定额', 'quota'):
                if c in df.columns:
                    quota_col = c
                    break
            if not actual_col or not quota_col:
                return
            note_col = self.mw.data_service._find_remark_col(df)
            yield_col = self.mw.data_service._find_yield_col(df)

            qty_lookup = {str(k): v for k, v in zip(df['data_id'], df[actual_col])} if actual_col else {}
            note_lookup = {str(k): str(v) for k, v in zip(df['data_id'], df[note_col].astype(str))} if note_col else {}
            yield_lookup = {str(k): v for k, v in zip(df['data_id'], df[yield_col])} if yield_col else {}

            # O(1) 索引：data_id(str) -> row（与 scan_expired_quarantine 一致，防重复 data_id）
            try:
                df_index = df.drop_duplicates(subset='data_id', keep='first').set_index(df['data_id'].astype(str))
            except Exception:
                df_index = None

            cur_map = load_read_status(list(uids))

            auto_read, rolled_back = [], []
            snap_map = {}
            for uid in uids:
                try:
                    uid_s = str(uid)
                    if df_index is not None:
                        try:
                            row = df_index.loc[uid_s]
                        except KeyError:
                            continue
                    else:
                        sub = df[df['data_id'].astype(str) == uid_s]
                        if sub.empty:
                            continue
                        row = sub.iloc[0]
                    actual = self.mw.data_service._safe_qty(row.get(actual_col))
                    quota = self.mw.data_service._safe_qty(row.get(quota_col))
                    if actual is None or quota is None:
                        continue
                    # 与 neg_loss 口径一致：0<实际<定额 仍负损；其余（≥定额/≤0）视为已解决
                    still_neg = (actual > 0) and (actual < quota)
                    cur = cur_map.get(uid_s)  # (is_read, fp, sq, sn, sy, src)
                    is_read = int(cur[0]) if cur else 0
                    src = (cur[5] if cur else '') or ''
                    if not still_neg:
                        # 已解决：当前未读才自动标已读（已读的手动/自动均保留来源）
                        if is_read == 0:
                            auto_read.append(uid_s)
                            q = qty_lookup.get(uid_s)
                            n = note_lookup.get(uid_s, '')
                            y = yield_lookup.get(uid_s)
                            snap_map[uid_s] = (
                                self.mw.data_service._safe_qty(q) if actual_col else None,
                                self.mw.data_service._norm_note(n) if note_col else '',
                                self.mw.data_service._safe_qty(y) if yield_col else None,
                            )
                    else:
                        # 仍负损：仅把「自动已读」翻回未读，手动已读保留
                        if is_read == 1 and src == 'auto':
                            rolled_back.append(uid_s)
                except Exception as _e:
                    print(f"[WARN] 隔离区已读对账单行失败(uid={uid}): {_e}", flush=True)

            if auto_read:
                mark_read_batch(auto_read, snap_map, read_source='auto')
            if rolled_back:
                recs = []
                for d in rolled_back:
                    old_fp = cur_map.get(d, ('', '', '', '', '', ''))[1] or ''
                    recs.append((d, 0, old_fp, None, None, ''))
                save_read_status_batch(recs)

            # 同步内存 _read / _read_source，供 setDataFrame 后 UI 刷新
            if auto_read or rolled_back:
                dids_r = set(auto_read)
                dids_u = set(rolled_back)
                try:
                    if dids_r:
                        mask_r = df['data_id'].astype(str).isin(dids_r)
                        df.loc[mask_r, '_read'] = 1
                        df.loc[mask_r, '_read_source'] = 'auto'
                    if dids_u:
                        mask_u = df['data_id'].astype(str).isin(dids_u)
                        df.loc[mask_u, '_read'] = 0
                        df.loc[mask_u, '_read_source'] = ''
                except Exception as _e:
                    print(f"[WARN] 隔离区已读对账内存同步失败: {_e}", flush=True)

            if auto_read or rolled_back:
                parts = []
                if auto_read:
                    parts.append("已解决自动已读 %d 条" % len(auto_read))
                if rolled_back:
                    parts.append("仍负损翻回未读 %d 条" % len(rolled_back))
                toast("🧊 隔离区已读对账：" + "｜".join(parts), "success", parent=self.mw, duration=6000)
                self.mw.statusBar().showMessage("隔离区已读对账：" + "；".join(parts), 6000)
                if auto_read:
                    self.mw._auto_read_count += len(auto_read)
                    self.mw._update_read_counter()
        except Exception as e:
            print(f"[WARN] 隔离区已读对账失败(不影响主流程): {e}", flush=True)

    # ═══════════════ 手动移入/移出 ═══════════════

    def _set_quarantine(self, rows, flag: bool):
        """右键菜单：将选中行移入/移出隔离区，并同步主表与卡片"""
        df = self.mw.view_model.df
        if df is None or 'data_id' not in df.columns:
            return
        ids = set()
        for r in rows:
            if r >= len(df):
                continue
            uid = df.iloc[r].get('data_id')
            if uid:
                ids.add(str(uid))
        if not ids:
            return
        if flag:
            from gui_pyside6.main_window import _ask_quarantine_reason
            reason = _ask_quarantine_reason(self.mw, "移入隔离区")
            if reason is None:
                return
            basis = "手动:" + (reason.strip() if reason.strip() else "手动隔离")
            add_quarantine_batch([(uid, reason, basis) for uid in ids])
        else:
            for uid in ids:
                remove_quarantine(uid)
        df.loc[df['data_id'].isin(ids), '_quarantined'] = 1 if flag else 0
        self.mw.view_model.df = df
        if self.mw.source_model:
            # 就地更新隔离标记，不整表 setDataFrame → 保留滚动/排序/选中/筛选视图
            self.mw.source_model.mark_quarantine(ids, flag)
            if hasattr(self.mw, '_apply_column_visibility_by_name'):
                self.mw._apply_column_visibility_by_name()
        if hasattr(self.mw, 'stats_cards') and self.mw.stats_cards is not None:
            self.mw.stats_cards.refresh(df)
        toast(f"{'⚠️ 已移入隔离区' if flag else '↩ 已取消隔离'} {len(ids)} 条", parent=self.mw)

    # ═══════════════ 修复一致性 ═══════════════

    def _repair_quarantine_consistency(self, silent=False):
        """修复隔离区一致性：把界面中标记隔离(_quarantined==1)但 SQLite 库内缺失的行补写进库。

        救回因旧版本写库未落盘、或数据重导后复合主键漂移造成的「内存孤儿」记录——
        否则重载数据后这些行因水合读不到库而消失，且永远进不了基于库的统计/失效复核。
        返回修复条数。
        """
        df = self.mw.view_model.df
        if df is None or '_quarantined' not in df.columns or 'data_id' not in df.columns:
            return 0
        try:
            qids = get_quarantined_ids()
        except Exception as e:
            self.mw.statusBar().showMessage(f"修复隔离区一致性失败: {e}")
            return 0
        mask = pd.to_numeric(df['_quarantined'], errors='coerce').fillna(0).astype(int) == 1
        orphan_ids = []
        for d in df.loc[mask, 'data_id']:
            s = str(d)
            if s in qids or s in ('', 'nan', 'None') or not pd.notna(d):
                continue
            orphan_ids.append(s)
        if not orphan_ids:
            if not silent:
                toast("隔离区一致性正常，无需修复", parent=self.mw)
            return 0
        items = [(uid, "自动修复:界面标记隔离但库内缺失", "手动:自动修复") for uid in orphan_ids]
        try:
            add_quarantine_batch(items)
        except Exception as e:
            self.mw.statusBar().showMessage(f"修复隔离区一致性写库失败: {e}")
            return 0
        msg = f"🔧 已修复隔离区一致性，补写 {len(orphan_ids)} 条到库"
        self.mw.statusBar().showMessage(msg)
        if not silent:
            toast(msg, parent=self.mw)
        return len(orphan_ids)

    # ═══════════════ 自动移入 ═══════════════

    def _auto_move_to_quarantine(self, manual=False):
        """按 config/auto_quarantine_config.json 配置把符合条件的记录移入隔离区。
        配置项：关键词 / 是否限定包材 / 是否排除替代料 / 是否要求负损。
        manual=True 来自工具栏手动按钮（弹窗反馈）；False 为分析完成后静默执行。"""
        cfg = load_auto_quarantine_config()
        if not cfg.get("enabled", True):
            if manual:
                QMessageBox.information(
                    self.mw, "自动整理隔离区",
                    "自动隔离已关闭（配置 enabled=false），可在工具栏「⚙ 规则」中开启。")
            return
        df = self.mw.view_model.df
        if df is None or 'data_id' not in df.columns:
            if manual:
                QMessageBox.information(self.mw, "自动整理隔离区", "暂无数据，无法执行。")
            return
        matched = compute_auto_quarantine_ids(df, cfg)
        if not matched:
            if manual:
                QMessageBox.information(
                    self.mw, "自动整理隔离区",
                    "没有符合规则的记录（%s）。" % build_all_summary(cfg))
            return
        # 仅对「尚未在隔离区」的新记录执行，避免重复打扰 / 覆盖用户手动取消隔离的行
        already = set()
        if '_quarantined' in df.columns:
            already = set(df.loc[df['_quarantined'] == 1, 'data_id'].astype(str))
        new_ids = set(matched) - already
        if not new_ids:
            if manual:
                QMessageBox.information(
                    self.mw, "自动整理隔离区",
                    f"符合规则的 {len(matched)} 条均已在隔离区，无需重复移入。")
            return
        # 批量写入 SQLite：单事务 executemany，替代逐行 connect/commit/close（12K 行下卡死的根因之一）
        from core.quarantine_manager import add_quarantine_batch
        # basis 用自动规则 reason 文本（含「自动规则」标识），供失效复核重跑规则判定
        add_quarantine_batch([(uid, matched[uid], matched[uid]) for uid in new_ids])
        df.loc[df['data_id'].isin(new_ids), '_quarantined'] = 1
        self.mw.view_model.df = df
        if self.mw.source_model:
            self.mw.source_model.setDataFrame(df)
            if hasattr(self.mw, '_apply_column_visibility_by_name'):
                self.mw._apply_column_visibility_by_name()
        self.mw.stats_cards.refresh(df)
        msg = f"🧹 自动移入隔离区 {len(new_ids)} 条（{build_all_summary(cfg)}）"
        toast(msg, parent=self.mw)
        if manual:
            QMessageBox.information(self.mw, "自动整理隔离区", msg)

    # ═══════════════ 角标 ═══════════════

    def _update_quarantine_badge(self, expired_list):
        """更新隔离区按钮角标：显示当前失效记录数。无失效则去掉角标。"""
        if not hasattr(self.mw, 'action_btn_quarantine'):
            return
        n = len(expired_list) if expired_list else 0
        if n > 0:
            self.mw.action_btn_quarantine.setText(f"⚠️ 隔离区 ({n}失效)")
            self.mw.action_btn_quarantine.setToolTip(
                f"隔离区：{n} 条记录的入区原因已失效（如负损已补投相符），点击查看")
        else:
            self.mw.action_btn_quarantine.setText("⚠️ 隔离区")
            self.mw.action_btn_quarantine.setToolTip("隔离区：查看/管理疑难记录")

    # ═══════════════ 失效扫描/弹窗 ═══════════════

    def _scan_expired_quarantine_after_analysis(self):
        """分析完成后静默扫描隔离区失效。仅当「新增」失效记录出现时才弹窗告知。"""
        df = self.mw.view_model.df
        if df is None or 'data_id' not in df.columns:
            return
        cfg = load_auto_quarantine_config()
        expired = scan_expired_quarantine(df, cfg)
        # 缓存当前失效集，供隔离区弹窗与角标复用
        self.mw._expired_q_cache = {r['uid']: r for r in expired}
        self._update_quarantine_badge(expired)
        # 仅对新出现的失效 uid 弹窗（避免每次分析重复打扰）
        notified = getattr(self.mw, '_expired_q_notified', set())
        new_uids = [r['uid'] for r in expired if r['uid'] not in notified]
        if new_uids:
            notified.update(new_uids)
            self.mw._expired_q_notified = notified
            self._notify_expired_quarantine(new_uids, expired)

    def _notify_expired_quarantine(self, new_uids, expired_all):
        """弹窗告知失效记录（仅列出本次新增的）。"""
        df = self.mw.view_model.df
        # 用 data_id → 行的索引，避免每条都全表扫描
        _idx = {}
        if df is not None and "data_id" in df.columns:
            try:
                _idx = dict(zip(df["data_id"].astype(str), range(len(df))))
            except Exception:
                pass

        detail_lines = []
        for r in expired_all:
            if r['uid'] not in new_uids:
                continue
            actual = r.get('actual')
            quota = r.get('quota')
            aq = ""
            if actual is not None and quota is not None:
                aq = f"（实际={actual:g}，定额={quota:g}）"
            # 用物料编码+物料名称替代裸 data_id（uid 格式：日期|流程订单|物料编码）
            label = r['uid']
            row_idx = _idx.get(r['uid'])
            if row_idx is not None:
                row = df.iloc[row_idx]
                mat_code = str(row.get("物料编码", "") or "").strip()
                mat_name = str(row.get("物料名称", "") or row.get("物料描述", "") or "").strip()
                if mat_code:
                    label = mat_code
                    if mat_name:
                        label = f"{mat_code}  {mat_name}"
            detail_lines.append(f"• {label}：{r['detail']}{aq}")
        if not detail_lines:
            return
        msg = ("以下隔离区记录的「入区原因已失效」，建议复核并移出隔离区：\n\n"
               + "\n".join(detail_lines)
               + "\n\n可在「⚠️ 隔离区」弹窗的「失效复核」页一键移出。")
        QMessageBox.information(self.mw, "隔离区失效复核", msg)
