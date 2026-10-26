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
    # ── v43.266 补齐：底部工具条 / 菜单 / 状态栏用 ──
    "maximize": "M4 9V4h5M20 15v5h-5M20 9V4h-5M4 15v5h5",
    "minimize": "M9 4v5H4M15 20v-5h5M15 4v5h5M9 20v-5H4",
    "eye": "M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12z"
           "M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
    "unlock": "M6 11V8a6 6 0 0 1 11.5-2M5 11h14v9H5z",
    "clock": "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 7.5V12l3 2",
    "timer": "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 8v4.5M9.5 2h5",
    "book": "M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5zM4 5.5v15",
    "scroll": "M6 3h9l4 4v14H6zM15 3v4h4M9 12h7M9 16h7",
    "gear": "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"
            "M12 2.5l1.3 2.2 2.5-.6.6 2.5 2.2 1.3-1 2.3 1 2.3-2.2 1.3-.6 2.5-2.5-.6L12 21.5l-1.3-2.2-2.5.6-.6-2.5L5.4 16l1-2.3-1-2.3 2.2-1.3.6-2.5 2.5.6z",
    "exchange": "M4 8h13l-3-3M20 16H7l3 3",
    "sparkles": "M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6zM18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z",
    "chevron-down": "M6 9.5l6 6 6-6",
    "chevron-up": "M6 14.5l6-6 6 6",
    "chevron-left": "M14.5 6l-6 6 6 6",
    "chevron-right": "M9.5 6l6 6-6 6",
    "check-circle": "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM8 12.2l2.8 2.8L16 9.5",
    "close-circle": "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM9 9l6 6M15 9l-6 6",
    "paperclip": "M20 11.5l-8.2 8.2a5 5 0 0 1-7-7l8.5-8.5a3.5 3.5 0 0 1 5 5L9.7 17.7a2 2 0 0 1-2.8-2.8l7.8-7.8",
    "folder-open": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H3zM3 10h18l-2 8H5z",
    "undo": "M9 8H4V3M4.5 8.5A8 8 0 1 1 6 18",
    "menu": "M4 7h16M4 12h16M4 17h16",
    "tag": "M3 11V4h7l11 11-7 7L3 11zM7.5 7.5h.01",
    "flag": "M6 21V4M6 4h12l-2.5 4L18 12H6",
}

_SVG_TMPL = ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
             'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
             'stroke-linecap="round" stroke-linejoin="round">'
             '<path d="{paths}"/></svg>')

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


# ══════════════════════════════════════════════════════════════════
# v43.266：emoji → 线性图标 映射 + 按钮/菜单工厂
# 背景：裴哥截图指出底部工具条的 🔒/⛶/👁 三个「纯符号按钮」在
# Microsoft YaHei 字体下回退成了怪字形（油漆桶/四点/i）。纯符号按钮
# 尤其明显——emoji 撑满 32px 按钮，一眼看不出是什么。
# 做法：按钮/菜单项统一走 make_button / make_tool_button / add_icon_action，
# 由工厂自动剥掉文本里的 emoji 前缀并挂上对应 SVG 图标。
# ══════════════════════════════════════════════════════════════════
EMOJI_TO_ICON = {
    "➕": "plus", "⭕": "circle", "⛶": "maximize", "🗑": "trash", "✕": "close",
    "🔍": "search", "✓": "check", "🔧": "wrench", "📋": "clipboard", "🔄": "refresh",
    "🕒": "clock", "⏱": "timer", "📖": "book", "🔽": "funnel-lines", "🪪": "tag",
    "📜": "scroll", "⚡": "zap", "🔒": "lock", "👁": "eye", "⚙": "gear",
    "🔔": "bell", "⇄": "exchange", "✨": "sparkles", "🔘": "circle", "✎": "edit",
    "✏": "edit", "💾": "save", "❌": "close-circle", "📦": "box", "📂": "folder-open",
    "✅": "check-circle", "📎": "paperclip", "⚠": "alert", "⚠️": "alert",
    "↩": "undo", "☰": "menu", "🎉": "check", "🔓": "unlock", "🖨": "print",
    "🗑️": "trash", "✏️": "edit", "❌": "close-circle",
}


def split_emoji(text: str):
    """把「emoji 前缀 + 文字」拆成 (图标名, 纯文字)。

    无 emoji 前缀时返回 (None, 原文本)。emoji 不在映射表里时保留原样
    （宁可留个 emoji，也不要静默丢信息）。
    """
    if not text:
        return None, text
    stripped = text.lstrip()
    for ch in stripped:
        if ch.isspace():
            continue
        icon = EMOJI_TO_ICON.get(ch)
        if icon:
            return icon, stripped[len(ch):].lstrip()
        break
    return None, text


def make_button(text: str, size: int = 14, parent=None):
    """QPushButton 工厂：自动剥 emoji 前缀 + 挂 SVG 图标。

    替代写法：`make_button("📎 导出 Excel")` → `make_button("📎 导出 Excel")`。
    文本里没有 emoji 时行为与 QPushButton 完全一致（不挂图标）。
    """
    from PySide6.QtWidgets import QPushButton
    icon, clean = split_emoji(text)
    btn = QPushButton(clean, parent)
    if icon:
        btn.setIcon(get_icon(icon, size))
    return btn


def make_tool_button(text: str, size: int = 14, parent=None):
    """QToolButton 工厂（同 make_button）。"""
    from PySide6.QtWidgets import QToolButton
    icon, clean = split_emoji(text)
    btn = QToolButton(parent)
    btn.setText(clean)
    if icon:
        btn.setIcon(get_icon(icon, size))
        from PySide6.QtCore import Qt
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    return btn


def add_icon_action(menu, text: str, handler=None, size: int = 14):
    """菜单项工厂：自动剥 emoji 前缀 + 挂 SVG 图标（v43.266 统一入口）。"""
    from PySide6.QtGui import QAction
    icon, clean = split_emoji(text)
    act = QAction(get_icon(icon, size) if icon else None, clean, menu)
    if handler is not None:
        act.triggered.connect(handler)
    menu.addAction(act)
    return act
