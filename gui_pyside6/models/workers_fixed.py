# -*- coding: utf-8 -*-
"""
后台工作线程（分析、AI审核）
"""
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

    def __init__(self, input_file, alt_pairs, start_date, end_date, material_search):
        super().__init__()
        self.input_file = input_file
        self.alt_pairs = alt_pairs
        self.start_date = start_date
        self.end_date = end_date
        self.material_search = material_search
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self.log.emit("开始分析...")
            # 读取替代料净偏差抵消配置
            _cfg = ConfigManager()
            _enable_net_offset = _cfg.get_net_offset_enabled()
            self.log.emit(f"替代料净偏差抵消: {'开启' if _enable_net_offset else '关闭'}")

            def progress_cb(step_idx, step_name, percent):
                if self._cancel:
                    raise InterruptedError("用户取消")
                self.progress.emit(percent, step_name)
                self.log.emit(f"{step_name} ({percent}%)")

            df = do_analysis_v2(
                input_file=self.input_file,
                output_dir=None,
                alt_pairs=self.alt_pairs,
                progress_callback=progress_cb,
                cancel_check=lambda: self._cancel,
                start_date=self.start_date,
                end_date=self.end_date,
                material_search=self.material_search,
                output_path=None,
                enable_net_offset=_enable_net_offset,
                return_dataframe=True,  # 不保存文件，直接返回 DataFrame
            )
            if self._cancel:
                return
            self.log.emit(f"分析完成，共 {len(df)} 行")
            self.finished.emit(df)
        except Exception as e:
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
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self.log.emit("AI审核开始...")
            total = len(self.audit_data)
            self.log.emit(f"待审核记录: {total} 条")
            processed = 0
            
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

            for idx, row in self.audit_data.iterrows():
                if self._cancel:
                    break

                # 获取偏差率（支持字符串和数字）
                dev_rate_raw = row.get('偏差率(%)', 0)
                try:
                    if isinstance(dev_rate_raw, str):
                        dev_rate = float(dev_rate_raw.replace('%', ''))
                    else:
                        dev_rate = float(dev_rate_raw)
                except:
                    dev_rate = 0.0
                abs_rate = abs(dev_rate)

                # 获取备注内容
                remark = str(row.get(remark_col, '')).strip()
                if remark in ('nan', 'None', ''):
                    remark = ''

                # ---------- 关键词优先 ----------
                keywords = ['替代料', '系统无定额', '已核实']
                if remark and any(kw in remark for kw in keywords):
                    audit_result = '合格'
                    note_source = remark
                else:
                    if remark:
                        # 有备注但不含关键词，检查长度
                        if len(remark) < 5:
                            audit_result = '需改进'
                            note_source = '人工填写'
                        else:
                            audit_result = '合格'
                            note_source = '人工填写'
                    else:
                        # 备注为空，根据偏差率分级
                        if abs_rate < 5:
                            audit_result = '合格'
                            note_source = 'AI审核'
                        elif 5 <= abs_rate < 10:
                            audit_result = '需关注'
                            note_source = 'AI审核'
                        else:
                            audit_result = '需补备注'
                            note_source = 'AI审核'

                # 生成 AI 建议（如果规则认为需要，否则可留空）
                ai_suggestion = ''
                if not remark:   # 无备注时生成 AI 建议
                    try:
                        # 调用正确的方法：ai_client.audit()
                        ai_result = self.ai_client.audit(remark, dev_rate)
                        if isinstance(ai_result, dict):
                            ai_suggestion = ai_result.get('suggestion', '')
                        else:
                            ai_suggestion = str(ai_result)
                    except Exception as e:
                        # 降级建议
                        if abs_rate >= 30:
                            ai_suggestion = "严重超耗，请检查工艺或定额"
                        elif abs_rate >= 10:
                            ai_suggestion = "偏差较大，建议核查是否存在替代料或录入错误"
                        elif abs_rate >= 5:
                            ai_suggestion = "偏差需关注，请确认合理性"
                # 如果已有备注但长度过短，也可以生成改进建议
                elif audit_result == '需改进':
                    ai_suggestion = "备注过短，请补充详细原因"

                self.audit_data.at[idx, 'AI建议'] = ai_suggestion
                self.audit_data.at[idx, 'audit_result'] = audit_result
                self.audit_data.at[idx, '备注来源'] = note_source

                processed += 1
                if processed % 10 == 0:
                    self.progress.emit(processed, total)
                    self.log.emit(f"AI审核进度: {processed}/{total}")

            if not self._cancel:
                self.log.emit("AI审核完成")
                self.finished.emit(self.audit_data)
            else:
                self.log.emit("AI审核已取消")
        except Exception as e:
            self.log.emit(f"AI审核错误: {str(e)}")
            self.error.emit(f"AI审核失败: {str(e)}\n{traceback.format_exc()}")
