# core/rule_engine.py
import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger

logger = get_logger("RuleEngine")


class RuleEngine:
    """轻量规则引擎，从 JSON 加载规则，支持热重载"""

    def __init__(self, rules_path: Optional[Path] = None):
        if rules_path is None:
            rules_path = Path(__file__).parent.parent / "config" / "system" / "rules.json"
        self.rules_path = rules_path
        self.rules: Dict[str, Any] = {}
        
        # Auto-create default rules file if not exists
        if not self.rules_path.exists():
            self.rules_path.parent.mkdir(parents=True, exist_ok=True)
            default_rules = self._get_default_rules()
            with open(self.rules_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(default_rules, f, indent=2, ensure_ascii=False)
            print(f"[RuleEngine] Created default rules file: {self.rules_path}")
        
        self._load()

    def _load(self):
        if not self.rules_path.exists():
            logger.warning(f"规则文件不存在: {self.rules_path}，使用默认规则")
            self.rules = self._get_default_rules()
            return
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                self.rules = json.load(f)
            logger.info(f"规则加载成功: {self.rules_path}")
        except Exception as e:
            logger.error(f"加载规则失败: {e}，使用默认规则")
            self.rules = self._get_default_rules()

    def _get_default_rules(self) -> Dict:
        return {
            "version": "1.0",
            "deviation_rate_bands": [
                {"min": 0, "max": 0.05, "color": "#e8f5e9", "label": "正常", "level": "info"},
                {"min": 0.05, "max": 0.10, "color": "#fff3e0", "label": "关注", "level": "warning"},
                {"min": 0.10, "max": 999, "color": "#ffebee", "label": "异常", "level": "error"}
            ],
            "auto_close": {
                "enabled": True,
                "conditions": [
                    {"field": "审核状态", "operator": "eq", "value": "已审核"},
                    {"field": "偏差率", "operator": "lt", "value": 0.05}
                ]
            },
            "deviation_amount_bands": [
                {"min": 0, "max": 1000, "color": "#e8f5e9", "label": "小"},
                {"min": 1000, "max": 10000, "color": "#fff3e0", "label": "中"},
                {"min": 10000, "max": 999999, "color": "#ffebee", "label": "大"}
            ]
        }

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _evaluate_condition(self, actual: Any, operator: str, expected: Any) -> bool:
        if isinstance(expected, (int, float)) or (isinstance(expected, str) and expected.replace('.', '', 1).isdigit()):
            actual = self._safe_float(actual)
            expected = self._safe_float(expected)

        if operator == "eq":
            return actual == expected
        elif operator == "ne":
            return actual != expected
        elif operator == "lt":
            return actual < expected
        elif operator == "le":
            return actual <= expected
        elif operator == "gt":
            return actual > expected
        elif operator == "ge":
            return actual >= expected
        else:
            logger.warning(f"不支持的操作符: {operator}")
            return False

    def reload(self):
        self._load()
        logger.info("规则已重新加载")

    def get_band(self, value: float, band_key: str) -> Optional[Dict]:
        bands = self.rules.get(band_key, [])
        for band in bands:
            min_val = band.get("min", -float("inf"))
            max_val = band.get("max", float("inf"))
            if min_val <= value < max_val:
                return band
        return None

    def get_color_for_deviation_rate(self, rate: float) -> str:
        band = self.get_band(rate, "deviation_rate_bands")
        return band.get("color", "#ffffff") if band else "#ffffff"

    def get_level_for_deviation_rate(self, rate: float) -> str:
        band = self.get_band(rate, "deviation_rate_bands")
        return band.get("level", "info") if band else "info"

    def get_color_for_deviation_amount(self, amount: float) -> str:
        band = self.get_band(amount, "deviation_amount_bands")
        return band.get("color", "#ffffff") if band else "#ffffff"

    def check_auto_close_condition(self, row: Dict) -> bool:
        auto_close_cfg = self.rules.get("auto_close", {})
        if not auto_close_cfg.get("enabled", False):
            return False
        conditions = auto_close_cfg.get("conditions", [])
        for cond in conditions:
            field = cond.get("field")
            op = cond.get("operator")
            expected = cond.get("value")
            actual = row.get(field)
            if not self._evaluate_condition(actual, op, expected):
                return False
        return True

    def get_all_rules(self) -> Dict:
        return self.rules.copy()

    def get_s01_rules(self) -> dict:
        """返回所有以 's01.' 或 'inventory.' 开头的规则配置"""
        return {k: v for k, v in self.rules.items() if k.startswith('s01.') or k.startswith('inventory.')}
