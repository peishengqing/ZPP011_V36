"""
ZPP011 UI 重构 - 组件文件清单

本文档记录了本次 UI 重构涉及的所有文件和关键变更。
供后续维护和二次开发参考。

创建时间: 2026-06-23
作者: UI Designer (裴哥)
"""

COMPONENTS = {
    "title_bar.py": {
        "path": "gui_pyside6/components/title_bar.py",
        "class": "TitleBarWidget",
        "changes": [
            "替换原来硬编码蓝色标题栏",
            "增加工厂选择下拉框（连接 config.py 中的 factory_config）",
            "增加主题切换按钮（暗色/亮色）",
            "保留最小化/最大化/关闭按钮",
            "暗色主题下标题栏背景 #1A1830",
        ],
    },
    "left_panel.py": {
        "path": "gui_pyside6/components/left_panel.py",
        "class": "LeftPanelComponent",
        "changes": [
            "宽度固定 240px（原 180px）",
            "新增偏差率范围过滤（QSpinBox x2）",
            "新增审核状态多选过滤",
            "新增"备选料管理"折叠区域",
            "新增"快捷操作"按钮组（全部选中、清除、反选）",
            "QLineEdit/QComboBox/QCheckBox 暗色样式",
        ],
    },
    "main_table.py": {
        "path": "gui_pyside6/components/main_table.py",
        "class": "MainTableComponent",
        "changes": [
            "主表增加水平滚动（QScrollArea 包裹 QTableView）",
            "表头区域嵌入统计卡片（总行数、偏差率、审核进度）",
            "新增"列管理"下拉菜单（checkbox 列表控制显隐）",
            "固定列（左侧6列）与滚动列分离渲染",
        ],
    },
    "bottom_bar.py": {
        "path": "gui_pyside6/components/bottom_bar.py",
        "class": "BottomBarComponent",
        "changes": [
            "高度从 80px 增加到 140px",
            "等宽字体 (Courier New / Consolas)",
            "深色背景 #1A1830",
            "错误日志行红色高亮",
            "支持点击日志行跳转到对应数据行",
        ],
    },
    "dark_theme.qss": {
        "path": "gui_pyside6/dark_theme.qss",
        "class": None,
        "changes": [
            "全局 QSS 样式表",
            "覆盖 QMainWindow/QWidget/QTableView/QHeaderView",
            "自定义 QScrollBar 暗色样式",
            "自定义 QProgressBar 暗色样式",
            "自定义 QGroupBox 暗色样式",
            "自定义 QToolTip 暗色样式",
        ],
    },
}

if __name__ == "__main__":
    import json
    print(json.dumps(COMPONENTS, indent=2, ensure_ascii=False))
