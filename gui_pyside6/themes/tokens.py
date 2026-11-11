# -*- coding: utf-8 -*-
"""设计令牌唯一真源 · design-tokens（设计稿 v43.333 第五章 5.1/5.2/5.3）

为什么要有这个文件
------------------
改造前全项目有 **5 份各自写死的颜色真源**，同一个「主色」存在 4 个值：

  1. gui_pyside6/light_theme.qss / dark_theme.qss   → #1E40AF / #4C7DFF（设计稿值）
  2. widgets/board_visual.py  BOARD_QSS             → #0969da（GitHub 蓝，写死浅色）
  3. components/dashboard_shell.py 兜底 QSS         → #0969DA / #5C7CFA
  4. gui_pyside6/themes/{light,dark}_dashboard.qss  → #1E40AF / #4C7DFF
  5. utils/theme_manager.py  _LIGHT/_DARK_CONFIG    → #0969DA / #5C7CFA（且零调用方）

设计稿第一期第 1 条要求「抽出 design-tokens 单一真源」，本文件即该真源。
**任何 QSS / 颜色常量都不得再写死 hex**，一律从本文件取。

对外提供
--------
- ``TOKENS[light|dark]``      语义令牌表（5.1 颜色 + 5.2 字号 + 5.3 尺寸）
- ``build_dashboard_qss(t)``  DashboardShell 外壳 QSS（唯一生成处）
- ``build_board_qss(t)``      表格看板 dialog 级 QSS（原 BOARD_QSS，改为主题感知）
- ``build_theme_manager_configs()``  给 utils/theme_manager.py 派生 _LIGHT/_DARK_CONFIG

红线（照旧遵守，见 board_visual.py v43.299 / v43.343 尺寸纪律）
--------------------------------------------------------------
筛选栏里的 QPushButton / QComboBox / QLineEdit **只写颜色类属性**：
不写 padding / margin / border / border-radius / min-width / font-size。
Qt 一旦看到这些尺寸属性就改走 stylesheet 路径重算 sizeHint
（offscreen 实测：按钮 80x20→58x29、下拉 54x22→178x30），
而顶部筛选栏宽度是 v43.139/143/154 逐像素精算过的，尺寸一变就挤压重叠。
圆角/边框只允许用在「不进布局」的独立悬浮按钮，以及表格/表头/滚动条上。

同样照旧的红线：
- 禁止裸 ``QFrame { color: ... }``（QTableView/QLabel/QScrollArea 都是 QFrame 子类，
  同特异性后者胜，会把表格数据冲成浅色；v43.299 量化实测深色像素 7.27%→0.00%）。
- QSS 选择器必须带 ID 前缀保特异性（裸 ``QPushButton#id`` 会输给
  ``QDialog#id QPushButton``）。

重生成 .qss 文件（供审阅/外部工具，运行时不读取）::

    python -m gui_pyside6.themes.tokens
"""

from __future__ import annotations

import os

# ==========================================================================
#  5.1 颜色 + 5.2 字号 + 5.3 尺寸
# ==========================================================================

_LIGHT = {
    # 结构
    "bg": "#EEF1F6",
    "surface": "#FFFFFF",
    "surface2": "#F5F8FC",
    "surface3": "#E9EEF5",
    "border": "#DBE2EC",
    "borderStrong": "#C0CCDA",
    # 文字
    "text": "#101828",
    "textMuted": "#5A6B82",
    "textFaint": "#8595AA",
    # 主色（纪律：只允许出现在主按钮、选中态、焦点环、链接四处）
    "primary": "#1E40AF",
    "primaryHover": "#1E3A8A",
    "primaryActive": "#1A3478",
    "primarySoft": "#E7EDFB",
    "primarySoftBd": "#C3D3F4",
    # 主色实底之上的前景（按钮文字、选中数字）。亮/暗同值，靠主色本身拉开对比。
    "onPrimary": "#FFFFFF",
    # 语义色（纪律：只允许出现在 6px 圆点、状态胶囊、accent 条三处）
    "ok": "#0E8F63", "okSoft": "#E3F5EE",
    # 实底语义按钮（「AI 分析」这类整块填色的主操作）。设计稿 5.1 只给了文字/胶囊
    # 两档，而 Qt QSS 没有 CSS 的 brightness()，hover 变深必须有显式取值，故补此档。
    "okSolid": "#0E8F63", "okSolidHover": "#0B7355",
    "warn": "#C2740B", "warnSoft": "#FDF3E3",
    "danger": "#C62A2A", "dangerSoft": "#FBEAEA",
    "info": "#2563EB", "infoSoft": "#E8F0FE",
    "violet": "#6D28D9", "violetSoft": "#EFE9FD",
}

