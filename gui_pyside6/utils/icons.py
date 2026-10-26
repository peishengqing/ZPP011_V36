# -*- coding: utf-8 -*-
"""内联 SVG 线性图标集 — v43.264 起取代全仓 emoji 图标。

设计约定（与 QSS 主题体系配合）：
- 24×24 viewBox、stroke 线性风格（1.8px、round 端点/转角），与「1px 描边卡片」
  的现代扁平语言一致；
- 图标按 (name, color, size) 缓存 QIcon；QSvgRenderer 以 2× 超采样渲染后
  setDevicePixelRatio(2)，高分屏与 100% 缩放下都不糊；
- 默认色为中性暖灰 #8A8A82：亮色主题 (#FAF9F6) 与暗色主题 (#1C1C1A) 上
  都清晰但不抢文字；主色按钮（如「分析」）显式传白色；
- 新增图标只需往 _ICONS 里加一条 path 数据，禁止引入图片文件/图标字体
  （公司网络 DNS 劫持，零外链铁律同样适用于本地资源）。
"""
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, Qt

_DEFAULT_INK = "#8A8A82"

# ── 图标 path 数据（stroke 线性，24×24）──
_ICONS = {
    # 品牌/标题栏
    "factory": "M3 21h18M5 21V10l5 3V10l5 3V10l4 3v8M9 21v-4h3v4",
    "moon": "M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z",
    "sun": ("M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z"
            "M12 2v2.2M12 19.8V22M2 12h2.2M19.8 12H22M4.9 4.9l1.6 1.6M17.5 17.5l1.6 1.6"
            "M19.1 4.9l-1.6 1.6M6.5 17.5l-1.6 1.6"),
    # 操作栏
    "play": "M7 4.5l12 7.5-12 7.5z",
    "panel-left": "M3.5 5h17v14h-17zM9.5 5v14",
    "search": "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM16.2 16.2L21 21",
    "funnel-lines": "M4 6h16M7 12h10M10 18h4",
    "chart": "M6 20V11M12 20V5M18 20v-6M3 20h18",
    "download": "M12 3v12M8 11l4 4 4-4M4 17v4h16v-4",
    "sliders": "M4 7h8M16 7h4M16 5v4M4 17h2M10 17h10M8 15v4",
    "gauge": "M4.5 17a8.5 8.5 0 1 1 15 0M12 14l4.2-4.2",
    "zap": "M13 2.5L4.5 14H11l-1 7.5L18.5 10H12l1-7.5z",
    "megaphone": "M4 10v4h3l7 4V6L7 10H4zM17 9a4 4 0 0 1 0 6",
    "shield": "M12 3l7 3v6c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6l7-3zM9 12l2 2 4-4",
    # 看板菜单
    "bell": "M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6M10 20a2 2 0 0 0 4 0",
    "alert": "M12 4L2.5 20h19L12 4zM12 10v4.2M12 17.3v.3",
    "trending-down": "M3 7l6 6 4-4 8 8M15 17h6v-6",
    "trending-up": "M3 17l6-6 4 4 8-8M15 7h6v6",
    "lock": "M6 11V8a6 6 0 0 1 12 0v3M5 11h14v9H5z",
    "clipboard": "M9 4h6v3H9zM7 6H5v14h14V6h-2M9 12h6M9 16h4",
    "link": "M10 14a4 4 0 0 0 6 .4l3-3a4 4 0 0 0-5.7-5.7L12 7M14 10a4 4 0 0 0-6-.4l-3 3a4 4 0 0 0 5.7 5.7L12 17",
    "box": "M21 8l-9-5-9 5v8l9 5 9-5V8zM3 8l9 5 9-5M12 13v8",
    # 导出/维护菜单
    "file-text": "M6 2h8l5 5v15H6zM14 2v5h5M9 13h6M9 17h6",
    "table": "M3.5 5h17v14h-17zM3.5 10h17M9.5 10v9M15 10v9",
    "id-card": "M3 6h18v12H3zM6 11h4M6 15h3M14 10h4M14 14h4",
    # 侧栏
    "folder": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    "wrench": "M17.5 3.5l3 3-8.6 8.6-3.4.6.6-3.4 8.4-8.8zM14 8l2.5 2.5",
    "pin": "M12 3a5 5 0 0 1 5 5c0 4-5 9-5 9s-5-5-5-9a5 5 0 0 1 5-5zM12 8a1.6 1.6 0 1 0 0-.01",
    "layers": "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5",
    # 通用动作
    "plus": "M12 5v14M5 12h14",
    "edit": "M4 20h4L19 9l-4-4L4 16v4zM14.5 6.5l4 4",
    "trash": "M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13M10 11v6M14 11v6",
    "refresh": "M20 12a8 8 0 1 1-2.3-5.7M20 3.5V8h-4.5",
    "save": "M5 3h12l3 3v15H5V3zM8 3v5h7V3M8 12h8v8H8v-8z",
    "close": "M6 6l12 12M18 6L6 18",
    "check": "M5 12l5 5L20 7",
    "circle": "M12 4.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15z",
}

_SVG_TMPL = ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
             'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
             'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')

_icon_cache = {}


def icon_svg(name: str, color: str = _DEFAULT_INK) -> str:
    """取图标的 SVG 源码（着色后的完整 XML）。"""
    paths = _ICONS.get(name)
    if paths is None:
        raise KeyError(f"未知图标: {name}（可用: {sorted(_ICONS)}）")
    return _SVG_TMPL.format(w=24, h=24, color=color, paths=paths)


def get_icon(name: str, size: int = 16, color: str = None) -> QIcon:
    """渲染线性图标为 QIcon（2× 超采样，按 (name,color,size) 缓存）。

    color 传 None 用默认中性墨色；主色按钮上传 "#FFFFFF"。
    """
    color = color or _DEFAULT_INK
    key = (name, color, size)
    cached = _icon_cache.get(key)
    if cached is not None:
        return cached

    svg = icon_svg(name, color).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(svg))
    px = QPixmap(size * 2, size * 2)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    renderer.render(painter)
    painter.end()
    px.setDevicePixelRatio(2.0)
    icon = QIcon(px)
    _icon_cache[key] = icon
    return icon


def has_icon(name: str) -> bool:
    """图标名是否存在（供测试/调用方探测）。"""
    return name in _ICONS
