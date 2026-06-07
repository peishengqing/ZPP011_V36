# -*- coding: utf-8 -*-
"""
指纹计算模块
根据偏差金额和偏差率生成指纹，用于检测数据变动
"""

def calc_fingerprint(amount, rate):
    """
    计算数据指纹
    参数:
        amount: 偏差金额（含税）
        rate: 偏差率(%)
    返回:
        指纹字符串，格式: "金额(2位小数)|偏差率(1位小数)"
    """
    try:
        # 处理 NaN 和 None
        if amount is None or (isinstance(amount, float) and __import__('math').isnan(amount)):
            amount = 0.0
        if rate is None or (isinstance(rate, float) and __import__('math').isnan(rate)):
            rate = 0.0
        
        return f"{float(amount):.2f}|{float(rate):.1f}"
    except Exception:
        return "0.00|0.0"