_DARK = {
    "bg": "#0B1220",
    "surface": "#121A2B",
    "surface2": "#182136",
    "surface3": "#1E2A42",
    "border": "#253148",
    "borderStrong": "#35455F",
    "text": "#E6EDF7",
    "textMuted": "#9AA9BF",
    "textFaint": "#6E7E96",
    "primary": "#4C7DFF",
    "primaryHover": "#6B93FF",
    "primaryActive": "#3A66E8",
    "primarySoft": "#18254A",
    "primarySoftBd": "#2B3E6E",
    "onPrimary": "#FFFFFF",
    "ok": "#3FBF8F", "okSoft": "#0E2C22",
    # 暗色下 #3FBF8F 是「文字/圆点」档，直接当实底按钮会顶掉白字对比度，
    # 因此实底按钮单列一档更深的绿（同 light 侧的理由：QSS 没有 brightness()）。
    "okSolid": "#116B4E", "okSolidHover": "#178A64",
    "warn": "#E0A33C", "warnSoft": "#33270F",
    "danger": "#F26D6D", "dangerSoft": "#331A1A",
    "info": "#60A5FA", "infoSoft": "#15243F",
    "violet": "#A78BFA", "violetSoft": "#231C42",
}

#: 语义令牌表。``TOKENS["light"]`` / ``TOKENS["dark"]``
TOKENS = {"light": _LIGHT, "dark": _DARK}

# ---- 5.2 字体 ----
# Qt 的 setPixelSize 只收整数，设计稿的 12.5 / 13.5 / 16.5 在此就近取整；
# 观感差异 < 0.5px，不值得为此换成缩放绘制。
FONT_UI = '"Segoe UI","Microsoft YaHei UI","Microsoft YaHei"'
FONT_NUM = '"Cascadia Mono","Consolas"'
FONT_PT = {
    "label": 11,       # 设计稿 10.5
    "aux": 11,
    "note": 12,
    "body": 13,        # 设计稿 12.5
    "heading": 14,     # 设计稿 13.5
    "kpi": 17,         # 设计稿 16.5
    "verdict": 22,
}

# ---- 5.3 尺寸（px）----
SIZE_PX = {
    "titleBar": 48,
    "actionBar": 44,        # 主界面操作栏
    "boardFilterBar": 40,   # 看板常驻筛选条
    "boardKpiBar": 54,      # 看板 KPI 带
    "boardActBar": 40,      # 看板底部操作条
    "navPanel": 236,
    "tableRow": 36,
    "tableHeader": 32,
    "statusBar": 30,
    "cardPad": 12,
    "gridGap": 8,
    "radiusSm": 4,
    "radiusMd": 6,
    "radiusLg": 10,
    "radiusPill": 18,     # 悬浮胶囊按钮（高 36 的一半），设计稿 .pill 同源
}

#: 弹窗尺寸规范（设计稿 4.4）：名称 → (宽, 高)
DIALOG_SIZES = {
    "small": (420, 520),    # 小表单
    "medium": (720, 560),   # 中表单
    "large": (960, 640),    # 大型分析
    "board": (1440, 900),   # 看板（可最大化）
}


def t(theme: str, key: str) -> str:
    """取一个颜色令牌值。theme: 'light' | 'dark'。"""
    try:
        return TOKENS[theme][key]
    except KeyError:
        raise KeyError(
            "未知颜色令牌 %r（theme=%r）。可用键：%s"
            % (key, theme, ", ".join(sorted(TOKENS[theme])))
        ) from None


def theme_of(is_dark: bool) -> str:
    return "dark" if is_dark else "light"


def _families(spec: str) -> list:
    """'"A","B"' → ['A', 'B']，供 QFont.setFamilies 使用。"""
    return [f.strip().strip('"') for f in spec.split(",") if f.strip()]


