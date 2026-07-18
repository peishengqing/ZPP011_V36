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

    def __init__(self, input_file, alt_pairs, start_date, end_date, material_search, dev_rate_threshold=1.0):
        super().__init__()
        self.input_file = input_file
        self.alt_pairs = alt_pairs
        self.start_date = start_date
        self.end_date = end_date
        self.material_search = material_search
        self.dev_rate_threshold = dev_rate_threshold
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
                ai = row.get('AI建议', '')
                ns = row.get('备注来源', '')
                fp = row.get('fingerprint', '')
                # 只保存有内容的记录
                if ar or ai or ns:
                    records.append({
                        'data_id': str(did),
                        'audit_result': str(ar) if ar else '',
                        'ai_suggestion': str(ai) if ai else '',
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

            # 确保必要的列存在
            for col in ['AI建议', 'audit_result', '备注来源']:
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

            # ── 第一轮：本地分类（瞬间完成）──
            ai_queue = []  # [(idx, context, dev_rate)] 需要调用 AI 的行

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
                    self.audit_data.at[idx, 'AI建议'] = ''
                elif remark:
                    if len(remark) < 5:
                        self.audit_data.at[idx, 'audit_result'] = '需改进'
                        self.audit_data.at[idx, '备注来源'] = '人工填写'
                    else:
                        self.audit_data.at[idx, 'audit_result'] = '合格'
                        self.audit_data.at[idx, '备注来源'] = '人工填写'
                        self.audit_data.at[idx, 'AI建议'] = ''
                else:
                    abs_rate = abs(dev_rate)
                    if abs_rate < 5:
                        self.audit_data.at[idx, 'audit_result'] = '合格'
                    elif abs_rate < 10:
                        self.audit_data.at[idx, 'audit_result'] = '需关注'
                    else:
                        self.audit_data.at[idx, 'audit_result'] = '需补备注'
                    self.audit_data.at[idx, '备注来源'] = 'AI审核'

                # 收集需要 AI 建议的行
                current_result = self.audit_data.at[idx, 'audit_result']
                if not remark or current_result == '需改进':
                    context = {
                        "remark": remark,
                        "物料编码": str(row.get("物料编码", "")),
                        "物料描述": str(row.get("物料描述", "") or row.get("物料名称", "")),
                        "物料大类": str(row.get("物料大类", "") or row.get("物料类型", "") or row.get("组件物料类型描述", "")),
                        "工厂": str(row.get("工厂", "") or row.get("工厂名称", "")),
                        "车间": str(row.get("车间", "")),
                        "流程订单": str(row.get("流程订单", "") or row.get("生产订单", "")),
                        "偏差金额": float(row.get("偏差金额", 0) or row.get("总偏差金额(含税)", 0) or 0),
                        "偏差数量": float(row.get("偏差数量", 0) or 0),
                        "dev_rate": dev_rate,
                    }
                    ai_queue.append((idx, context, dev_rate))
                else:
                    self.audit_data.at[idx, 'AI建议'] = ''

            local_done = total - len(ai_queue)
            self.log.emit(f"本地分类完成: {local_done} 条，待 AI 生成建议: {len(ai_queue)} 条")

            # ── 第二轮：批量 AI 调用 ──
            BATCH_SIZE = 15
            ai_total = len(ai_queue)

            if ai_total == 0:
                self.progress.emit(total, total)
                self.log.emit("全部记录已本地分类完成，无需调用 AI")
            else:
                ai_processed = 0
                self.progress.emit(0, ai_total)

                for batch_start in range(0, ai_total, BATCH_SIZE):
                    if self._cancel.is_set():
                        break

                    batch_end = min(batch_start + BATCH_SIZE, ai_total)
                    batch_items = []
                    batch_idxs = []
                    for i in range(batch_start, batch_end):
                        idx, ctx, dr = ai_queue[i]
                        batch_items.append({"context": ctx, "dev_rate": dr})
                        batch_idxs.append(idx)

                self.log.emit(f"AI批量审核: {ai_processed}/{ai_total} (本轮 {len(batch_items)} 条)")
                try:
                    results = self.ai_client.audit_batch(batch_items)
                except Exception as e:
                    # 批量失败 → 直接用 Mock 降级，不再逐条调 API（浪费时间）
                    self.log.emit(f"批量调用失败({str(e)[:60]})，降级 Mock")
                    results = []
                    for item in batch_items:
                        dr = item["dev_rate"]
                        abs_r = abs(dr)
                        if abs_r >= 30:
                            results.append({"result": "需补备注", "suggestion": "严重超耗，请检查工艺或定额"})
                        elif abs_r >= 10:
                            results.append({"result": "需补备注", "suggestion": "偏差较大，建议核查替代料或录入错误"})
                        elif abs_r >= 5:
                            results.append({"result": "需关注", "suggestion": "偏差需关注，请确认合理性"})
                        else:
                            results.append({"result": "合格", "suggestion": "偏差在正常范围内"})

                for j, (idx, result) in enumerate(zip(batch_idxs, results)):
                    if isinstance(result, dict):
                        self.audit_data.at[idx, 'AI建议'] = result.get('suggestion', '')
                    else:
                        self.audit_data.at[idx, 'AI建议'] = str(result)

                ai_processed = batch_end
                self.progress.emit(ai_processed, ai_total)
                self.log.emit(f"AI审核进度: {ai_processed}/{ai_total}")

            if not self._cancel.is_set():
                if 'audit_result' in self.audit_data.columns or '审核结果' in self.audit_data.columns:
                    self._save_audit_results()
                self.log.emit("AI审核完成")
                self.finished.emit(self.audit_data)
            else:
                self.log.emit("AI审核已取消")
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
