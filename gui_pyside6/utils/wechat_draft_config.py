# -*- coding: utf-8 -*-
"""
ZPP011 微信草稿格式配置
"""
import os
import json
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QGroupBox, QCheckBox, QLabel, QMessageBox
from PySide6.QtCore import Qt

CONFIG_FILE = os.path.join(os.path.expanduser("~"), "Documents", "ZPP011分析报告", "wechat_draft_config.json")

# 默认配置
DEFAULT_FIELDS = [
    {"key": "date", "label": "日期", "aliases": ["创建日期", "date", "order_date"], "show_empty": True, "format_func": lambda v, df, row: v},
    {"key": "order", "label": "流程订单", "aliases": ["流程订单", "order", "SAP订单", "订单号"], "show_empty": True, "format_func": lambda v, df, row: v},
    {"key": "code", "label": "物料编码", "aliases": ["物料编码", "物料号", "code", "组件物料号"], "show_empty": True, "format_func": lambda v, df, row: v},
    {"key": "name", "label": "物料名称", "aliases": ["物料名称", "物料描述", "name", "组件物料描述"], "show_empty": True, "format_func": lambda v, df, row: str(v)[:20]},
    {"key": "quota", "label": "定额", "aliases": ["定额", "标准用量", "quota"], "show_empty": True, "format_func": lambda v, df, row: v},
    {"key": "actual", "label": "实际", "aliases": ["实际", "实际用量", "actual"], "show_empty": True, "format_func": lambda v, df, row: v},
    {"key": "dev_qty", "label": "偏差数量", "aliases": ["偏差数量", "dev_qty", "quantity"], "show_empty": True, "format_func": lambda v, df, row: v},
    {"key": "dev_rate", "label": "偏差率", "aliases": ["偏差率(%)", "偏差率", "deviation_rate", "rate"], "show_empty": True, "format_func": lambda v, df, row: f"{v}%" if v else ""},
    {"key": "dev_amt", "label": "偏差金额", "aliases": ["偏差金额(含税)", "偏差金额", "deviation_amount", "amount"], "show_empty": True, "format_func": lambda v, df, row: f"¥{v}" if v else ""},
    {"key": "remark", "label": "备注", "aliases": ["备注", "备注原因", "remark"], "show_empty": True, "format_func": lambda v, df, row: v},
]

DEFAULT_CONFIG = {
    "version": "1.0",
    "date": "2026-10-21",
    "fields": DEFAULT_FIELDS,
    "append_date": False,  # 是否在末尾再附加日期
    "header": "偏差沟通",
}

def load_wechat_draft_config():
    """加载配置，如果不存在则返回默认配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        # 尝试创建目录和默认文件
        _save_wechat_draft_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def _save_wechat_draft_config(config):
    """保存配置到文件"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        QMessageBox.critical(None, "错误", f"配置保存失败：{CONFIG_FILE}")
        return False

# 从 main_window 导入一个打开配置窗口的方法，避免循环导入
