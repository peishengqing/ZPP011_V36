# -*- coding: utf-8 -*-
"""自定义标题栏组件 — 仿 Tkinter 旧版深蓝标题栏
左侧蓝色竖条 + 🏭 图标 + 主标题/副标题 + 主题切换
"""
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QComboBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class TitleBarWidget(QWidget):
    """品牌化深蓝标题栏（仿 Tkinter 旧版 header）

    v43.128：补上工厂选择器。此前本类只有 theme_toggled 与一个从未被 emit 的
    `factory_selected` 空信号（主窗口侧 `_on_title_factory_selected` 实现完整、
    信号也接好了，唯独缺 UI），属「接线做完、控件漏做」的半成品。
    本控件与筛选面板的「工厂」下拉**语义不同、不重复**：
      · 标题栏 → `_on_factory_changed` → **重建主表数据源**（整个主表换成该工厂）
      · 筛选面板 → `proxy.setCustomFilters` → 只**筛表格里的行**
    故两者互补，标题栏放它是合理的。
    """

    theme_toggled = Signal()
    factory_selected = Signal(str)

    def __init__(self, version: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setObjectName("titleBar")
        # 记录当前工厂名，供外部对比「用户是否真的换了厂」——避免在
        # setCurrentIndex 触发的信号里做无意义的重建（切回原厂不应重算）
        self._current_factory = ''
        self._setup_ui(version)

    def _setup_ui(self, version: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(0)

        # 左侧蓝色竖条（4px）
        accent_bar = QWidget()
        accent_bar.setFixedWidth(4)
        accent_bar.setObjectName("titleAccentBar")
        layout.addWidget(accent_bar)

        # Emoji 图标
        logo_label = QLabel("\U0001F3ED")  # factory emoji
        logo_label.setFont(QFont("Segoe UI Emoji", 20))
        logo_bar = QVBoxLayout()
        logo_bar.setContentsMargins(16, 0, 12, 0)
        logo_bar.addWidget(logo_label, alignment=Qt.AlignVCenter)
        layout.addLayout(logo_bar, 0)

        # 标题区域（主标题 + 副标题）
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.setContentsMargins(0, 0, 0, 0)

        main_title = QLabel(f"云南达利ZPP011生产偏差分析器 {version}")
        main_title.setObjectName("titleMain")
        title_box.addWidget(main_title)

        sub_title = QLabel(f"制作人：裴盛清 | {version}")
        sub_title.setObjectName("titleSub")
        title_box.addWidget(sub_title)

        layout.addLayout(title_box, 0)
        layout.addStretch()

        # 工厂选择器（v43.128 新增）：切换主表数据源
        self.factory_combo = QComboBox()
        self.factory_combo.setObjectName("titleFactoryCombo")
        self.factory_combo.setFixedWidth(130)
        self.factory_combo.setCursor(Qt.PointingHandCursor)
        self.factory_combo.addItem("全部")  # 无数据时也有选项，避免空控件
        self.factory_combo.setToolTip("切换主表数据源到指定工厂（与左侧筛选面板的「工厂」不同：\n"
                                      "这里换整张表，筛选面板只筛表内行）")
        self.factory_combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.factory_combo, 0, Qt.AlignVCenter)

        # 主题切换
        self.theme_btn = QPushButton("\u2601 暗色")
        self.theme_btn.setFixedSize(64, 28)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.clicked.connect(self.theme_toggled.emit)
        layout.addWidget(self.theme_btn, 0, Qt.AlignVCenter)

    def set_theme_light(self):
        """当前是亮色主题，按钮显示'暗色'"""
        self.theme_btn.setText("\u2601\uFE0F 暗色")

    def set_theme_dark(self):
        """当前是暗色主题，按钮显示'亮色'"""
        self.theme_btn.setText("\u2600\uFE0F 亮色")

    # ── 工厂选择器（v43.128）──────────────────────────────

    def set_factories(self, names, current=None):
        """分析完成后填充工厂选项。

        参数
        ----
        names  : 可迭代的工厂名列表（一般是 analysis_controller.get_factories()）
        current: 当前工厂名；给了就选中它，不给则保持现状
        """
        names = [str(n) for n in (names or []) if str(n)]
        if not names:
            return
        # '全部' 排最前（_on_factory_changed 对它有专门的合并逻辑）
        ordered = (['全部'] + [n for n in names if n != '全部']) if '全部' not in names else list(names)

        # 重建会清掉当前选中项，故先记住目标值
        target = current if current in ordered else ordered[0]
        self.factory_combo.blockSignals(True)
        try:
            self.factory_combo.clear()
            for n in ordered:
                self.factory_combo.addItem(n)
            self.factory_combo.setCurrentText(target)
        finally:
            self.factory_combo.blockSignals(False)
        self._current_factory = target

    def set_current_factory(self, name):
        """外部（主窗口切完数据源后）把下拉同步到实际生效的工厂。

        用 blockSignals 防止「程序设值 → 再发信号 → 主窗口又重建一次数据源」的回环。
        """
        name = str(name or '')
        if not name or name == self._current_factory:
            return
        idx = self.factory_combo.findText(name)
        if idx < 0:
            return
        self.factory_combo.blockSignals(True)
        try:
            self.factory_combo.setCurrentIndex(idx)
        finally:
            self.factory_combo.blockSignals(False)
        self._current_factory = name

    def get_current_factory(self):
        return self._current_factory

    def _on_combo_changed(self, index):
        """用户主动切换 → 发信号。

        切回原厂不发信号：数据源已经是它了，重建一次纯属浪费
        （_on_factory_changed 会重跑 setDataFrame 并刷新统计卡）。
        """
        text = self.factory_combo.itemText(index) if 0 <= index < self.factory_combo.count() else ''
        if not text or text == self._current_factory:
            return
        self._current_factory = text
        self.factory_selected.emit(text)
