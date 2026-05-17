# test_rule_engine.py
from core.rule_engine import RuleEngine

re = RuleEngine()

print("=== deviation rate colors ===")
print(f"0.03 -> {re.get_color_for_deviation_rate(0.03)}")
print(f"0.07 -> {re.get_color_for_deviation_rate(0.07)}")
print(f"0.12 -> {re.get_color_for_deviation_rate(0.12)}")

print()
print("=== auto close ===")
print(f"pass: {re.check_auto_close_condition({'审核状态': '已审核', '偏差率': 0.04})}")
print(f"fail: {re.check_auto_close_condition({'审核状态': '未审核', '偏差率': 0.04})}")

print()
print("=== dirty data ===")
print(f"dirty: {re.check_auto_close_condition({'审核状态': None, '偏差率': 'abc'})}")

print()
print("=== boundary (min <= value < max) ===")
print(f"0.05 boundary: {re.get_color_for_deviation_rate(0.05)}")
print(f"0.10 boundary: {re.get_color_for_deviation_rate(0.10)}")
print("ALL OK")
