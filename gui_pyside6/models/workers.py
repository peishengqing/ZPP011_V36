# -*- coding: utf-8 -*-
"""
后台工作线程（分析、AI审核）
"""
import threading
import traceback
import pandas as pd
from PySide6.QtCore import QThread, Signal

from analysis.analyzer import do_analysis_v2
from core.rule_engine import RuleEngine
from core.ai_client import AIClient
from core.config_manager import ConfigManager
from core.snapshot import compute_unfinished
import core.audit_evidence as ae
import core.attribution as attribution
from core.read_status import DB_PATH


class AnalysisWorker(QThread):
    progress = Signal(int, str)  # percent, step_name
    finished = Signal(pd.DataFrame)  # df (不自动保存文件)
    error = Signal(str)
    log = Signal(str)           # 日志信号

    def __init__(self, input_file, alt_pairs, start_date, end_date, material_search,
                 dev_rate_threshold=1.0, data_service=None, previous_df=None, input_df=None,
                 dyn_thresh=None):
        super().__init__()
        self.input_file = input_file
        self.alt_pairs = alt_pairs
        self.start_date = start_date
        self.end_date = end_date
        self.material_search = material_search
        self.dev_rate_threshold = dev_rate_threshold
        self.dyn_thresh = dyn_thresh
        # 后台预处理所需（DataSerivce 为 QObject，跨线程仅发信号，逻辑可安全在 worker 跑）
        self.data_service = data_service
        self._previous_df = previous_df
        self._input_df = input_df
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            self.log.emit("开始分析...")
            # 读取替代料净偏差抵消配置
            _cfg = ConfigManager()
            _enable_net_offset = _cfg.get_net_offset_enabled()
            self.log.emit(f"替代料净偏差抵消: {'开启' if _enable_net_offset else '关闭'}")

            def progress_cb(step_idx, step_name, percent):
                if self._cancel.is_set():
                    raise InterruptedError("用户取消")
                self.progress.emit(percent, step_name)
                self.log.emit(f"{step_name} ({percent}%)")

            df = do_analysis_v2(
                input_file=self.input_file,
                output_dir=None,
                alt_pairs=self.alt_pairs,
                progress_callback=progress_cb,
                cancel_check=lambda: self._cancel.is_set(),
                start_date=self.start_date,
                end_date=self.end_date,
                material_search=self.material_search,
                output_path=None,
                enable_net_offset=_enable_net_offset,
                return_dataframe=True,  # 返回DataFrame，不自动保存文件
                dev_rate_threshold=self.dev_rate_threshold,
                input_df=self._input_df,  # reuse cached DataFrame from file selection
                dyn_thresh=self.dyn_thresh,
            )

            if self._cancel.is_set():
                self.log.emit("分析已取消")
                return  # 优雅退出，不发射错误信号

            self.log.emit(f"分析完成，共 {len(df)} 行")
            self.finished.emit(df)
        except InterruptedError:
            # 用户取消，优雅退出
            self.log.emit("分析已取消")
        except Exception as e:
            # 1. 打印详细堆栈到控制台
            traceback.print_exc()
            # 2. 发射错误信号（包含堆栈信息）
            self.log.emit(f"错误: {str(e)}")
            self.error.emit(f"分析失败: {str(e)}\n{traceback.format_exc()}")


class AIAuditWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(pd.DataFrame)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, audit_data: pd.DataFrame, rule_engine: RuleEngine, ai_client: AIClient):
        super().__init__()
        self.audit_data = audit_data.copy()
        self.rule_engine = rule_engine
        self.ai_client = ai_client
        self._cancel = threading.Event()
        self._audit_records = []          # F1：每条审核的判定+证据，落库用

    def cancel(self):
        self._cancel.set()

    def _save_audit_results(self):
        """将审核结果批量保存到 SQLite。

        三段落地相互独立，任何一段失败都不影响其余：
          1) 遗留 audit_result 表写入（历史兼容）
          2) F1 证据 + F2 归因建议落地（核心，必须尽量落库）
          3) 历史频率库同步
        """
        # 1) 遗留：审核结果写 audit_result 表（失败不影响 F1/F2 落地）
        try:
            from core.read_status import save_audit_results_batch
            # 确定列名
            result_col = '审核结果' if '审核结果' in self.audit_data.columns else 'audit_result'
            records = []
            for _, row in self.audit_data.iterrows():
                did = row.get('data_id', '')
                if not did:
                    continue
                ar = row.get(result_col, '')
                ns = row.get('备注来源', '')
                fp = row.get('fingerprint', '')
                # 只保存有内容的记录（AI建议已停用，不再写入 ai_suggestion）
                if ar or ns:
                    records.append({
                        'data_id': str(did),
                        'audit_result': str(ar) if ar else '',
                        'ai_suggestion': '',
                        'note_source': str(ns) if ns else '',
                        'fingerprint': str(fp) if fp else '',
                    })
            if records:
                save_audit_results_batch(records)
                self.log.emit(f"已保存 {len(records)} 条审核结果到数据库")
        except Exception as e:
            self.log.emit(f"保存遗留审核结果失败（不影响证据落地）: {e}")

        # 2) F1 证据 + F2 归因建议落地（独立，不受遗留写入影响）
        if self._audit_records:
            rv = ae._app_version()
            mv = ae.DEFAULT_MODEL_VERSION
            for rec in self._audit_records:
                try:
                    aid = ae.write_audit(
                        data_id=rec["data_id"], verdict=rec["verdict"],
                        confidence=rec["confidence"], needs_human=rec["needs_human"],
                        suggestion=rec["suggestion"], evidence_list=rec["evidence"],
                        rule_version=rv, model_version=mv)
                    att = rec.get("attribution") or {}
                    ae.write_suggestion(
                        aid, rec["data_id"], rec.get("branch", ""),
                        att.get("root_cause", ""), att.get("action", ""),
                        att.get("precedent", []), att.get("candidates", []),
                        rv, mv)
                except Exception as e:
                    self.log.emit(f"写入审核证据失败（跳过该条）: {e}")
            self.log.emit(f"已写入 {len(self._audit_records)} 条审核证据+归因建议到 audit_evidence/audit_report/audit_suggestion")

        # 3) 同步更新历史频率库
        try:
            from core.history_freq import batch_update
            batch_update(self.audit_data)
        except Exception:
            pass  # 频率更新失败不影响主流程

    # ------------------------------------------------------------------
    # F1 证据采集
    # ------------------------------------------------------------------
    def _ev(self, etype, content, rv, mv):
        return {"evidence_type": etype, "content": content,
                "rule_version": rv, "model_version": mv}

    def _record_decision(self, idx, row, dev_rate, remark, did, is_unfinished, rv, mv):
        """按现有本地分级逻辑推导 verdict/confidence/needs_human，并采集证据链 + F2 归因建议。"""
        result_col = '审核结果' if '审核结果' in self.audit_data.columns else 'audit_result'
        kw = ['替代料', '系统无定额', '已核实']
        hit = [k for k in kw if k in remark] if remark else []
        evidence = []

        if is_unfinished:
            branch = "unfinished"
            verdict, confidence, needs_human = "不确定(数据未完结)", "低", True
            self.audit_data.at[idx, result_col] = verdict
            self.audit_data.at[idx, '备注来源'] = 'AI审核'
            evidence.append(self._ev(ae.EV_UNFINISHED,
                                    {"status": "未完结", "suggestion": "暂缓判定"}, rv, mv))
        elif remark and any(k in remark for k in kw):
            branch = "keyword_hit"
            verdict, confidence, needs_human = "合格", "高", False
            self.audit_data.at[idx, result_col] = verdict
            self.audit_data.at[idx, '备注来源'] = remark
            evidence.append(self._ev(ae.EV_RULE_HIT,
                                    {"branch": "keyword_hit", "keyword": hit}, rv, mv))
        elif remark:
            if len(remark) < 5:
                branch = "remark_short"
                verdict, confidence, needs_human = "需改进", "中", True
            else:
                branch = "remark_ok"
                verdict, confidence, needs_human = "合格", "中", False
            self.audit_data.at[idx, result_col] = verdict
            self.audit_data.at[idx, '备注来源'] = '人工填写'
            evidence.append(self._ev(ae.EV_RULE_HIT,
                                    {"branch": "remark_present", "remark_len": len(remark)}, rv, mv))
        else:
            abs_rate = abs(dev_rate)
            if abs_rate < 5:
                branch = "dev_low"
                verdict, confidence, needs_human = "合格", "中", False
            elif abs_rate < 10:
                branch = "dev_mid"
                verdict, confidence, needs_human = "需关注", "中", False
            else:
                branch = "dev_high"
                verdict, confidence, needs_human = "需补备注", "低", True
            self.audit_data.at[idx, result_col] = verdict
            self.audit_data.at[idx, '备注来源'] = 'AI审核'
            evidence.append(self._ev(ae.EV_RULE_HIT,
                                    {"branch": "dev_rate_band", "abs_rate": round(abs_rate, 2)}, rv, mv))

        # 公共证据：偏差率 + 备注覆盖
        evidence.append(self._ev(ae.EV_DEV_RATE, {
            "dev_rate": round(dev_rate, 2),
            "direction": "超耗" if dev_rate > 0 else ("少耗" if dev_rate < 0 else "持平"),
        }, rv, mv))
        evidence.append(self._ev(ae.EV_REMARK, {
            "remark_len": len(remark), "has_remark": bool(remark),
        }, rv, mv))

        # F2 归因建议：规则模板 + 历史检索（best-effort）。仅 needs_human 才把较重的
        # 替代料长链 / 历史相似证据挂到证据链，限制开销。
        mat = str(row.get("物料编码", "")).strip()
        fac = str(row.get("工厂", "")).strip()
        alt_ev = self._alt_chain_evidence(row, rv, mv)
        has_alt = alt_ev is not None
        if has_alt and needs_human:
            evidence.append(alt_ev)
        if needs_human:
            hist = self._history_evidence(row, rv, mv)
            if hist is not None:
                evidence.append(hist)
        att = attribution.build_attribution(
            branch, dev_rate=dev_rate, remark=remark, has_alt_chain=has_alt,
            material=mat, factory=fac,
            keywords=hit if branch == "keyword_hit" else None)
        suggestion = attribution.compact_suggestion(att)

        self._audit_records.append({
            "data_id": str(did), "verdict": verdict, "confidence": confidence,
            "needs_human": needs_human, "suggestion": suggestion,
            "evidence": evidence, "attribution": att, "branch": branch,
        })

    def _alt_chain_evidence(self, row, rv, mv):
        """best-effort：判断物料是否身处替代料长链。失败返回 None。"""
        try:
            import os
            mat = str(row.get("物料编码", "")).strip()
            if not mat:
                return None
            cfg = os.path.join(os.environ.get("APPDATA", ""), "ZPP011", "config", "alt_pairs.json")
            if not os.path.exists(cfg):
                return None
            with open(cfg, "r", encoding="utf-8") as f:
                data = __import__("json").load(f)
            nodes = set()
            if isinstance(data, list):
                for pair in data:
                    if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                        nodes.add(str(pair[0])); nodes.add(str(pair[1]))
            elif isinstance(data, dict):
                for k, v in data.items():
                    nodes.add(str(k))
                    if isinstance(v, (list, tuple, set)):
                        nodes.update(str(x) for x in v)
                    else:
                        nodes.add(str(v))
            if mat in nodes:
                return self._ev(ae.EV_ALT_CHAIN, {"material": mat, "in_alt_chain": True}, rv, mv)
        except Exception:
            pass
        return None

    def _history_evidence(self, row, rv, mv):
        """best-effort：同物料+同厂的历史备注原因 Top3（deviation_history）。失败返回 None。"""
        try:
            import sqlite3
            mat = str(row.get("物料编码", "")).strip()
            fac = str(row.get("工厂", "")).strip()
            if not mat:
                return None
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cur = conn.execute(
                "SELECT 备注原因 FROM deviation_history "
                "WHERE 物料编码=? AND 工厂=? LIMIT 50", (mat, fac))
            from collections import Counter
            cnt = Counter()
            for (r,) in cur.fetchall():
                rs = str(r or "").strip()
                if rs and rs not in ("nan", "None", ""):
                    cnt[rs] += 1
            conn.close()
            top = [{"remark": k, "count": v} for k, v in cnt.most_common(3)]
            if top:
                return self._ev(ae.EV_HISTORY, {"top_remarks": top}, rv, mv)
        except Exception:
            pass
        return None

    def run(self):
        try:
            self.log.emit("AI审核开始...")
            total = len(self.audit_data)
            self.log.emit(f"待审核记录: {total} 条")

            # 确保必要的列存在（AI建议已停用：不再创建/写入该列）
            for col in ['audit_result', '备注来源']:
                if col not in self.audit_data.columns:
                    self.audit_data[col] = ''

            # 备注原因列可能叫 '备注原因' 或 '备注'
            remark_col = None
            for col in ['备注原因', '备注']:
                if col in self.audit_data.columns:
                    remark_col = col
                    break
            if remark_col is None:
                raise ValueError("找不到备注列")

            # F1：未完结集合（分批入库场景下，未完结订单要先标「数据未完结，建议暂缓判定」）
            try:
                unf = compute_unfinished(self.audit_data)
                unfinished_ids = {d.get("data_id") for d in unf.get("details", []) if d.get("data_id")}
            except Exception:
                unfinished_ids = set()
            rv = ae._app_version()
            mv = ae.DEFAULT_MODEL_VERSION

            # 第一轮本地分类只写「审核结果 / 备注来源」；AI建议已停用，不再进入 ai_queue。
            # 同时采集 F1 证据链（verdict/confidence/needs_human/evidence）。

            for idx, row in self.audit_data.iterrows():
                if self._cancel.is_set():
                    break

                dev_rate = self._parse_dev_rate(row)
                remark = str(row.get(remark_col, '')).strip()
                if remark in ('nan', 'None', ''):
                    remark = ''
                did = row.get('data_id', '')
                self._record_decision(idx, row, dev_rate, remark, did, did in unfinished_ids, rv, mv)

            # AI建议已停用：第一轮本地分类完成后直接结束，不再调用 AI、不生成任何建议文案。
            self.progress.emit(total, total)
            self.log.emit(f"本地分类完成: {total} 条（AI建议功能已停用）")

            if not self._cancel.is_set():
                if 'audit_result' in self.audit_data.columns or '审核结果' in self.audit_data.columns:
                    self._save_audit_results()
                self.log.emit("审核完成")
                self.finished.emit(self.audit_data)
            else:
                self.log.emit("审核已取消")
        except Exception as e:
            traceback.print_exc()
            self.log.emit(f"AI审核错误: {str(e)}")
            self.error.emit(f"AI审核失败: {str(e)}\n{traceback.format_exc()}")

    def _parse_dev_rate(self, row):
        """从行数据解析偏差率"""
        for c in ['偏差率', '偏差率(%)']:
            if c in row:
                raw = row[c]
                try:
                    if isinstance(raw, str):
                        return float(raw.replace('%', ''))
                    return float(raw)
                except Exception:
                    pass
        return 0.0


