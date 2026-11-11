# -*- coding: utf-8 -*-
"""自定义标题栏组件 —— 设计稿 v43.333 第五期第 1 项（Tier 1 标题栏）。

设计稿原文：「标题栏减负，把『制作人』换成数据上下文」。
改造前两行文字写的是「云南达利ZPP011生产偏差分析器 v43.348」+「数据源：x | 分析时间：y」
—— 主标题把公司名和产品名挤在一起占 30px 宽，副标题一整行小字糊在一起看不清。

新版按设计稿分四段：
  品牌块（主色圆角方块 + 两行文字：产品名 / 公司产地）│ 竖分隔 │
  数据上下文（本次分析时间 · 数据源）│ 右端（数据源可点=选文件、暗色切换）
版本号从主标题里摘掉，移入底部状态条右侧（低频信息右置）。

「数据源」这颗胶囊做成可点击入口（裴哥定：左栏改成纯导航后，选 Excel 的入口
放标题栏），点击发 ``source_requested``，由 MainWindow 走原来的 _select_input_file。
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)
from PySide6.QtCore import Qt, Signal

from gui_pyside6.themes.tokens import SIZE_PX
from gui_pyside6.utils.icons import get_icon
from utils.theme_manager import Thm

#: 品牌副行（设计稿 brand-text span：公司 · 产地）
BRAND_SUB = "云南达利食品 · 玉溪"
#: 主标题（设计稿：去掉「云南达利」前缀，公司名降为副行）
BRAND_MAIN = "ZPP011 生产偏差分析器"


class TitleBarWidget(QWidget):
    """标题栏：品牌块 + 数据上下文 + 右端入口（设计稿 Tier 1，48px）"""

    theme_toggled = Signal()
    factory_selected = Signal(str)
    #: 点「数据源」胶囊 → 选输入 Excel（MainWindow 接 _select_input_file）
    source_requested = Signal()

    def __init__(self, version: str = "", parent=None):
        super().__init__(parent)
        # QWidget 子类不自己画 QSS 底色，必须显式开这个属性（同 dashboard_shell.py:117）。
        # 改造前标题栏的 #titleBar{background:#FFFFFF} 一直是空规则 —— 实测整窗取色
        # 拿到的是窗口底 #EEF1F6，标题栏和下面内容区糊成一片，设计稿的 Tier 分层根本
        # 显不出来。开属性后同一位置取色才是 #FFFFFF。
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(SIZE_PX["titleBar"])
        self.setObjectName("titleBar")
        self._version = version
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        # 设计稿 .title-bar：padding 0 10px 0 14px，gap 12px
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(SIZE_PX["gridGap"] + 4)

        # ── 品牌块：28×28 主色圆角方块 + 白色工厂标 ──
        self.brand_mark = QLabel()
        self.brand_mark.setFixedSize(28, 28)
        self.brand_mark.setAlignment(Qt.AlignCenter)
        self.brand_mark.setObjectName("titleBrand")
        self.brand_mark.setPixmap(
            get_icon("factory", 15, Thm.color("onPrimary")).pixmap(15, 15))
        layout.addWidget(self.brand_mark, 0, Qt.AlignVCenter)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        self.main_title = QLabel(BRAND_MAIN)
        self.main_title.setObjectName("titleMain")
        brand_text.addWidget(self.main_title)
        self.brand_sub = QLabel(BRAND_SUB)
        self.brand_sub.setObjectName("titleBrandSub")
        brand_text.addWidget(self.brand_sub)
        layout.addLayout(brand_text, 0)

        # ── 竖分隔（1×22）──
        sep = QWidget()
        sep.setFixedSize(1, 22)
        sep.setObjectName("titleSep")
        layout.addWidget(sep, 0, Qt.AlignVCenter)

        # ── 数据上下文：本次分析时间 ──
        ctx = QHBoxLayout()
        ctx.setSpacing(6)
        self.ctx_icon = QLabel()
        self.ctx_icon.setObjectName("titleCtxIcon")
        self.ctx_icon.setPixmap(get_icon("chart", 13, Thm.color("textFaint")).pixmap(13, 13))
        ctx.addWidget(self.ctx_icon, 0, Qt.AlignVCenter)
        ctx_caption = QLabel("本次分析")
        ctx_caption.setObjectName("titleCtx")
        ctx.addWidget(ctx_caption)
        self.ctx_value = QLabel("—")
        self.ctx_value.setObjectName("titleCtxValue")
        ctx.addWidget(self.ctx_value)
        layout.addLayout(ctx, 0)

        layout.addStretch()

        # ── 右端：数据源（可点=选文件）+ 暗色切换 ──
        self.source_btn = QPushButton("数据源  未选择文件")
        self.source_btn.setObjectName("titleSourceBtn")
        self.source_btn.setFixedHeight(28)
        self.source_btn.setCursor(Qt.PointingHandCursor)
        self.source_btn.setIcon(get_icon("menu", 12))
        self.source_btn.setToolTip("点此选择要分析的 Excel 文件")
        self.source_btn.clicked.connect(self.source_requested.emit)
        layout.addWidget(self.source_btn, 0, Qt.AlignVCenter)

        self.theme_btn = QPushButton("暗色")
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.setFixedHeight(28)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self.theme_toggled.emit)
        layout.addWidget(self.theme_btn, 0, Qt.AlignVCenter)

    def set_data_context(self, source_name: str, when: str = ""):
        """刷新数据上下文（设计稿第 1 项）：数据源名 + 本次分析时刻。"""
        self.source_btn.setText("数据源  %s" % (source_name or "未选择文件"))
        self.ctx_value.setText(when or "—")

    def set_theme_light(self):
        """当前是亮色主题：按钮显示'暗色'，品牌块与上下文图标换亮色墨色。"""
        self._repaint_icons()
        self.theme_btn.setIcon(get_icon("moon", 13))
        self.theme_btn.setText("暗色")

    def set_theme_dark(self):
        """当前是暗色主题：按钮显示'亮色'，图标同步换墨色。"""
        self._repaint_icons()
        self.theme_btn.setIcon(get_icon("sun", 13))
        self.theme_btn.setText("亮色")

    def _repaint_icons(self):
        """图标是 QPixmap，QSS 管不到它 —— 主题切换必须在这里重画一次。

        改造前只有品牌块一个图标，且暗色下它一直是亮色墨（#1E40AF 底上的白标看不出
        问题），新增的「本次分析」图标在暗底上会变成一块灰斑，所以按当前主题取色。
        """
        self.brand_mark.setPixmap(
            get_icon("factory", 15, Thm.color("onPrimary")).pixmap(15, 15))
        self.ctx_icon.setPixmap(
            get_icon("chart", 13, Thm.color("textFaint")).pixmap(13, 13))
        for btn, name in ((self.source_btn, "menu"), (self.theme_btn, None)):
            if name:
                btn.setIcon(get_icon(name, 12, Thm.color("textMuted")))
