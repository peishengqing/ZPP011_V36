@echo off
chcp 65001 >nul
cd /d E:\zpp011_dev\模块化脚本

echo ==============================
echo   更新测试文件并推送
echo ==============================

echo.
echo [1/4] 创建更新后的测试文件...

(
echo # -*- coding: utf-8 -*-
echo """
echo 单元测试：core.rule_engine.RuleEngine.check_remark
echo """
echo.
echo import sys, os
echo sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
echo.
echo from core.rule_engine import RuleEngine
echo.
echo.
echo def make_row(remark='', quota=None, code='MAT001', deviation_rate=0.0, stagnant_days=0, actual=0^):
echo     """构造单行数据字典"""
echo     return {
echo         '备注': remark,
echo         '定额': quota,
echo         '组件物料号': code,
echo         '偏差率': deviation_rate,
echo         '呆滞天数': stagnant_days,
echo         '实际': actual,
echo     }
echo.
echo.
echo def test_empty_remark(^):
echo     engine = RuleEngine(^)
echo     row = make_row(remark='', code='MAT001'^)
echo     status, msg = engine.check_remark(row, alt_pairs=None^)
echo     assert status == 'red'
echo     print('[OK] test_empty_remark'^)
echo.
echo.
echo def test_non_quota_non_alt(^):
echo     engine = RuleEngine(^)
echo     row = make_row(remark='有备注', quota=None, code='MAT002', actual=100^)
echo     status, msg = engine.check_remark(row, alt_pairs={'MAT001'}^)
echo     assert status == 'yellow'
echo     print('[OK] test_non_quota_non_alt'^)
echo.
echo.
echo def test_non_quota_zero_actual(^):
echo     engine = RuleEngine(^)
echo     row = make_row(remark='有备注', quota=None, code='MAT002', actual=0^)
echo     status, msg = engine.check_remark(row, alt_pairs={'MAT001'}^)
echo     assert status == 'none'
echo     print('[OK] test_non_quota_zero_actual'^)
echo.
echo.
echo def test_deviation_and_stagnant(^):
echo     engine = RuleEngine(^)
echo     row = make_row(remark='有备注', quota=100, code='MAT003', deviation_rate=0.15, stagnant_days=100, actual=100^)
echo     status, msg = engine.check_remark(row, alt_pairs=None^)
echo     assert status == 'red'
echo     print('[OK] test_deviation_and_stagnant'^)
echo.
echo.
echo def test_alt_material_exempt(^):
echo     engine = RuleEngine(^)
echo     row = make_row(remark='有备注', quota=None, code='MAT001', actual=100^)
echo     status, msg = engine.check_remark(row, alt_pairs={'MAT001', 'MAT002'}^)
echo     assert status == 'none'
echo     print('[OK] test_alt_material_exempt'^)
echo.
echo.
echo def test_all_pass(^):
echo     engine = RuleEngine(^)
echo     row = make_row(remark='正常备注', quota=100, code='MAT004', deviation_rate=0.05, stagnant_days=50, actual=100^)
echo     status, msg = engine.check_remark(row, alt_pairs=None^)
echo     assert status == 'none'
echo     print('[OK] test_all_pass'^)
echo.
echo.
echo if __name__ == '__main__':
echo     test_empty_remark(^)
echo     test_non_quota_non_alt(^)
echo     test_non_quota_zero_actual(^)
echo     test_deviation_and_stagnant(^)
echo     test_alt_material_exempt(^)
echo     test_all_pass(^)
echo     print('\n✅ 全部测试通过！'^)
) > tests\unit\test_rule_engine.py

echo [2/4] 运行测试...
python tests\unit\test_rule_engine.py
if errorlevel 1 (
    echo 测试失败！请检查代码。
    pause
    exit /b 1
)

echo.
echo [3/4] 提交更改...
git add tests\unit\test_rule_engine.py
git commit -m "fix: 修复测试文件，添加 actual 参数"

echo.
echo [4/4] 推送到远程...
git push origin main

echo.
echo ==============================
echo   完成！
echo ==============================
pause
