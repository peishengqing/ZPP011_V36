# -*- coding: utf-8 -*-
"""
导入前数据体检（v1）
在分析前检查 SAP 导出文件的质量问题。
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class InspectionResult:
    """体检结果"""
    valid: bool
    message: str
    errors: List[str]
    warnings: List[str]


class DataInspector:
    """数据体检器"""

    # 必需的列名
    REQUIRED_COLUMNS = [
        '订单开始日期', '数量-定额', '数量-实际', '偏差数量',
        '金额-定额(含税)', '金额-实际(含税)', '材料偏差', '偏差率(%)',
        '组件物料描述', '物料编码', '工厂', '流程订单', '订单日期',
        '实际成本', '产量', '组件数量', '单位', '供应商',
        '组件物料类型描述'
    ]

    def __init__(self):
        self.errors = []
        self.warnings = []

    def inspect_file(self, file_path: str) -> InspectionResult:
        """检查文件质量"""
        self.errors = []
        self.warnings = []

        try:
            # 使用 pandas 快速读取
            df = pd.read_excel(file_path, sheet_name='Data', nrows=0)  # 只读列结构

            # 检查必需列
            self._check_required_columns(df)

            if self.errors:
                return InspectionResult(
                    valid=False,
                    message=f"发现 {len(self.errors)} 个错误，{len(self.warnings)} 个警告",
                    errors=self.errors.copy(),
                    warnings=self.warnings.copy()
                )

            # 后续检查需要完整数据，可以抽样检查
            df_full = pd.read_excel(file_path, sheet_name='Data')
            self._check_data_quality(df_full)

            if self.errors:
                return InspectionResult(
                    valid=False,
                    message=f"发现 {len(self.errors)} 个错误，{len(self.warnings)} 个警告",
                    errors=self.errors.copy(),
                    warnings=self.warnings.copy()
                )

            return InspectionResult(
                valid=True,
                message=f"数据检查通过，共 {len(self.warnings)} 个警告",
                errors=[],
                warnings=self.warnings.copy()
            )

        except Exception as e:
            self.errors.append(f"文件读取失败：{str(e)}")
            return InspectionResult(
                valid=False,
                message="文件读取失败",
                errors=self.errors.copy(),
                warnings=self.warnings.copy()
            )

    def _check_required_columns(self, df: pd.DataFrame):
        """检查必需列"""
        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            self.errors.append(f"缺少必需列：{', '.join(missing)}")
        else:
            self.warnings.append(f"所有必需列存在 ({len(self.REQUIRED_COLUMNS)})")

    def _check_data_quality(self, df: pd.DataFrame):
        """检查数据质量"""
        # 检查空行
        total_rows = len(df)
        empty_rows = df.isnull().all(axis=1)
        empty_count = empty_rows.sum()
        if empty_count > 0:
            self.warnings.append(f"发现 {empty_count} 个全空行 (共 {total_rows} 行)")

        # 检查关键数值列为空的情况
        numeric_cols = ['数量-定额', '数量-实际', '偏差数量', '金额-定额(含税)', '金额-实际(含税)']
        for col in numeric_cols:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                if null_count > 0:
                    self.warnings.append(f"列 '{col}' 有 {null_count} 个空值")

        # 检查单位格式（简单检查）
        if '单位' in df.columns:
            unusual_units = df[~df['单位'].str.contains(r'^[a-zA-Z0-9 \\/]', na=False)].iloc[:5]
            if len(unusual_units) > 0:
                self.warnings.append(f"发现 {len(unusual_units)} 个非标准单位")

        # 检查日期格式
        date_cols = ['订单开始日期', '订单日期']
        for col in date_cols:
            if col in df.columns:
                try:
                    pd.to_datetime(df[col], errors='raise')
                except Exception:
                    self.warnings.append(f"列 '{col}' 存在非日期格式")

    def get_clean_instructions(self) -> str:
        """获取修复建议"""
        instructions = []
        for error in self.errors:
            if "缺少必需列" in error:
                instructions.append("✓ 确认 SAP 导出时选择了完整的列")
                break
        for warning in self.warnings:
            if "全空行" in warning:
                instructions.append("• 可以删除 Excel 中的空白行以提高分析效率")
            if "非标准单位" in warning:
                instructions.append("• 检查单位列是否包含特殊字符或中文单位")
        return "\n".join(instructions)