class PreprocessWorker(QThread):
    """后台预处理线程：把 DataService.preprocess_audit_data（含 load_read_status /
    save_snapshot_batch / load_audit_results 重 DB IO）挪出主线程，杜绝 GUI 卡死、
    并避免受 Windows 对后台控制台进程的 CPU 限流影响。

    关键点：run() 内只 emit 一次 finished(df)，绝不在循环里逐行发信号
    （逐行 emit QObject 信号曾把 0.2s 拖成 3+ 分钟）。preprocess_audit_data 内部
    通过 data_service.log_signal 发的少量日志，因 data_service 活着主线程，会走
    QueuedConnection 安全排队到主线程，无需额外转发。
    """
    finished = Signal(pd.DataFrame)
    error = Signal(str)

    def __init__(self, data_service, df, previous_df=None):
        super().__init__()
        self.data_service = data_service
        # 深拷贝，避免与调用方持有的同一 df 实例在跨线程期间产生别名竞争
        # （preprocess_audit_data 内部会对输入 df 做 in-place 赋值，如 _read 列）
        self.df = df.copy(deep=True)
        self.previous_df = previous_df.copy(deep=True) if previous_df is not None else None

    def run(self):
        try:
            result = self.data_service.preprocess_audit_data(self.df, self.previous_df)
            self.finished.emit(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(f"预处理失败: {e}\n{traceback.format_exc()}")