def ui_font(pt_size: int = None, bold: bool = False):
    """正文字体（FONT_UI 家族）。字号一律走 FONT_PT 档位，不要就地写数字；
    pt_size=None 表示「不设字号、继承控件/表格当前字号」。"""
    from PySide6.QtGui import QFont
    f = QFont()
    f.setFamilies(_families(FONT_UI))
    if pt_size is not None:
        f.setPixelSize(pt_size)
    f.setBold(bold)
    return f


def num_font(pt_size: int = None, bold: bool = False):
    """数字/编码字体（FONT_NUM 家族 + 等宽数字）。

    改造前 KPI 值、表格数字列各自写死 QFont("Cascadia Mono", 17) /
    QFont("Consolas", 10)，字号还不在设计稿阶梯上；统一由此处发。
    """
    from PySide6.QtGui import QFont
    f = QFont()
    f.setFamilies(_families(FONT_NUM))
    if pt_size is not None:
        f.setPixelSize(pt_size)
    f.setBold(bold)
    try:
        f.setFontVariants({"tnum": True})   # tabular-nums，列对齐不抖
    except Exception:
        pass
    return f


# ==========================================================================
#  QSS 生成
# ==========================================================================

def build_dashboard_qss(theme: str) -> str:
    """DashboardShell 外壳 QSS —— 全项目唯一生成处，themes/*_dashboard.qss 由此落盘。

    尺寸纪律：常驻筛选条里的 QPushButton / QToolButton / QComboBox / QLineEdit /
    QSpinBox 只写颜色；只有抽屉（QGroupBox）、表格与 KPI 卡可以用边框/圆角/内距。
    """
    c = TOKENS[theme]
    return """/* 由 gui_pyside6/themes/tokens.py 生成 · 请勿手改，改令牌请改 tokens.py
 *
 * 尺寸纪律（v43.343 红线）：筛选栏里的 QPushButton / QComboBox / QLineEdit
 * 只写颜色类属性，绝不写 padding / border / border-radius / min-width / font-size，
 * 否则 Qt 重算 sizeHint（按钮 80x20→58x29、下拉 54x22→178x30），
 * 顶部筛选栏逐像素精算的宽度会被挤压重叠。
 * 表格 / 表头 / 滚动条不在筛选栏内，可安全用边框与圆角。
 */
#DashboardShell {{ background: {bg}; }}
#title_bar {{ background: {surface}; border-bottom: 1px solid {border}; }}
#filter_bar {{ background: {surface}; border-bottom: 1px solid {border}; }}
#kpi_bar {{ background: {surface}; border-bottom: 1px solid {border}; }}
#action_bar {{ background: {surface}; border-top: 1px solid {border}; }}
#content {{ background: {surface}; }}
#status_bar {{ background: {surface2}; border-top: 1px solid {border}; }}
#drawer_container {{ background: {surface2}; }}

/* 按钮：只写颜色。筛选区是 checkable 按钮，:checked 用主色实底标出当前档位。 */
QPushButton {{
    background-color: {surface};
    color: {textMuted};
}}
QPushButton:hover    {{ background-color: {primarySoft}; color: {primaryHover}; }}
QPushButton:pressed  {{ background-color: {primarySoftBd}; }}
QPushButton:checked  {{ background-color: {primary}; color: {onPrimary}; }}
QPushButton:disabled {{ background-color: {surface3}; color: {textFaint}; }}

/* 工具按钮同样只写颜色（外壳标题条/筛选条里的 导出/全屏/关闭/筛选 都算筛选控件）。 */
QToolButton {{
    background-color: {surface2};
    color: {textMuted};
}}
QToolButton:hover {{ background-color: {primarySoft}; color: {primaryHover}; }}
QToolButton:pressed {{ background-color: {primarySoftBd}; }}
QToolButton:checked {{ background-color: {primary}; color: {onPrimary}; }}
QToolButton:disabled {{ background-color: {surface3}; color: {textFaint}; }}

/* 标签 */
QLabel {{ color: {text}; }}
QLabel[class="mutedText"] {{ color: {textMuted}; font-size: {f_note}px; }}

/* 下拉：只写颜色；刻意不写 ::drop-down，一旦接管该子控件 Qt 就不再画原生箭头。
   弹出列表 QAbstractItemView 不占筛选栏布局，可保留边框。 */
QComboBox {{
    background-color: {surface};
    color: {text};
    selection-background-color: {primarySoft};
    selection-color: {primary};
}}
QComboBox:hover {{ background-color: {surface2}; }}
QComboBox QAbstractItemView {{
    background-color: {surface};
    border: 1px solid {border};
    selection-background-color: {primarySoft};
    selection-color: {primary};
}}

/* 输入框 / 数字框：只写颜色（数字框同样不写 ::up-button，理由同下拉箭头） */
QLineEdit, QSpinBox, QDateEdit {{
    background-color: {surface};
    color: {text};
    selection-background-color: {primary};
    selection-color: {onPrimary};
}}
QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {{ background-color: {surface2}; }}

/* KPI 带的横向滚动容器：只负责去掉边框与滚动条，不负责配色 */
QScrollArea#kpiScroll {{ border: none; background: transparent; }}

/* 标题条右侧窗口按钮（导出/全屏/关闭）：幽灵样式，不参与筛选条精算 */
QPushButton#titleToolBtn {{ background: transparent; color: {textMuted}; }}
QPushButton#titleToolBtn:hover {{ background-color: {surface3}; color: {text}; }}

/* 品牌块：26×26 装饰方块，不进配色纪律范围，允许渐变与圆角 */
QFrame#tb_mark {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 {primary}, stop:1 {primaryHover});
    border-radius: {r_md}px;
}}

/* 抽屉里的命中计数徽章（胶囊）：抽屉不在筛选条精算范围内 */
QLabel#hitBadge {{
    color: {primary};
    background: {primarySoft};
    border: 1px solid {primarySoftBd};
    border-radius: {r_pill}px;
    padding: 0 5px;
    min-width: 35px;
    font-size: {f_aux}px;
    font-weight: 600;
}}

/* 抽屉里的分组卡：不在精算过的筛选条内，可安全用边框/圆角/内边距 */
QGroupBox {{
    color: {text};
    background: {surface};
    border: 1px solid {border};
    border-radius: {r_md}px;
    margin-top: 12px;
    padding: {pad}px;
    font-size: {f_body}px;
    font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}

/* KPI 卡：整块只允许 1px 左分隔线 + hover 换底，禁止投影/大面积填色 */
QWidget[kpiCard="1"] {{
    background: transparent;
    border-left: 1px solid {border};
}}
QWidget[kpiCard="1"]:hover {{ background: {surface2}; }}
QLabel[kpiLabel="1"] {{
    color: {textMuted};
    font-family: {font_ui};
    font-size: {f_aux}px;
}}
QLabel[kpiValue="1"] {{
    font-family: {font_num};
    font-size: {f_kpi}px;
    font-weight: 600;
}}
QLabel[kpiValue="1"][status="ok"]     {{ color: {ok}; }}
QLabel[kpiValue="1"][status="warn"]   {{ color: {warn}; }}
QLabel[kpiValue="1"][status="danger"] {{ color: {danger}; }}
QLabel[kpiValue="1"][status="info"]   {{ color: {info}; }}
QLabel[kpiValue="1"][status="violet"] {{ color: {violet}; }}

/* 表格：看板实际用 QTableView + DataFrameModel（QTableWidget 选择器从未命中，已删） */
QTableView {{
    background-color: {surface};
    alternate-background-color: {surface2};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: {r_sm}px;
    selection-background-color: {primarySoft};
    selection-color: {text};
}}
QHeaderView::section {{
    background-color: {surface2};
    color: {textMuted};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {borderStrong};
    font-weight: bold;
}}
QHeaderView::section:hover {{ background-color: {surface3}; }}

/* 滚动条 */
QScrollBar:vertical {{
    background: {bg};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {borderStrong};
    border-radius: {r_sm}px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {primarySoftBd}; }}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{ background: transparent; }}

/* 语义色（5.1 纪律：只允许出现在 6px 圆点、状态胶囊、accent 条三处）
   供 objectName / dynamic property 挂钩，大面积填充一律禁止 */
QLabel[status="ok"]     {{ color: {ok}; }}
QLabel[status="warn"]   {{ color: {warn}; }}
QLabel[status="danger"] {{ color: {danger}; }}
QLabel[status="info"]   {{ color: {info}; }}
QLabel[status="violet"] {{ color: {violet}; }}
/* 偏差率双编码：颜色 + 数值，色觉障碍用户不丢信息（红线 6） */
QLabel[devrate="neg"]   {{ color: {danger}; font-weight: 600; }}
QLabel[devrate="pos"]   {{ color: {ok}; font-weight: 600; }}
""".format(
        bg=c["bg"], surface=c["surface"], surface2=c["surface2"], surface3=c["surface3"],
        border=c["border"], borderStrong=c["borderStrong"],
        text=c["text"], textMuted=c["textMuted"], textFaint=c["textFaint"],
        primary=c["primary"], primaryHover=c["primaryHover"],
        primarySoft=c["primarySoft"], primarySoftBd=c["primarySoftBd"],
        onPrimary=c["onPrimary"],
        r_sm=SIZE_PX["radiusSm"], r_md=SIZE_PX["radiusMd"], r_pill=SIZE_PX["radiusPill"],
        pad=SIZE_PX["cardPad"],
        font_ui=FONT_UI, font_num=FONT_NUM,
        f_aux=FONT_PT["aux"], f_note=FONT_PT["note"], f_body=FONT_PT["body"],
        f_kpi=FONT_PT["kpi"],
        ok=c["ok"], warn=c["warn"], danger=c["danger"], info=c["info"], violet=c["violet"],
    )


