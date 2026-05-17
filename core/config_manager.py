# core/config_manager.py
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger

logger = get_logger("ConfigManager")


class ConfigManager:
    """统一配置管理器，支持版本迁移、默认值、自动保存"""

    CURRENT_VERSION = "1.0"

    # 默认配置模板（新用户或无配置时使用）
    DEFAULT_CONFIG = {
        "version": CURRENT_VERSION,
        "window": {
            "width": 1200,
            "height": 800,
            "x": None,  # None 表示由窗口管理器决定
            "y": None,
            "maximized": False
        },
        "table": {
            "column_widths": {},  # 列名 -> 宽度
            "sort_column": None,
            "sort_order": "asc"
        },
        "recent_files": [],
        "ai": {"use_mock_ai": False},  # 最多5个
        "last_export_dir": "",
        "filter_history": {},  # 上次使用的筛选条件
        "auto_save": True,
        "theme": "default"
    }

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path.home() / ".zpp011_audit" / "config.json"
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """加载配置文件，若不存在或版本不匹配则迁移/创建默认"""
        if not self.config_path.exists():
            logger.info(f"配置文件不存在，使用默认配置: {self.config_path}")
            self.config = self.DEFAULT_CONFIG.copy()
            self._save()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # 版本迁移
            version = loaded.get("version", "0.0")
            if version != self.CURRENT_VERSION:
                logger.info(f"配置版本 {version} -> {self.CURRENT_VERSION}，执行迁移")
                loaded = self._migrate(loaded, version)
            self.config = loaded
        except Exception as e:
            logger.error(f"加载配置失败: {e}，使用默认配置")
            self.config = self.DEFAULT_CONFIG.copy()
            self._save()

    def _migrate(self, old_config: Dict, old_version: str) -> Dict:
        """版本迁移：根据版本差异调整配置结构"""
        old_config["version"] = self.CURRENT_VERSION
        # 确保所有顶层字段存在（合并默认值）
        for key, default_value in self.DEFAULT_CONFIG.items():
            if key not in old_config:
                old_config[key] = default_value
        return old_config

    def _save(self):
        """保存当前配置到文件"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.debug(f"配置已保存: {self.config_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def get(self, key: str, default=None):
        """获取配置值，支持点号路径，如 'window.width'"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any, auto_save: bool = True):
        """
        设置配置值，支持点号路径。
        脏检查：值未变则跳过保存。
        """
        keys = key.split('.')
        target = self.config
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        last_key = keys[-1]
        # 脏检查
        if last_key in target and target[last_key] == value:
            return
        target[last_key] = value
        if auto_save:
            self._save()

    def get_all(self) -> Dict:
        """返回整个配置字典（只读副本）"""
        return self.config.copy()

    def reset_to_default(self):
        """重置所有配置为默认值"""
        self.config = self.DEFAULT_CONFIG.copy()
        self._save()
        logger.info("配置已重置为默认")

    def save_window_geometry(self, root):
        """根据 tkinter 窗口保存位置和大小"""
        root.update_idletasks()
        geometry = root.geometry()  # 格式 "widthxheight+x+y"
        parts = geometry.replace('+', 'x').split('x')
        if len(parts) == 4:
            w, h, x, y = parts
            self.set('window.width', int(w))
            self.set('window.height', int(h))
            self.set('window.x', int(x))
            self.set('window.y', int(y))
            maximized = root.state() == 'zoomed'
            self.set('window.maximized', maximized)

    def apply_window_geometry(self, root):
        """将配置应用到 tkinter 窗口"""
        w = self.get('window.width', 1200)
        h = self.get('window.height', 800)
        x = self.get('window.x')
        y = self.get('window.y')
        if x is not None and y is not None:
            root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            root.geometry(f"{w}x{h}")
        if self.get('window.maximized', False):
            root.state('zoomed')
