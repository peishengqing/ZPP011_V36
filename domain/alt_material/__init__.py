# -*- coding: utf-8 -*-
"""
domain.alt_material 包
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
