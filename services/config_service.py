#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Config Service - 配置服务层

职责：
- 参数配置管理
- 阈值设置
- 颜色方案、路径配置

依赖：
- FileService（配置文件读写）
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime


class ConfigService:
    """配置服务类"""
    
    DEFAULT_CONFIG = {
        'thresholds': {
            'high_deviation_rate': 10.0,  # 高偏差阈值 (%)
            'no_remark_amount': 50000,    # 无备注预警阈值 (元)
        },
        'colors': {
            'positive': '#d4edda',  # 正偏差
            'negative': '#f8d7da',  # 负偏差
            'alt_material': '#fff3cd',  # 替代料
        },
        'paths': {
            'output_dir': '~/Desktop',
            'backup_dir': '~/Desktop/zpp011_backups',
        },
        'limits': {
            'max_rows': 50000,  # 最大数据行数
            'ppt_timeout': 30,  # PPT 生成超时 (秒)
        },
    }
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.expanduser("~/.zpp011_audit/config.json")
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except Exception:
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            self._config = self.DEFAULT_CONFIG.copy()
            self._save_config()
    
    def _save_config(self):
        """保存配置文件"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key_path: 配置键路径（如 "thresholds.high_deviation_rate"）
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any):
        """设置配置值
        
        Args:
            key_path: 配置键路径
            value: 配置值
        """
        keys = key_path.split('.')
        config = self._config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
        self._save_config()
    
    def get_threshold(self, name: str) -> float:
        """获取阈值
        
        Args:
            name: 阈值名称
        
        Returns:
            阈值
        """
        return self.get(f'thresholds.{name}', 0.0)
    
    def get_color(self, name: str) -> str:
        """获取颜色
        
        Args:
            name: 颜色名称
        
        Returns:
            颜色值（十六进制）
        """
        return self.get(f'colors.{name}', '#000000')
    
    def get_path(self, name: str) -> str:
        """获取路径
        
        Args:
            name: 路径名称
        
        Returns:
            路径（展开 ~）
        """
        path = self.get(f'paths.{name}', '~/')
        return os.path.expanduser(path)
