# -*- coding: utf-8 -*-
"""
domain 包 - 领域模型与业务实体
"""

from domain.alt_material.alt_manager import (
    load_alt_pairs,
    save_alt_pairs,
)

__all__ = [
    'load_alt_pairs',
    'save_alt_pairs',
]
