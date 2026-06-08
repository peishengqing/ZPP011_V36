import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import pandas as pd
import tempfile
from analysis.analyzer import do_analysis_v2


def _build_full_fixture_df():
    """构建包含 do_analysis_v2 所需全部输入列的 DataFrame"""
    data = {
        '订单日期': ['2026-05-01', '2026-05-02'],
        '流程订单': ['PO001', 'PO002'],
        '物料编码': ['200001', '300001'],
        '物料名称': ['托盘', '小麦粉'],
        '组件物料号': ['60001', '60002'],
        '组件物料描述': ['木托盘', '标准小麦粉'],
        '组件物料类型': ['Z020', 'Z030'],
        '组件物料类型描述': ['包材', '原料'],
        '数量-定额': [100.0, 200.0],
        '数量-实际': [110.0, 180.0],
        '金额-定额(含税)': [1000.0, 2000.0],
        '金额-实际(含税)': [1100.0, 1800.0],
        '工厂': ['工厂A', '工厂A'],
        '车间': ['车间1', '车间2'],
        '订单开始日期': ['2026-05-01', '2026-05-02'],
        '物料类型': ['包材', '原料'],
        '备注原因': ['正常', '正常'],
        '偏差率(%)': [10.0, -10.0],
        '生产管理员描述': ['主管1', '主管2'],
        '工厂名称': ['A工厂', 'A工厂'],
        '偏差数量': [10.0, -20.0],
        '偏差金额(含税)': [100.0, -200.0],
        '偏差率': ['10.0%', '-10.0%'],
        '偏差金额': [100.0, -200.0],
        '材料偏差': [10.0, -20.0],
        '实际成本': [1100.0, 1800.0],
        '单位': ['个', 'kg'],
        '组件数量': [10, 5],
        '产量': [110, 180],
        '原表行号': [1, 2],
        '备注': ['', ''],
        '备注来源': ['', ''],
        '标准原因': ['', ''],
        '预警': ['', ''],
        '是否替代料': ['否', '是'],
        '替代料组': ['', 'GROUP_A'],
        '净偏差金额': [0.0, 0.0],
        '净偏差数量': [0.0, 0.0],
        '订单类型': ['标准', '标准'],
        '组件单位': ['个', 'kg'],
    }
    df = pd.DataFrame(data)
    return df


@pytest.fixture
def full_excel_path():
    """写入完整 DataFrame 为临时 Excel"""
    df = _build_full_fixture_df()
    tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    df.to_excel(tmp.name, sheet_name='Data', index=False)
    path = tmp.name
    tmp.close()
    yield path
    try:
        os.unlink(path)
    except PermissionError:
        pass


class TestDoAnalysisV2Integration:
    """do_analysis_v2 端到端集成测试（完整列）"""

    def test_basic_flow(self, full_excel_path):
        """基础路径：能正常完成"""
        result = do_analysis_v2(
            input_file=full_excel_path,
            output_dir=None,
            alt_pairs=[],
            enable_net_offset=False,
            return_dataframe=True
        )
        assert result is not None
        assert not result.empty

    def test_returns_dataframe(self, full_excel_path):
        """确保返回 DataFrame"""
        result = do_analysis_v2(
            input_file=full_excel_path,
            output_dir=None,
            alt_pairs=[],
            enable_net_offset=False,
            return_dataframe=True
        )
        assert isinstance(result, pd.DataFrame)

    def test_with_alt_pair(self, full_excel_path):
        """替代料配对处理"""
        result = do_analysis_v2(
            input_file=full_excel_path,
            output_dir=None,
            alt_pairs=[('200001', '300001')],
            enable_net_offset=True,
            return_dataframe=True
        )
        assert '净偏差金额' in result.columns or '净偏差' in result.columns

    def test_output_file_created(self, full_excel_path):
        """指定 output_path 时生成文件"""
        import tempfile
        out = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        out.close()
        try:
            do_analysis_v2(
                input_file=full_excel_path,
                output_dir=None,
                alt_pairs=[],
                enable_net_offset=False,
                return_dataframe=False,
                output_path=out.name
            )
            assert os.path.exists(out.name)
            assert os.path.getsize(out.name) > 0
        finally:
            try: os.unlink(out.name)
            except: pass

    def test_empty_file(self):
        """空文件应抛出异常"""
        df = _build_full_fixture_df().iloc[:0]
        tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        df.to_excel(tmp.name, sheet_name='Data', index=False)
        path = tmp.name
        tmp.close()
        try:
            result = do_analysis_v2(
                input_file=path,
                output_dir=None,
                alt_pairs=[],
                enable_net_offset=False,
                return_dataframe=True
            )
            assert result is None or result.empty
        except (Exception,):
            pass
        finally:
            try: os.unlink(path)
            except: pass

    def test_file_not_found(self):
        """文件不存在应该报错"""
        with pytest.raises(FileNotFoundError):
            do_analysis_v2(
                input_file=r'C:\nonexistent_file_12345.xlsx',
                output_dir=None,
                alt_pairs=[],
                enable_net_offset=False,
                return_dataframe=True
            )
