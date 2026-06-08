# -*- coding: utf-8 -*-
"""
配置加载器 (单例)
支持从 config/config.yaml 读取配置，缺失字段自动回退默认值。
"""
import os
import yaml
from pathlib import Path


class ConfigLoader:
    _instance = None
    _config = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        base_dir = Path(__file__).resolve().parent.parent
        config_path = base_dir / "config" / "config.yaml"
        default_config = {
            'alert': {
                'threshold_percent': 10.0,
                'scan_interval_seconds': 60,
                'only_alt_materials': True,
            },
            'ppt': {
                'alert_threshold_percent': 10.0,
            }
        }
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                self._config = self._deep_merge(default_config, user_config or {})
            except Exception as e:
                print(f"[ConfigLoader] 加载失败: {e}，使用默认配置")
                self._config = default_config
        else:
            os.makedirs(config_path.parent, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True)
            self._config = default_config

    def reload(self):
        """重新加载配置文件（用于运行时修改）"""
        self._load_config()

    @staticmethod
    def _deep_merge(base, update):
        for k, v in update.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                base[k] = ConfigLoader._deep_merge(base[k], v)
            else:
                base[k] = v
        return base

    def get(self, key_path, default=None):
        keys = key_path.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default


# 全局单例
config = ConfigLoader()
