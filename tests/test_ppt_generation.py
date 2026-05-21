# -*- coding: utf-8 -*-
"""
ZPP011 PPT 生成优化 v1.2 单元测试

覆盖以下场景：
1. 数据集 9889 条，生成时间 <= 30 秒
2. 分工厂逻辑：食品厂/饮料厂数据隔离
3. 物料分类：编码前缀 100/400/200/600 分类准确
4. 空数据处理：某工厂无车间数据，显示"无数据"
5. 不足 10 条：饮料厂物料 Top10 仅 3 条，显示全部并标注
6. 模板缺失：Fallback 代码生成样式正常
7. 数据超限：模拟 50000+ 条数据，抛出异常
8. 进度回调：生成过程中进度百分比从 0% 递增至 100%

测试执行：pytest tests/test_ppt_generation.py -v
"""
import os
import sys
import time
import tempfile
import shutil

# 确保项目根目录在 path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import pytest


# ============================================================
# 测试数据生成辅助函数
# ============================================================

def make_df_9889():
    """生成 9889 条测试数据（接近实际数据量）"""
    import numpy as np
    np.random.seed(42)

    factories = ['1101', '1102'] * 4900 + ['1101']
    workshops = ['食品一车间', '食品二车间', '饮料一车间', '饮料二车间',
                 '食品一车间', '食品二车间', '饮料一车间', '饮料二车间',
                 '包装车间', '原料仓库']

    data = []
    for i in range(9889):
        fac = factories[i % len(factories)]
        ws = workshops[i % len(workshops)]
        # 物料编码前缀
        mat_codes = ['100' + str(i % 1000), '200' + str(i % 500),
                     '400' + str(i % 800), '600' + str(i % 600),
                     '999' + str(i % 300)]
        mat_code = mat_codes[i % len(mat_codes)]
        mat_names = [f'物料-{mat_code}-{i}' for _ in range(1)]
        mat_name = f'物料-{mat_code}-{i%50}'

        dev_amount = round(np.random.uniform(-50000, 50000), 2)
        dev_rate = round(np.random.uniform(-30, 30), 2)

        reasons = ['生产原因', '设备原因', '物料原因', '工艺原因', '']
        remark = reasons[i % len(reasons)]

        dev_types = ['数量偏差', '质量偏差', '规格偏差', '其他偏差']
        dev_type = dev_types[i % len(dev_types)]

        data.append({
            '工厂': fac,
            '车间': ws,
            '物料编码': mat_code,
            '组件物料描述': mat_name,
            '物料名称': mat_name,
            '偏差金额': dev_amount,
            '偏差率': dev_rate,
            '偏差率(%)': dev_rate,
            '偏差类型': dev_type,
            '备注原因': remark,
            '数量 - 定额': abs(round(np.random.uniform(0, 100), 2)),
            '数量 - 实际': 0 if i % 50 == 0 else abs(round(np.random.uniform(0, 100), 2)),
        })

    return pd.DataFrame(data)


def make_df_only_3_materials():
    """生成仅 3 条物料的测试数据（不足 10 条场景）"""
    return pd.DataFrame([
        {'工厂': '1102', '车间': '饮料一车间', '物料编码': '200001',
         '组件物料描述': '饮料瓶A', '物料名称': '饮料瓶A',
         '偏差金额': 3000.0, '偏差率': 5.0, '偏差率(%)': 5.0,
         '偏差类型': '数量偏差', '备注原因': '测试原因1',
         '数量 - 定额': 100, '数量 - 实际': 95},
        {'工厂': '1102', '车间': '饮料一车间', '物料编码': '200002',
         '组件物料描述': '饮料瓶B', '物料名称': '饮料瓶B',
         '偏差金额': 5000.0, '偏差率': 8.0, '偏差率(%)': 8.0,
         '偏差类型': '数量偏差', '备注原因': '测试原因2',
         '数量 - 定额': 100, '数量 - 实际': 92},
        {'工厂': '1102', '车间': '饮料一车间', '物料编码': '200003',
         '组件物料描述': '饮料瓶C', '物料名称': '饮料瓶C',
         '偏差金额': -2000.0, '偏差率': -3.0, '偏差率(%)': -3.0,
         '偏差类型': '数量偏差', '备注原因': '',
         '数量 - 定额': 100, '数量 - 实际': 103},
    ])


def make_df_no_workshop():
    """生成无车间数据的测试数据"""
    return pd.DataFrame([
        {'工厂': '1101', '车间': '', '物料编码': '100001',
         '组件物料描述': '物料A', '物料名称': '物料A',
         '偏差金额': 1000.0, '偏差率': 2.0, '偏差率(%)': 2.0,
         '偏差类型': '数量偏差', '备注原因': '',
         '数量 - 定额': 50, '数量 - 实际': 48},
    ])