def build_board_qss(theme: str) -> str:
    """表格看板 dialog 级 QSS（原 ``board_visual.BOARD_QSS``）—— 改为主题感知。

    改造前这段只有浅色值（#f4f7fb 白底 + #0969da 蓝），是设计稿诊断 D1
    「主窗口切暗色后看板依然亮」的直接根源；v43.344 的临时办法是
    「暗色时不加载它」，属于绕行。现在暗色有对应取值，绕行可以拆掉。

    作用域仍锁 ``QDialog#zppBoardDialog`` 后代选择器，不污染主窗口全局主题。
    选择器特异性纪律不变：悬浮按钮必须写
    ``QDialog#zppBoardDialog QPushButton#zppVisualBtn``（2 ID + 2 元素），
    否则会输给 ``QDialog#zppBoardDialog QPushButton``（1 ID + 2 元素）而变白底。
    """
    c = TOKENS[theme]
    return """/* 由 tokens.build_board_qss() 生成 · 主题感知（设计稿第一期第 2 条） */
QDialog#zppBoardDialog {{ background-color: {bg}; }}

QDialog#zppBoardDialog QLabel {{ color: {textMuted}; }}
QDialog#zppBoardDialog QLabel[class="mutedText"] {{ color: {textFaint}; }}

QDialog#zppBoardDialog QScrollArea {{ background-color: {surface}; }}

/* 筛选控件：只改颜色，零 sizeHint 影响（红线） */
QDialog#zppBoardDialog QComboBox,
QDialog#zppBoardDialog QLineEdit {{
    background-color: {surface};
    color: {text};
    selection-background-color: {primary};
    selection-color: {onPrimary};
}}
QDialog#zppBoardDialog QComboBox:focus,
QDialog#zppBoardDialog QLineEdit:focus {{ background-color: {surface2}; }}

QDialog#zppBoardDialog QPushButton {{
    background-color: {surface};
    color: {textMuted};
}}
QDialog#zppBoardDialog QPushButton:hover {{
    background-color: {primarySoft};
    color: {primaryHover};
}}
QDialog#zppBoardDialog QPushButton:pressed {{ background-color: {primarySoftBd}; }}
QDialog#zppBoardDialog QPushButton:checked {{
    background-color: {primary};
    color: {onPrimary};
}}
QDialog#zppBoardDialog QPushButton:disabled {{
    color: {textFaint};
    background-color: {surface3};
}}

QDialog#zppBoardDialog QCheckBox {{ color: {textMuted}; }}
QDialog#zppBoardDialog QGroupBox {{ background-color: {surface2}; }}
/* 🔴 禁止在此处新增裸 `QFrame {{ color: ... }}`：QTableView / QLabel / QScrollArea
   全是 QFrame 子类，且规则排在它们之后（同特异性后者胜），会把表格数据与标签
   文字一并冲成浅色。v43.299 量化对照实测：深色像素占比 7.27% → 0.00%。 */

/* 表格不在筛选栏内，可安全用圆角/边框 */
QDialog#zppBoardDialog QTableView {{
    background-color: {surface};
    alternate-background-color: {surface2};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: {r_md}px;
    selection-background-color: {primarySoft};
    selection-color: {text};
}}
QDialog#zppBoardDialog QHeaderView::section {{
    background-color: {surface2};
    color: {textMuted};
    border: none;
    border-right: 1px solid {border};
    border-bottom: 2px solid {borderStrong};
}}
QDialog#zppBoardDialog QHeaderView::section:hover {{ background-color: {surface3}; }}

QDialog#zppBoardDialog QScrollBar:vertical {{
    background: {bg};
    width: 9px;
    margin: 0;
}}
QDialog#zppBoardDialog QScrollBar::handle:vertical {{
    background: {borderStrong};
    border-radius: {r_sm}px;
    min-height: 24px;
}}
QDialog#zppBoardDialog QScrollBar::handle:vertical:hover {{ background: {primarySoftBd}; }}
QDialog#zppBoardDialog QScrollBar::add-line:vertical,
QDialog#zppBoardDialog QScrollBar::sub-line:vertical {{ height: 0; }}
QDialog#zppBoardDialog QScrollBar::add-page:vertical,
QDialog#zppBoardDialog QScrollBar::sub-page:vertical {{ background: transparent; }}

/* 悬浮按钮：独立 child，不进任何 layout，可安全用渐变/圆角/内边距 + 投影。
   选择器必须带 QDialog#zppBoardDialog 前缀（特异性红线，见函数 docstring）。 */
QDialog#zppBoardDialog QPushButton#zppVisualBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {primary}, stop:1 {primaryHover});
    color: {onPrimary};
    border: none;
    border-radius: {r_pill}px;
    padding: 8px 18px;
    font-weight: bold;
}}
QDialog#zppBoardDialog QPushButton#zppVisualBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {primaryHover}, stop:1 {primaryActive});
}}
QDialog#zppBoardDialog QPushButton#zppVisualBtn:pressed {{
    background-color: {primaryActive};
}}
/* checked/disabled 通用规则也会命中悬浮按钮，显式覆盖回主色底白字 */
QDialog#zppBoardDialog QPushButton#zppVisualBtn:disabled {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {primary}, stop:1 {primaryHover});
    color: {onPrimary};
}}
""".format(
        bg=c["bg"], surface=c["surface"], surface2=c["surface2"], surface3=c["surface3"],
        border=c["border"], borderStrong=c["borderStrong"],
        text=c["text"], textMuted=c["textMuted"], textFaint=c["textFaint"],
        primary=c["primary"], primaryHover=c["primaryHover"], primaryActive=c["primaryActive"],
        primarySoft=c["primarySoft"], primarySoftBd=c["primarySoftBd"],
        onPrimary=c["onPrimary"],
        r_sm=SIZE_PX["radiusSm"], r_md=SIZE_PX["radiusMd"], r_pill=SIZE_PX["radiusPill"],
    )


