# core/rule_engine.py
import json
import ast
import operator as op
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger

logger = get_logger("RuleEngine")

# 允许的字段白名单
ALLOWED_FIELDS = {
    'dev_rate', 'deviation_amount', 'remark', 'remark_status', 'is_alt',
    '定额', '实际', '偏差率(%)', '备注', '备注原因'
}

# 允许的运算符映射
OP_MAP = {
    '>=': op.ge, '>': op.gt, '==': op.eq, '!=': op.ne,
    '<': op.lt, '<=': op.le,
    'contains': lambda a, b: b in str(a) if a is not None else False,
    'empty': lambda a, _: not str(a).strip() if a is not None else True
}


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
                    {"field": "偏差率(%)", "operator": "lt", "value": 0.05}
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

    def test_condition(self, condition: dict, test_data: dict) -> tuple[bool, dict]:
        """
        测试规则，返回 (是否匹配, 执行的动作)
        
        Args:
            condition: 条件字典，如 {"field": "dev_rate", "op": ">=", "value": 10}
            test_data: 测试数据字典
            
        Returns:
            (是否匹配, 执行的动作字典)
        """
        if not condition:
            return False, {}
        
        # 处理组合条件
        if "operator" in condition:
            op_type = condition["operator"].lower()
            if op_type not in ("and", "or"):
                return False, {}
            sub_results = []
            for sub in condition.get("conditions", []):
                matched, _ = self.test_condition(sub, test_data)
                sub_results.append(matched)
            match = all(sub_results) if op_type == "and" else any(sub_results)
            return match, {}
        
        # 单条件
        field = condition.get("field")
        op_name = condition.get("op")
        value = condition.get("value")
        
        if field not in ALLOWED_FIELDS:
            return False, {"error": f"字段 '{field}' 不在白名单中"}
        
        actual = test_data.get(field)
        
        # 空值检查
        if op_name == "empty":
            match = (actual is None) or (str(actual).strip() == "")
            return match, {"field": field, "actual": actual}
        
        # 包含检查
        if op_name == "contains":
            match = str(value) in str(actual) if actual is not None else False
            return match, {"field": field, "actual": actual, "expected": value}
        
        # 数值比较
        try:
            left = float(actual) if actual is not None else 0.0
            right = float(value)
        except (TypeError, ValueError):
            return False, {"field": field, "error": f"无法转换为数值: {actual}"}
        
        op_func = OP_MAP.get(op_name)
        if not op_func:
            return False, {"field": field, "error": f"不支持的运算符: {op_name}"}
        
        match = op_func(left, right)
        return match, {"field": field, "actual": actual, "expected": right, "match": match}

    def reload_rules(self):
        """热重载规则"""
        self.reload()

    def get_s01_rules(self) -> dict:
        """返回所有以 's01.' 或 'inventory.' 开头的规则配置"""
        return {k: v for k, v in self.rules.items() if k.startswith('s01.') or k.startswith('inventory.')}

    def check_remark(self, row: Dict, alt_pairs: Optional[set] = None,
                      workshop_mapping: Optional[Dict] = None,
                      turnover_dict: Optional[Dict] = None) -> tuple:
        """
        备注校验规则引擎
        :param row: 单行数据字典
        :param alt_pairs: 替代料编码集合（可选，用于豁免）
        :param workshop_mapping: 车间→库存地点映射字典（可选，规则3用）
        :param turnover_dict: (物料编码, 库存地点)→周转天数 字典（可选，规则3用）
        :return: (status, message) 元组，status ∈ {red, yellow, none}
        """
        remark = str(row.get('备注', '')).strip()
        code = str(row.get('组件物料号', '')).strip()
        deviation_rate = self._safe_float(row.get('偏差率(%)', 0))

        # 规则1：空备注 → red
        if not remark:
            return ('red', '备注为空')

        # 规则2：无定额非替代料 → yellow
        quota = row.get('定额', None)
        actual = self._safe_float(row.get('实际', 0))
        is_alt = code in alt_pairs if alt_pairs else False
        if quota is None and actual > 0 and not is_alt:
            return ('yellow', '无定额且非替代料')

        # 规则3：偏差率(%) > 10 且 周转天数 > 90 → yellow
        if deviation_rate > 10 and workshop_mapping and turnover_dict:
            factory = str(row.get('工厂', '')).strip()
            workshop = str(row.get('车间', '')).strip()
            key = f"{factory}:{workshop}"
            inv_location = workshop_mapping.get(key)
            if inv_location:
                material_code = str(row.get('物料编码', '')).strip()
                key = (material_code, inv_location)
                turnover_days = turnover_dict.get(key)
                if turnover_days and turnover_days > 90:
                    return ('yellow', '偏差较大且物料周转天数过长，请核实')

        # 全部通过
        return ('none', '')
# ==================== 安全条件解析器（任务卡025）====================

import operator as op
from typing import Dict, Any

# 允许的字段白名单
ALLOWED_FIELDS = {
    'dev_rate', 'deviation_amount', 'remark', 'remark_status', 'is_alt'
}

# 允许的运算符映射
OP_MAP = {
    '>=': op.ge, '>': op.gt, '==': op.eq, '!=': op.ne,
    '<': op.lt, '<=': op.le,
    'contains': lambda a, b: b in str(a) if a is not None else False,
    'empty': lambda a, _: not str(a).strip() if a is not None else True
}

def safe_eval_condition(condition: Dict[str, Any], row_data: Dict[str, Any]) -> bool:
    """
    安全评估结构化条件
    单条件: {"field": "dev_rate", "op": ">=", "value": 10}
    组合条件: {"operator": "and", "conditions": [...]}
    """
    if "operator" in condition:
        op_type = condition["operator"].lower()
        if op_type not in ("and", "or"):
            raise ValueError(f"不支持的组合操作符: {op_type}")
        results = [safe_eval_condition(sub, row_data) for sub in condition["conditions"]]
        return all(results) if op_type == "and" else any(results)

    field = condition.get("field")
    op_name = condition.get("op")
    value = condition.get("value")

    if field not in ALLOWED_FIELDS:
        raise ValueError(f"字段 '{field}' 不在白名单中")

    actual = row_data.get(field)

    if op_name == "empty":
        return (actual is None) or (str(actual).strip() == "")

    if op_name == "contains":
        return str(value) in str(actual) if actual is not None else False

    try:
        left = float(actual) if actual is not None else 0.0
        right = float(value)
    except (TypeError, ValueError):
        return False

    op_func = OP_MAP.get(op_name)
    if not op_func:
        raise ValueError(f"不支持的运算符: {op_name}")

    return op_func(left, right)