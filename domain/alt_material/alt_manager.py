# -*- coding: utf-8 -*-
"""
替代料管理模块（标准化版）
强制使用 (工厂, 编码, 名称) 三元组格式
兼容旧格式自动迁移
"""

import os
import json
import sys
import pandas as pd

def _get_config_path():
    """获取配置文件路径（用户目录，可写）"""
    config_dir = os.path.join(
        os.environ.get('APPDATA', os.path.expanduser('~')),
        'ZPP011', 'config'
    )
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'alt_pairs.json')

def _normalize_item(item):
    """
    将任意格式的单个物料转为 (工厂, 编码, 名称) 三元组
    - 三元组 (工厂, 编码, 名称): 直接返回
    - 三元组 (编码, 名称, 工厂): 自动交换
    - 二元组 (编码, 名称): 工厂为空
    - 字符串: 编码=名称=字符串，工厂为空
    """
    # 已经是三元组
    if isinstance(item, (list, tuple)) and len(item) == 3:
        factory, code, name = item[0], item[1], item[2]
        # 检查第三个元素是否像工厂（包含'厂'或'公司'）
        if name and ('厂' in str(name) or '公司' in str(name)):
            # 顺序可能是 (编码, 名称, 工厂)，需要交换
            return (str(name), str(factory), str(code))
        return (str(factory), str(code), str(name))
    
    # 二元组 (编码, 名称)
    if isinstance(item, (list, tuple)) and len(item) == 2:
        return ('', str(item[0]), str(item[1]))
    
    # 纯字符串或其他
    s = str(item) if item else ''
    return ('', s, s)

def _normalize_pair(pair):
    """标准化一对物料"""
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return (('', '', ''), ('', '', ''))
    
    a = _normalize_item(pair[0])
    b = _normalize_item(pair[1])
    return (a, b)

def load_alt_pairs(log_cb=None, material_df=None):
    """
    加载替代料配对，强制返回标准化三元组列表
    返回格式：[((工厂, 编码, 名称), (工厂, 编码, 名称)), ...]
    """
    config_path = _get_config_path()
    
    # 如果配置文件不存在，返回空列表（让调用方使用默认）
    if not os.path.exists(config_path):
        if log_cb:
            log_cb("替代料配置文件不存在，将使用内置配对", "warning")
        return list(DEFAULT_ALT_PAIRS)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            if log_cb:
                log_cb("替代料配置文件格式错误，已重置", "warn")
            return list(DEFAULT_ALT_PAIRS)
        
        pairs = []
        for pair in data:
            normalized = _normalize_pair(pair)
            # 至少编码非空才加入
            if normalized[0][1] and normalized[1][1]:
                pairs.append(normalized)
        
        if log_cb:
            log_cb(f"加载替代料配置：{config_path}，共{len(pairs)}对")
        
        return pairs
    
    except Exception as e:
        if log_cb:
            log_cb(f"加载替代料配置失败：{e}", "error")
        return list(DEFAULT_ALT_PAIRS)

def save_alt_pairs(pairs, log_cb=None):
    """
    保存替代料配对，确保为标准三元组格式
    保存格式：[[[工厂, 编码, 名称], [工厂, 编码, 名称]], ...]
    """
    config_path = _get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    # 标准化所有配对
    normalized = []
    for a, b in pairs:
        na = _normalize_item(a)
        nb = _normalize_item(b)
        normalized.append([list(na), list(nb)])
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        
        if log_cb:
            log_cb(f"替代料配置已保存：{config_path}，共{len(normalized)}对")
    
    except Exception as e:
        if log_cb:
            log_cb(f"保存替代料配置失败：{e}", "error")

def get_display_text(material_tuple):
    """
    根据物料三元组 (工厂, 编码, 名称) 返回显示文本
    优先显示 "编码 名称"，工厂可选显示
    """
    if not isinstance(material_tuple, (list, tuple)):
        return str(material_tuple)
    
    if len(material_tuple) >= 3:
        factory, code, name = material_tuple[0], material_tuple[1], material_tuple[2]
    elif len(material_tuple) == 2:
        factory, code, name = '', material_tuple[0], material_tuple[1]
    else:
        return str(material_tuple)
    
    # 构建显示文本
    if code and name:
        return f"{code} {name}"
    elif code:
        return code
    elif name:
        return name
    else:
        return "?"

# 内置默认配对（格式：(工厂, 编码, 名称)）
DEFAULT_ALT_PAIRS = [
    (('', '', ''), ('', '', '')),  # 占位，实际应从配置文件加载
]
