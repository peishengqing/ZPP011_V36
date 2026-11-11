# -*- coding: utf-8 -*-
"""
主题管理器单例（治本方案）
提供全局唯一的主题状态和颜色映射，所有 UI 组件从此读取，不再各自猜 palette。
"""
from typing import Callable, Optional
from dataclasses import dataclass

# 单例实例
_Instance: Optional["ThemeManager"] = None


@dataclass
class _ThemeConfig:
    """UI 颜色配置（亮/暗两套）"""
    # 基础背景
    bg: str
    surface: str
    # 文字
    text_primary: str
    text_secondary: str
    # 品牌色（主色，明暗通用）
    primary: str
    # 边框、分割线
    border: str
    # 表格交替行
    table_alternate: str
    # 高亮/选中
    highlight: str
    #  드래그/悬停
    hover: str


# 两套静态配置（直接映射到 QSS hex）
_LIGHT_CONFIG = _ThemeConfig(
    bg="#FFFFFF",
    surface="#FFFFFF",
    text_primary="#1F2937",
    text_secondary="#6B7280",
    primary="#0969DA",
    border="#E2E8F0",
    table_alternate="#F8FAFC",
    highlight="#E0F2FE",
    hover="#F1F5F9",
)

_DARK_CONFIG = _ThemeConfig(
    bg="#1E1E24",
    surface="#25262B",
    text_primary="#E9ECEF",
    text_secondary="#9AA7B6",
    primary="#5C7CFA",
    border="#2C2E33",
    table_alternate="#2C2E33",
    highlight="#454D60",
    hover="#3A4050",
)


class ThemeManager:
    """主题管理器单例"""

    def __init__(self) -> None:
        self._is_dark: bool = False
        self._callbacks: list[Callable[[bool], None]] = []

    def set_dark(self, dark: bool) -> None:
        if self._is_dark == dark:
            return
        self._is_dark = dark
        for cb in self._callbacks[:]:  # 复制列表避免修改中迭代
            try:
                cb(dark)
            except Exception:
                pass  # 忽略回调中的错误，避免一个回调失败影响其他

    def toggle(self) -> None:
        self.set_dark(not self._is_dark)

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def on_change(self, cb: Callable[[bool], None]) -> None:
        self._callbacks.append(cb)

    def unregister(self, cb: Callable[[bool], None]) -> None:
        try:
            self._callbacks.remove(cb)
        except ValueError:
            pass

    def get_config(self) -> _ThemeConfig:
        return _DARK_CONFIG if self._is_dark else _LIGHT_CONFIG

    def get_color(self, name: str) -> Optional[str]:
        try:
            return getattr(self.get_config(), name)
        except AttributeError:
            return None


def get_theme_manager() -> ThemeManager:
    """获取主题管理器单例"""
    global _Instance
    if _Instance is None:
        _Instance = ThemeManager()
    return _Instance


# 全局实例（供直接导入使用）
Thm = get_theme_manager()
