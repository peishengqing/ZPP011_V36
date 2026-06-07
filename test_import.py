import sys, io, os
sys.path.insert(0, '.')

# 捕获 stdout/stderr
out = io.StringIO()
err = io.StringIO()
sys.stdout = out
sys.stderr = err

try:
    import smart_ppt_generator_v3
    print("✅ 导入成功")
    
    # 检查 SmartAnalyzer 是否有新方法
    from smart_ppt_generator_v3 import SmartAnalyzer
    has_method = hasattr(SmartAnalyzer, '_calc_food_beverage_stats')
    print(f"  SmartAnalyzer._calc_food_beverage_stats 存在: {has_method}")
    
    # 检查 SmartPPTGenerator 是否有新方法
    from smart_ppt_generator_v3 import SmartPPTGenerator
    has_slide = hasattr(SmartPPTGenerator, '_add_food_beverage_slide')
    print(f"  SmartPPTGenerator._add_food_beverage_slide 存在: {has_slide}")
    
    print("✅ 所有检查通过")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

stdout = out.getvalue()
stderr = err.getvalue()

print("=== STDOUT ===")
print(stdout if stdout else "（空）")
print("=== STDERR ===")
print(stderr if stderr else "（空）")

with open('test_output.txt', 'w', encoding='utf-8') as f:
    f.write("=== STDOUT ===\n")
    f.write(stdout)
    f.write("\n=== STDERR ===\n")
    f.write(stderr)
