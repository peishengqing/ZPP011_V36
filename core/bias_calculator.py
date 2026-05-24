#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
偏差计算核心模块（MVP 重构 Task 2）

从 analyzer.py 抽取偏差数量、偏差率、偏差等级判定逻辑，实现配置化阈值。
"""

import json
import os
from typing import Dict, Optional, Any
import pandas as pd


class BiasCalculator:
    """偏差计算器（配置化阈值）"""

    # 默认阈值（当配置文件缺失或节点不存在时使用）
    DEFAULT_THRESHOLDS = {
        'normal': 0.01,   # 1%
        'minor': 0.05,    # 5%
        'major': 0.10,    # 10%
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 BiasCalculator

        :param config_path: 配置文件路径（config/defaults.json），如果为 None 则使用默认路径
        """
        if config_path is None:
            # 默认路径：相对于本文件的 ../../config/defaults.json
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, 'config', 'defaults.json')

        self.thresholds = self._load_thresholds(config_path)

    def _load_thresholds(self, config_path: str) -> Dict[str, float]:
        """
        从配置文件加载阈值

        :param config_path: 配置文件路径
        :return: 阈值字典 {'normal': float, 'minor': float, 'major': float}
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # 读取 bias.thresholds 节点
            bias_config = config.get('bias', {}).get('thresholds', {})

            # 使用配置文件的值，缺失则使用默认值
            return {
                'normal': bias_config.get('normal', self.DEFAULT_THRESHOLDS['normal']),
                'minor': bias_config.get('minor', self.DEFAULT_THRESHOLDS['minor']),
                'major': bias_config.get('major', self.DEFAULT_THRESHOLDS['major']),
            }
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # 配置缺失或格式错误，使用默认值
            return self.DEFAULT_THRESHOLDS.copy()

    # ────────────────────────────────────────────────
    # 方法1：对 DataFrame 向量化计算（高效，替代原有赋值）
    # ────────────────────────────────────────────────
    def calculate_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        对整个 DataFrame 向量化计算偏差数量、偏差率、偏差等级
        （直接替代 analyzer.py 中原有的三行赋值）

        :param df: 包含 '数量-实际'、'数量-定额' 列的 DataFrame
        :return: 新增/更新 '偏差数量'、'偏差率(%)'、'_bias_level' 列的 DataFrame
        """
        # 1. 偏差数量
        dev_qty = df['数量-实际'] - df['数量-定额']

        # 2. 偏差率（%）：|偏差数量| / 定额 × 100，定额为0时记0
        mask = df['数量-定额'] != 0
        bias_rate_pct = pd.Series(0.0, index=df.index)
        bias_rate_pct.loc[mask] = (dev_qty[mask].abs() / df.loc[mask, '数量-定额']) * 100

        # 3. 偏差等级（内部用，基于小数阈值）
        #    先算小数偏差率，再判定等级
        #    注意：定额为0时，偏差率设为 inf，对应等级为 'critical'
        bias_rate_decimal = pd.Series(0.0, index=df.index)
        bias_rate_decimal.loc[mask] = (dev_qty[mask].abs() / df.loc[mask, '数量-定额'])
        bias_rate_decimal.loc[~mask] = float('inf')  # 定额为0 → 偏差率=inf → 等级=critical

        # 4. 写回 DataFrame
        df = df.copy()
        df['偏差数量'] = dev_qty
        df['偏差率(%)'] = bias_rate_pct.round(2)
        df['_bias_level'] = bias_rate_decimal.apply(self._classify_level)

        return df

    # ────────────────────────────────────────────────
    # 方法2：对单行计算（供事件处理、API 调用）
    # ────────────────────────────────────────────────
    def calculate_row(self, actual: float, standard: float,
                    price: Optional[float] = None,
                    amount_actual: Optional[float] = None,
                    amount_standard: Optional[float] = None) -> Dict[str, Any]:
        """
        计算单条记录的偏差量、偏差率、偏差等级、偏差金额

        :param actual: 实际数量（数量-实际）
        :param standard: 定额（数量-定额）
        :param price: 单价（可从 金额-实际(含税) / 数量-实际 计算得到）
        :param amount_actual: 实际金额（金额-实际(含税)），如果提供则优先用于偏差金额计算
        :param amount_standard: 定额金额（金额-定额(含税)），如果提供则优先用于偏差金额计算
        :return: {
            'bias_qty': float,      # 偏差量（actual - standard）
            'bias_rate': float,     # 偏差率（小数，如 0.05 表示 5%）
            'bias_rate_pct': float, # 偏差率（百分数，如 5.0 表示 5%）
            'bias_level': str,      # 'normal', 'minor', 'major', 'critical'
            'bias_amount': float   # 偏差金额
        }
        """
        # 1. 偏差量
        bias_qty = actual - standard

        # 2. 偏差率（小数）
        if standard == 0:
            bias_rate = float('inf')
        else:
            bias_rate = abs(bias_qty) / standard

        # 3. 偏差等级
        bias_level = self._classify_level(bias_rate)

        # 4. 偏差金额（优先使用含税金额差值，否则使用偏差量 × 单价）
        bias_amount = self._calculate_amount(bias_qty, price, amount_actual, amount_standard)

        return {
            'bias_qty': bias_qty,
            'bias_rate': bias_rate,
            'bias_rate_pct': bias_rate * 100,
            'bias_level': bias_level,
            'bias_amount': bias_amount,
        }

    def _classify_level(self, bias_rate: float) -> str:
        """
        根据偏差率判定偏差等级

        :param bias_rate: 偏差率（小数）
        :return: 'normal', 'minor', 'major', 'critical'
        """
        if bias_rate == float('inf'):
            return 'critical'

        if bias_rate < self.thresholds['normal']:
            return 'normal'
        elif bias_rate < self.thresholds['minor']:
            return 'minor'
        elif bias_rate < self.thresholds['major']:
            return 'major'
        else:
            return 'critical'

    def _calculate_amount(self, bias_qty: float, price: Optional[float],
                         amount_actual: Optional[float],
                         amount_standard: Optional[float]) -> float:
        """
        计算偏差金额（优先使用含税金额直接相减）

        :param bias_qty: 偏差量
        :param price: 单价
        :param amount_actual: 实际金额（含税）
        :param amount_standard: 定额金额（含税）
        :return: 偏差金额
        """
        # 优先使用含税金额直接相减（与原代码一致）
        if amount_actual is not None and amount_standard is not None:
            return round(amount_actual - amount_standard, 2)

        # 降级使用偏差量 × 单价
        if price is not None:
            return round(bias_qty * price, 2)

        # 都无法计算，返回 0.0
        return 0.0


# 方便直接导入
__all__ = ['BiasCalculator']
