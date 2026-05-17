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
                return cfg.get("ai.use_mock_ai", False)
            except Exception:
                pass
        return False

    def _get_mock_result(self, text, dev_rate):
        if not text or str(text).strip() == "":
            if abs(dev_rate) < 0.05:
                return {"result": "合格", "suggestion": "小偏差(5%以内)，可接受，无需特别说明"}
            elif dev_rate > 0:
                return {"result": "需补备注", "suggestion": f"超耗{dev_rate*100:.1f}%，建议检查BOM用量或损耗率"}
            else:
                return {"result": "需补备注", "suggestion": f"少耗{abs(dev_rate)*100:.1f}%，建议核实实际用量"}
        remark_str = str(text).strip()
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
        except requests.Timeout:
            raise TimeoutError("AI 服务响应超时（10秒）")
        except requests.ConnectionError:
            raise ConnectionError("无法连接到 AI 服务，请检查网络")
        except Exception as e:
            raise RuntimeError(f"AI 服务异常：{str(e)}")
