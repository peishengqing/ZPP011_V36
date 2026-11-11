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
    # 品牌色（主色）
    primary: str
    # 边框、分割线
    border: str
    # 表格交替行
    table_alternate: str
    # 高亮/选中
    highlight: str
    # 悬停
    hover: str


# 两套配置由设计令牌唯一真源派生（gui_pyside6/themes/tokens.py）。
# 这里**不再写死任何 hex**：改造前本文件自带 #0969DA / #5C7CFA 两个主色，
# 与 light/dark_theme.qss 的 #1E40AF / #4C7DFF、board_visual 的 #0969da 并存，
# 是「同一个软件三种蓝」的第 5 个真源（且 get_config/get_color 全项目零调用方，
# 所以从没人在意过它和设计稿不一致）。
# 新增界面代码请优先直接用 tokens.TOKENS；本类的 get_color 仅作兼容保留。
from gui_pyside6.themes.tokens import build_theme_manager_configs

_LIGHT_CFG, _DARK_CFG = build_theme_manager_configs()
_LIGHT_CONFIG = _ThemeConfig(**_LIGHT_CFG)
_DARK_CONFIG = _ThemeConfig(**_DARK_CFG)


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

    def color(self, token_key: str) -> str:
        """按当前主题取一个设计令牌色值（#RRGGBB 串）。

        画布绘制（QPainter / QIcon 上色 / 富文本 HTML）拿不到 QSS，只能显式取色；
        改造前这些地方各自写死 #0078D4 / #4CAF50 / #8A8A82 等游离色，暗色主题下
        就是一块块错色。一律走这里，颜色真源仍只有 tokens.py 一份。
        """
        from gui_pyside6.themes.tokens import t, theme_of
        return t(theme_of(self._is_dark), token_key)

    def qcolor(self, token_key: str):
        from PySide6.QtGui import QColor
        return QColor(self.color(token_key))


def get_theme_manager() -> ThemeManager:
    """获取主题管理器单例"""
    global _Instance
    if _Instance is None:
        _Instance = ThemeManager()
    return _Instance


# 全局实例（供直接导入使用）
Thm = get_theme_manager()