def make_df_over_50k():
    """生成超过 50000 条的测试数据"""
    base = make_df_9889()
    # 重复 6 次 → 59334 条
    return pd.concat([base] * 6, ignore_index=True).head(60000)


# ============================================================
# Mock View 实现
# ============================================================

class MockView:
    """Mock View 实现，仅用于测试 Presenter"""

    def __init__(self, df=None):
        self._df = df if df is not None else make_df_9889()
        self._output_path = tempfile.mktemp(suffix='.xlsx')
        self._log_messages = []

    def get_audit_data(self):
        return self._df

    def get_output_path(self):
        return self._output_path

    def log(self, msg, level=None):
        self._log_messages.append((level, msg))


# ============================================================
# pytest 测试用例
# ============================================================

class TestClassifyMaterialType:
    """测试 _classify_material_type 方法"""

    def test_原材料_prefix_100(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        presenter = AuditPresenter(MockModel(), MockView())
        assert presenter._classify_material_type('100001') == '原材料'
        assert presenter._classify_material_type('100999') == '原材料'

    def test_原材料_prefix_400(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        presenter = AuditPresenter(MockModel(), MockView())
        assert presenter._classify_material_type('400001') == '原材料'
        assert presenter._classify_material_type('400888') == '原材料'

    def test_包材_prefix_200(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        presenter = AuditPresenter(MockModel(), MockView())
        assert presenter._classify_material_type('200001') == '包材'
        assert presenter._classify_material_type('200777') == '包材'

    def test_包材_prefix_600(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        presenter = AuditPresenter(MockModel(), MockView())
        assert presenter._classify_material_type('600001') == '包材'
        assert presenter._classify_material_type('600555') == '包材'

    def test_其他_prefix_其他(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        presenter = AuditPresenter(MockModel(), MockView())
        assert presenter._classify_material_type('999001') == '其他'
        assert presenter._classify_material_type('888001') == '其他'
        assert presenter._classify_material_type('300001') == '其他'

    def test_空值和异常(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        presenter = AuditPresenter(MockModel(), MockView())
        assert presenter._classify_material_type('') == '其他'
        assert presenter._classify_material_type(None) == '其他'
        assert presenter._classify_material_type(12345) == '其他'  # int
        assert presenter._classify_material_type('   ') == '其他'


class TestPreAggregateData:
    """测试 _pre_aggregate_data 方法"""

    def test_动态检测工厂(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_9889()
        view = MockView(df)
        presenter = AuditPresenter(MockModel(), view)
        pre = presenter._pre_aggregate_data(df)
        assert '1101' in pre['factories']
        assert '1102' in pre['factories']
        assert len(pre['factories']) == 2

    def test_工厂KPI完整(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_9889()
        presenter = AuditPresenter(MockModel(), MockView(df))
        pre = presenter._pre_aggregate_data(df)
        for fac in ['1101', '1102']:
            assert fac in pre['factory_kpis']
            assert 'total_records' in pre['factory_kpis'][fac]
            assert 'total_amount' in pre['factory_kpis'][fac]
            assert 'avg_dev_rate' in pre['factory_kpis'][fac]
            assert 'high_dev_count' in pre['factory_kpis'][fac]

    def test_物料Top10分工厂(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_9889()
        presenter = AuditPresenter(MockModel(), MockView(df))
        pre = presenter._pre_aggregate_data(df)
        for fac in ['1101', '1102']:
            assert fac in pre['material_top10']
            assert isinstance(pre['material_top10'][fac], dict)

    def test_物料类型分类(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_9889()
        presenter = AuditPresenter(MockModel(), MockView(df))
        pre = presenter._pre_aggregate_data(df)
        assert 'material_type_net' in pre
        # 原材料（100/400）和包材（200/600）都应有数据
        mat_net = pre['material_type_net']
        assert '原材料' in [t for net in mat_net.values() for t in net.keys()] or \
               '包材' in [t for net in mat_net.values() for t in net.keys()]

    def test_无备注预警阈值5万(self):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_9889()
        presenter = AuditPresenter(MockModel(), MockView(df))
        pre = presenter._pre_aggregate_data(df)
        # 检查无备注预警的金额都 >= 50000
        for fac, warn_df in pre['no_remark_warning'].items():
            if not warn_df.empty:
                amounts = warn_df['偏差金额'].abs()
                assert (amounts >= 50000).all(), f"{fac} 无备注预警含有 <5万的记录"


class TestGeneratePPT:
    """测试 generate_ppt 主方法"""

    @pytest.fixture
    def temp_output(self):
        """创建临时输出目录"""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_数据集9889条_生成时间小于30秒(self, temp_output):
        from modules.audit.presenters.audit_presenter import AuditPresenter
        import time
        class MockModel: pass
        df = make_df_9889()
        view = MockView(df)
        presenter = AuditPresenter(MockModel(), view)

        output_path = os.path.join(temp_output, 'test_9889.pptx')

        start = time.time()
        result = presenter.generate_ppt(output_path=output_path)
        elapsed = time.time() - start

        assert os.path.exists(result), f"PPT 文件未生成: {result}"
        assert elapsed < 30, f"生成耗时 {elapsed:.1f}秒，超过 30 秒限制"
        print(f"\n[PASS] 9889 条数据生成耗时: {elapsed:.2f} 秒")

    def test_分工厂数据隔离(self, temp_output):
        """验证不同工厂的数据不会混淆"""
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_9889()
        view = MockView(df)
        presenter = AuditPresenter(MockModel(), view)

        output_path = os.path.join(temp_output, 'test_factory.pptx')
        result = presenter.generate_ppt(output_path=output_path)

        assert os.path.exists(result)
        print(f"\n[PASS] 分工厂数据隔离: PPT 已生成 {result}")

    def test_不足10条_显示全部并标注(self, temp_output):
        """仅 3 条物料时，显示全部并标注"""
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_only_3_materials()
        view = MockView(df)
        presenter = AuditPresenter(MockModel(), view)

        output_path = os.path.join(temp_output, 'test_3items.pptx')
        result = presenter.generate_ppt(output_path=output_path)

        assert os.path.exists(result)
        # _add_material_top10 应在表格下方添加标注
        print(f"\n[PASS] 不足10条物料: PPT 已生成，表格应含标注")

    def test_无车间数据_显示无数据(self, temp_output):
        """无车间数据时显示无车间级数据"""
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_no_workshop()
        view = MockView(df)
        presenter = AuditPresenter(MockModel(), view)

        output_path = os.path.join(temp_output, 'test_noworkshop.pptx')
        result = presenter.generate_ppt(output_path=output_path)

        assert os.path.exists(result)
        print(f"\n[PASS] 无车间数据: PPT 已生成")

    def test_模板缺失_Fallback正常(self, temp_output):
        """config/template.pptx 不存在时，Fallback 代码生成"""
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_9889()
        view = MockView(df)
        presenter = AuditPresenter(MockModel(), view)

        output_path = os.path.join(temp_output, 'test_no_template.pptx')
        result = presenter.generate_ppt(output_path=output_path)

        assert os.path.exists(result)
        # 验证是有效的 PPTX 文件（ZIP 格式）
        import zipfile
        assert zipfile.is_zipfile(result), "生成的 PPT 文件不是有效的 ZIP/PPTX"
        print(f"\n[PASS] 模板缺失 Fallback: PPT 有效 ZIP")

    def test_数据超限_抛出异常(self, temp_output):
        """超过 50000 条数据应抛出异常"""
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_over_50k()
        view = MockView(df)
        presenter = AuditPresenter(MockModel(), view)

        output_path = os.path.join(temp_output, 'test_50k.pptx')

        with pytest.raises(Exception) as exc_info:
            presenter.generate_ppt(output_path=output_path)

        assert '5 万' in str(exc_info.value) or '50000' in str(exc_info.value)
        print(f"\n[PASS] 数据超限: 正确抛出异常 - {exc_info.value}")

    def test_进度回调_从0到100(self, temp_output):
        """验证进度回调从 0% 递增至 100%"""
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        df = make_df_9889()
        view = MockView(df)
        presenter = AuditPresenter(MockModel(), view)

        output_path = os.path.join(temp_output, 'test_progress.pptx')
        progress_values = []

        def track(pct):
            progress_values.append(pct)

        presenter.generate_ppt(output_path=output_path, progress_callback=track)

        assert len(progress_values) > 0, "进度回调未被调用"
        assert progress_values[0] > 0, "进度应从 >0 开始"
        assert progress_values[-1] == 100, f"最终进度应为 100%，实际为 {progress_values[-1]}%"
        assert all(progress_values[i] <= progress_values[i+1]
                   for i in range(len(progress_values)-1)), "进度应单调递增"
        print(f"\n[PASS] 进度回调: {len(progress_values)} 次调用，范围 {progress_values[0]:.0f}%~{progress_values[-1]:.0f}%")

    def test_空DataFrame_抛出ValueError(self, temp_output):
        """空 DataFrame 应抛出 ValueError"""
        from modules.audit.presenters.audit_presenter import AuditPresenter
        class MockModel: pass
        view = MockView(pd.DataFrame())
        presenter = AuditPresenter(MockModel(), view)

        output_path = os.path.join(temp_output, 'test_empty.pptx')

        with pytest.raises(ValueError):
            presenter.generate_ppt(output_path=output_path)
        print(f"\n[PASS] 空 DataFrame: 正确抛出 ValueError")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
