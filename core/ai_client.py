# -*- coding: utf-8 -*-
# core/ai_client.py
"""AI 客户端封装 - Mock 模式 + 超时熔断 + 异常分类"""
import requests
import logging

logger = logging.getLogger("AIClient")


class AIClient:
    def __init__(self):
        self._config = None

    def _load_config(self):
        if self._config is not None:
            return self._config
        try:
            from core.config_manager import get_config_manager
            self._config = get_config_manager()
        except Exception:
            self._config = None
        return self._config

    def _is_mock_mode(self):
        cfg = self._load_config()
        if cfg:
            try:
                return cfg.get("ai.use_mock_ai", True)
            except Exception:
                pass
        return True  # 默认Mock，确保AI审核始终可用

    def _get_mock_result(self, text, dev_rate):
        if not text or str(text).strip() == "":
            if abs(dev_rate) < 0.05:
                return {"result": "合格", "suggestion": "小偏差(5%以内)，可接受，无需特别说明"}
            elif dev_rate > 0:
                return {"result": "需补备注", "suggestion": f"超耗{dev_rate*100:.1f}%，建议检查BOM用量或损耗率"}
            else:
                return {"result": "需补备注", "suggestion": f"少耗{abs(dev_rate)*100:.1f}%，建议核实实际用量"}
        remark_str = str(text).strip()
        # 跳过 nan/NaN/None 等无效值（之前已在上方处理空文本，此处作为兜底）
        if remark_str in ('nan', 'NaN', 'None', 'none', ''):
            return {"result": "需补备注", "suggestion": "未填写备注，建议填写偏差原因（超耗/少耗/替代/变更）"}
        if len(remark_str) < 5:
            return {"result": "需改进", "suggestion": "备注过短，建议补充详细原因"}
        if any(kw in remark_str for kw in ["超耗", "少耗", "损耗", "替代", "变更"]):
            return {"result": "合格", "suggestion": "备注清晰"}
        return {"result": "需改进", "suggestion": "建议明确偏差原因（如超耗/少耗/替代/变更）"}

    def audit(self, text, dev_rate=0.0):
        """调用 AI 审核，超时10秒熔断"""
        if self._is_mock_mode():
            logger.debug("Mock 模式：使用模拟审核结果")
            return self._get_mock_result(text, dev_rate)

        try:
            response = requests.post(
                "http://localhost:8080/audit",
                json={"text": text, "dev_rate": dev_rate},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"AI服务不可用({e})，自动降级到Mock模式")
            return self._get_mock_result(text, dev_rate)
        except Exception as e:
            logger.warning(f"AI服务异常({e})，自动降级到Mock模式")
            return self._get_mock_result(text, dev_rate)
