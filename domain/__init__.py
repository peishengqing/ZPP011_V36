# -*- coding: utf-8 -*-
"""
domain 包 - 数据模型与业务实体
"""

from domain.alt_material.alt_manager import (
    load_alt_pairs,
    save_alt_pairs,
    build_code_name_map,
    get_display_name,
)

__all__ = [
    'load_alt_pairs',
    'save_alt_pairs',
    'build_code_name_map',
    'get_display_name',
]