def build_theme_manager_configs():
    """给 utils/theme_manager.py 派生 (light_cfg, dark_cfg)，消灭第 5 份真源。

    字段名沿用 _ThemeConfig 现有定义，避免改动那个类的公开 API。
    ``hover`` 原值在暗色下是 #3A4050（游离于设计稿之外），统一收进 surface3。
    """
    out = []
    for name in ("light", "dark"):
        c = TOKENS[name]
        out.append({
            "bg": c["surface"],               # 外壳底：沿用原语义（原 #FFFFFF / #1E1E24）
            "surface": c["surface"],
            "text_primary": c["text"],
            "text_secondary": c["textMuted"],
            "primary": c["primary"],
            "border": c["border"],
            "table_alternate": c["surface2"],
            "highlight": c["primarySoft"],
            "hover": c["surface3"],
        })
    return out[0], out[1]


# ==========================================================================
#  落盘产物（供人工审阅 / 冒烟脚本读取；运行时内容与此逐字一致）
# ==========================================================================

_OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def write_qss_files() -> list:
    paths = []
    for theme in ("light", "dark"):
        p = os.path.join(_OUT_DIR, "%s_dashboard.qss" % theme)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(build_dashboard_qss(theme))
        paths.append(p)
    return paths


if __name__ == "__main__":
    for path in write_qss_files():
        print("已重生成:", path)
