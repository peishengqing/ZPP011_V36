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

    def cancel(self):
        self._cancel.set()

    def _save_audit_results(self):
        """将审核结果批量保存到 SQLite"""
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
            # ── 同步更新历史频率库 ──
            try:
                from core.history_freq import batch_update
                batch_update(self.audit_data)
            except Exception:
                pass  # 频率更新失败不影响主流程
        except Exception as e:
            self.log.emit(f"保存审核结果失败: {e}")

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

            # 第一轮本地分类只写「审核结果 / 备注来源」；AI建议已停用，不再进入 ai_queue。

            for idx, row in self.audit_data.iterrows():
                if self._cancel.is_set():
                    break

                dev_rate = self._parse_dev_rate(row)
                remark = str(row.get(remark_col, '')).strip()
                if remark in ('nan', 'None', ''):
                    remark = ''

                # 关键词优先 → 本地判定
                if remark and any(kw in remark for kw in ['替代料', '系统无定额', '已核实']):
                    self.audit_data.at[idx, 'audit_result'] = '合格'
                    self.audit_data.at[idx, '备注来源'] = remark
                elif remark:
                    if len(remark) < 5:
                        self.audit_data.at[idx, 'audit_result'] = '需改进'
                        self.audit_data.at[idx, '备注来源'] = '人工填写'
                    else:
                        self.audit_data.at[idx, 'audit_result'] = '合格'
                        self.audit_data.at[idx, '备注来源'] = '人工填写'
                else:
                    abs_rate = abs(dev_rate)
                    if abs_rate < 5:
                        self.audit_data.at[idx, 'audit_result'] = '合格'
                    elif abs_rate < 10:
                        self.audit_data.at[idx, 'audit_result'] = '需关注'
                    else:
                        self.audit_data.at[idx, 'audit_result'] = '需补备注'
                    self.audit_data.at[idx, '备注来源'] = 'AI审核'

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
