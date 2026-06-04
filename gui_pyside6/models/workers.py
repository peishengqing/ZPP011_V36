# -*- coding: utf-8 -*-
"""
后台工作线程（分析、AI 审核等）
裴哥 | 2026-06-04
"""

import os
import traceback
from typing import List, Optional, Dict, Any
import pandas as pd

from PySide6.QtCore import QThread, Signal

from analysis.analyzer import do_analysis_v2
from core.rule_engine import RuleEngine
from core.ai_client import AIClient


def _import_do_analysis():
    from analysis.analyzer import do_analysis_v2
    return do_analysis_v2


class AnalysisWorker(QThread):
    """
    分析工作线程
    信号:
        progress(percent, step_name)
        finished(output_path)
        error(msg)
        log(msg)
    """
    progress = Signal(int, str)   # percent, step_name
    finished = Signal(str)         # output_path
    error    = Signal(str)
    log      = Signal(str)

    def __init__(self,
                 input_file: str,
                 alt_pairs: List[list],
                 start_date: Optional[str] = None,
                 end_date: Optional[str] = None,
                 material_search: Optional[str] = None,
                 output_dir: Optional[str] = None):
        super().__init__()
        self.input_file      = input_file
        self.alt_pairs       = alt_pairs
        self.start_date      = start_date
        self.end_date        = end_date
        self.material_search  = material_search
        self.output_dir      = output_dir if output_dir is not None else os.path.dirname(input_file)
        self._cancel         = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            do_analysis_v2 = _import_do_analysis()

            def progress_cb(step_idx: int, step_name: str, percent: float):
                if self._cancel:
                    raise InterruptedError("用户取消")
                self.progress.emit(int(percent), step_name)
                self.log.emit(f"[分析] {step_name} {percent:.0f}%")

            output_path = do_analysis_v2(
                input_file       = self.input_file,
                output_dir       = self.output_dir,
                alt_pairs        = self.alt_pairs,
                progress_callback = progress_cb,
                cancel_check     = lambda: self._cancel,
                start_date       = self.start_date,
                end_date         = self.end_date,
                material_search  = self.material_search,
                output_path      = None,
            )
            if self._cancel:
                return
            self.finished.emit(output_path)

        except InterruptedError:
            self.error.emit("分析已取消")
        except Exception as e:
            self.error.emit(f"分析失败：{e}\n{traceback.format_exc()}")


class AIAuditWorker(QThread):
    """
    AI 审核工作线程
    完全迁移自 analysis_events.py 中的 _run_ai_audit 逻辑
    """
    progress = Signal(int, int)      # current, total
    finished = Signal(pd.DataFrame)  # 返回更新后的 DataFrame
    error    = Signal(str)
    log      = Signal(str)

    def __init__(self,
                 audit_data: pd.DataFrame,
                 rule_engine: RuleEngine,
                 ai_client: AIClient):
        super().__init__()
        # 深拷贝，避免跨线程修改原始数据
        self.audit_data   = audit_data.copy() if audit_data is not None else pd.DataFrame()
        self.rule_engine  = rule_engine
        self.ai_client    = ai_client
        self._cancel      = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            total = len(self.audit_data)
            updated = 0

            # 确保必要的列存在
            for col in ['AI建议', 'audit_result', '备注原因', '备注来源']:
                if col not in self.audit_data.columns:
                    self.audit_data[col] = ''

            for idx, row in self.audit_data.iterrows():
                if self._cancel:
                    break

                # 当前备注内容
                remark = str(row.get('备注原因', '')).strip()
                # 偏差率
                dev_rate = row.get('偏差率(%)', 0)
                if pd.isna(dev_rate):
                    dev_rate = 0
                try:
                    dev_rate = float(str(dev_rate).replace('%', ''))
                except (ValueError, TypeError):
                    dev_rate = 0.0

                # 1. 规则引擎评估（决定是否需要 AI 建议）
                should_ai = True
                if self.rule_engine:
                    try:
                        should_ai = self.rule_engine.should_ai_audit(dev_rate, remark)
                    except Exception:
                        pass
                if not should_ai:
                    # 如果已有备注且偏差率不高，标记为合格
                    if remark:
                        self.audit_data.at[idx, 'audit_result'] = '合格'
                        self.audit_data.at[idx, '备注来源']   = '已有备注'
                    continue

                # 2. 调用 AI 客户端生成建议
                ai_suggestion = ''
                try:
                    if self.ai_client:
                        ai_suggestion = self.ai_client.get_suggestion(row.to_dict())
                    else:
                        # mock 模式
                        ai_suggestion = self._mock_suggestion(remark, dev_rate)
                except Exception as e:
                    self.log.emit(f"第{idx}行 AI 调用失败：{e}，使用规则生成")
                    ai_suggestion = self._mock_suggestion(remark, dev_rate)

                # 3. 根据备注和偏差率更新审核结果
                if remark:
                    # 已有备注，根据备注内容智能判断
                    if '替代料' in remark:
                        audit_result = '合格（替代料）'
                        note_source  = '替代料'
                    elif '系统无定额' in remark:
                        audit_result = '合格（系统无定额）'
                        note_source  = '系统无定额'
                    elif '已核实' in remark or '确认' in remark:
                        audit_result = '合格'
                        note_source  = '人工填写'
                    else:
                        audit_result = '需关注'
                        note_source  = '人工填写'
                else:
                    # 无备注，根据偏差率给建议
                    if abs(dev_rate) >= 30:
                        audit_result = '需补备注（严重）'
                        note_source  = 'AI审核'
                    elif abs(dev_rate) >= 10:
                        audit_result = '需补备注'
                        note_source  = 'AI审核'
                    else:
                        audit_result = '需关注'
                        note_source  = 'AI审核'

                # 4. 更新 DataFrame
                self.audit_data.at[idx, 'AI建议']     = ai_suggestion
                self.audit_data.at[idx, 'audit_result'] = audit_result
                self.audit_data.at[idx, '备注来源']    = note_source

                updated += 1
                if updated % 10 == 0:
                    self.progress.emit(updated, total)
                    self.log.emit(f"AI 审核中 {updated}/{total}")

            # 收尾进度
            if total > 0:
                self.progress.emit(total, total)
            # 发送完成信号
            self.finished.emit(self.audit_data)

        except Exception as e:
            self.error.emit(f"AI 审核失败：{e}\n{traceback.format_exc()}")

    @staticmethod
    def _mock_suggestion(remark_str: str, dev_rate: float) -> str:
        """降级：根据规则生成简单建议（与 ai_client._get_mock_result 逻辑一致）"""
        if remark_str in ('nan', 'NaN', 'None', 'none', ''):
            abs_rate = abs(dev_rate)
            if abs_rate < 5:
                return f"小偏差({abs_rate:.1f}%)，可接受"
            elif abs_rate < 10:
                return f"偏差{abs_rate:.1f}%，建议确认原因"
            else:
                if dev_rate > 0:
                    return f"超耗{abs_rate:.1f}%，建议检查BOM用量"
                else:
                    return f"少耗{abs_rate:.1f}%，建议核实用量"
        # 关键词判断
        if any(kw in remark_str for kw in ["超耗", "少耗", "损耗", "替代", "变更"]):
            return "备注清晰，关键词匹配"
        if len(remark_str) < 5:
            return "备注过短，建议补充详细原因"
        return "建议明确偏差原因（如超耗/少耗/替代/变更）"
