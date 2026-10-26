# -*- coding: utf-8 -*-
"""
列控制器（ARC-003 拆分产物）
负责：列宽持久化 / 列显隐 / 表头排序 / 列过滤弹窗 / 多列排序 / 全屏与列锁

模式：组合式。本控制器持有 MainWindow 引用（self.mw），方法体从 MainWindow
原样搬迁、逻辑零改动；MainWindow 侧保留同名薄壳转发方法，保证外部既有调用
（components/main_table.py 的 self.mw._on_header_clicked 等信号绑定、各看板
dialog 的 self.main_window._apply_column_visibility_by_name()）签名不变。
"""

import os

import pandas as pd

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QHeaderView, QDialog, QDialogButtonBox,
    QMenu, QScrollArea, QCheckBox,
)

from gui_pyside6.models.data_frame_model import build_display_key_list
from gui_pyside6.widgets.toast import toast
from gui_pyside6.utils.icons import get_icon
from gui_pyside6.dialogs.col_filter_ui import set_col_filter_button_on


class ColumnController:
    """列相关业务控制器（纯 UI 逻辑，不触碰 analyzer 口径层）。"""

    def __init__(self, mw):
        self.mw = mw
    def _toggle_column_lock(self):
        locked = self.mw.lock_btn.isChecked()
        header = self.mw.table_view.horizontalHeader()
        if locked:
            header.setSectionResizeMode(QHeaderView.Fixed)
            # v43.266：锁按钮已图标化（make_button("🔒")），状态切换改 setIcon，
            # 原来的 setText("🔓") 会把图标洗回 emoji 字形。
            self.mw.lock_btn.setIcon(get_icon("unlock", 14))
            self.mw.statusBar().showMessage("列宽已锁定", 2000)
        else:
            header.setSectionResizeMode(QHeaderView.Interactive)
            self.mw.lock_btn.setIcon(get_icon("lock", 14))
            self.mw.statusBar().showMessage("列宽已解锁，可拖拽调整", 2000)

    def _toggle_table_fullscreen(self):
        """切换全屏模式"""
        full = not getattr(self, '_is_fullscreen', False)
        self.mw._is_fullscreen = full
        if full:
            self.mw.left_panel.setVisible(False)
            # 全屏时保留底部合计栏，隐藏系统状态栏
            if hasattr(self, 'filter_panel') and self.mw.filter_panel:
                self.mw.filter_panel.setVisible(False)
            self.mw.statusBar().hide()
            QApplication.processEvents()
            self.mw.statusBar().showMessage("全屏模式 (F11 退出)", 3000)
        else:
            self.mw.left_panel.setVisible(True)
            if hasattr(self, 'filter_panel') and self.mw.filter_panel:
                self.mw.filter_panel.setVisible(True)
            self.mw.statusBar().show()
            QApplication.processEvents()
            self.mw.statusBar().showMessage("已退出全屏", 2000)

    def _show_column_hide_dialog(self):
        """显示隐藏列对话框（按列名记录显隐，避免列重排后错位丢失）"""
        model = self.mw.table_view.model()
        if not model:
            return
        col_count = model.columnCount()
        if col_count == 0:
            return

        # 收集 (列索引, 列名) —— 列名用于稳定记录显隐状态
        cols_info = []
        for col in range(col_count):
            hdr = model.headerData(col, Qt.Horizontal)
            name = str(hdr).replace('\n', '') if hdr else f"列{col}"
            if name == '_post_audit_changed':  # 内部变更标记列，不在显隐对话框列出
                continue
            cols_info.append((col, name))

        dialog = QDialog(self.mw)
        dialog.setWindowTitle("隐藏/显示列")
        dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog)

        hint = QLabel("勾选要显示的列，取消勾选则隐藏；标「（已隐藏）」的列当前未显示：")
        layout.addWidget(hint)

        # 快捷按钮：一键恢复全部 / 全部隐藏
        btn_row = QHBoxLayout()
        btn_show_all = QPushButton("恢复全部显示")
        btn_hide_all = QPushButton("全部隐藏")
        btn_row.addWidget(btn_show_all)
        btn_row.addWidget(btn_hide_all)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 复选框列表（滚动区域）；隐藏的列追加「（已隐藏）」标记便于辨认
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)

        checkboxes = []
        for idx, (col, name) in enumerate(cols_info):
            # 真实可见性：既认 setColumnHidden，也认“宽度被拖成 0”的挤没列
            is_hidden = self.mw._is_column_effectively_hidden(col)
            label = f"{idx + 1}. {name}（已隐藏）" if is_hidden else f"{idx + 1}. {name}"
            cb = QCheckBox(label)
            cb.setChecked(not is_hidden)
            checkboxes.append((col, name, cb))
            scroll_layout.addWidget(cb)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # 确定按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        # 快捷按钮：恢复全部显示 / 全部隐藏（按列名清空/填满隐藏集合）
        btn_show_all.clicked.connect(lambda: [cb.setChecked(True) for _, _, cb in checkboxes])
        btn_hide_all.clicked.connect(lambda: [cb.setChecked(False) for _, _, cb in checkboxes])

        if dialog.exec() == QDialog.Accepted:
            # 记录被取消勾选（即要隐藏）的列名
            self.mw._hidden_column_names = {
                name for _, name, cb in checkboxes if not cb.isChecked()
            }
            self.mw._apply_column_visibility_by_name()
            # 被勾选（要显示）的列若被拖成 0 宽，恢复默认宽度（像 Excel 取消隐藏）
            for col, name, cb in checkboxes:
                if cb.isChecked():
                    self.mw._ensure_column_visible_width(col, name)
            self.mw._save_column_widths()  # 持久化显隐状态：手动显示/隐藏都记住
            self.mw.statusBar().showMessage("列显示已更新", 2000)

    def _is_column_effectively_hidden(self, col):
        """列是否实际不可见：被 setColumnHidden 或宽度被拖成 0 都算"""
        if self.mw.table_view.isColumnHidden(col):
            return True
        try:
            return self.mw.table_view.columnWidth(col) <= 1
        except Exception:
            return False

    def _ensure_column_visible_width(self, col, name):
        """若列宽被拖成 0（挤没），恢复一个合理的默认宽度"""
        if self.mw.table_view.columnWidth(col) <= 1:
            self.mw._apply_default_width(col, name)
            if self.mw.table_view.columnWidth(col) <= 1:
                self.mw.table_view.setColumnWidth(col, 120)

    def _apply_column_visibility_by_name(self):
        """按列名设置列的显隐状态（不受列重排 / 模型重置影响）"""
        self.mw._hidden_column_names.update({
            '_post_audit_changed', 'data_id', 'fingerprint', '_quarantined',
            'AI建议',
        })  # 内部技术列始终隐藏（即使用户在列显隐对话框里勾选显示）
        model = self.mw.table_view.model()
        if not model:
            return
        for col in range(model.columnCount()):
            hdr = model.headerData(col, Qt.Horizontal)
            name = str(hdr).replace('\n', '') if hdr else ''
            self.mw.table_view.setColumnHidden(col, name in self.mw._hidden_column_names)

    def _set_column_widths(self):
        header = self.mw.table_view.horizontalHeader()
        model = self.mw.table_view.model()
        if not model:
            return

        # 优先从配置文件恢复用户保存的列宽与隐藏状态
        saved_widths, saved_hidden = self.mw._load_column_widths()
        # 恢复隐藏集合（按列名），再按名应用显隐
        self.mw._hidden_column_names = set(saved_hidden) if saved_hidden else set()
        self.mw._apply_column_visibility_by_name()

        if saved_widths:
            for col in range(model.columnCount()):
                col_name = model.headerData(col, Qt.Horizontal)
                if col_name:
                    col_name = str(col_name).replace('\n', '')
                    if col_name in saved_widths:
                        self.mw.table_view.setColumnWidth(col, saved_widths[col_name])
                        continue
                # 没有保存过的列用默认逻辑
                self.mw._apply_default_width(col, col_name)
            return

        # 无配置文件时用默认逻辑。
        # 注意：不再调用 resizeColumnsToContents()——万行级表格会逐行测量宽度，
        # 导致主线程卡顿/未响应。改为按列名设定合理最小宽度，让用户可手动拖动。
        self.mw.table_view.setColumnWidth(0, 35)
        for col in range(1, model.columnCount()):
            col_name = model.headerData(col, Qt.Horizontal) if hasattr(model, 'headerData') else ''
            self.mw._apply_default_width(col, col_name)

    def _apply_default_width(self, col, col_name):
        """对单列应用默认宽度逻辑（按列名给最小宽度，避免 ResizeToContents 扫描全表）"""
        if isinstance(col_name, str):
            if '名称' in col_name or '描述' in col_name or col_name == '物料':
                if self.mw.table_view.columnWidth(col) < 200:
                    self.mw.table_view.setColumnWidth(col, 200)
            elif '编码' in col_name or '号' in col_name or '订单' in col_name or col_name == '半成品重分类':
                if self.mw.table_view.columnWidth(col) < 120:
                    self.mw.table_view.setColumnWidth(col, 120)
            elif '备注' in col_name or '原因' in col_name:
                if self.mw.table_view.columnWidth(col) < 150:
                    self.mw.table_view.setColumnWidth(col, 150)
            else:
                # 数字/日期等列给一个保底宽度，避免太窄
                if self.mw.table_view.columnWidth(col) < 80:
                    self.mw.table_view.setColumnWidth(col, 80)

    def _get_user_config_dir(self):
        """用户可写的配置目录（打包 onefile 后 __file__ 在临时目录，不能再用它落盘）。"""
        base = os.environ.get("ZPP011_CONFIG_DIR")
        if not base:
            base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ZPP011")
        return base

    def _get_config_path(self):
        """列宽/列显隐配置的读写路径（用户目录，如 %APPDATA%\\ZPP011\\column_widths.json）。"""
        config_dir = self.mw._get_user_config_dir()
        try:
            os.makedirs(config_dir, exist_ok=True)
        except Exception:
            pass
        return os.path.join(config_dir, 'column_widths.json')

    def _get_default_config_path(self):
        """仓库内置的默认列宽（只读）：用户配置不存在时作为初始值，保持历史观感。"""
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'config', 'column_widths.json')

    def _save_column_widths(self):
        """保存当前列宽与隐藏状态到配置文件（隐藏按列名记录，可手动在对话框中恢复显示）"""
        model = self.mw.table_view.model()
        if not model:
            return
        config = {}
        for col in range(model.columnCount()):
            col_name = model.headerData(col, Qt.Horizontal)
            if col_name:
                col_name = str(col_name).replace('\n', '')
                config[col_name] = {
                    'width': self.mw.table_view.columnWidth(col),
                    'hidden': col_name in self.mw._hidden_column_names,
                }
        try:
            import json
            with open(self.mw._get_config_path(), 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # self.mw.log 是空操作，必须显式提示，否则属静默失败
            self.mw.statusBar().showMessage(f"列宽保存失败：{e}", 5000)
            toast(f"列宽保存失败：{e}", level="warning", parent=self)

    def _load_column_widths(self):
        """从配置文件加载列宽与隐藏状态。返回 (widths_dict, hidden_set)。"""
        try:
            import json
            path = self.mw._get_config_path()
            if not os.path.exists(path):
                # 首次运行/旧版本升级：沿用仓库内既有列宽作为初始值
                path = self.mw._get_default_config_path()
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                widths = {}
                hidden = set()
                for k, v in raw.items():
                    if isinstance(v, dict):
                        widths[k] = v.get('width', 100)
                        if v.get('hidden'):
                            hidden.add(k)
                    else:
                        # 兼容旧格式（纯宽度数值）
                        widths[k] = v
                return widths, hidden
        except Exception as e:
            self.mw.log(f"加载列宽失败: {e}", "warning")
        return None, set()

    def _on_header_clicked(self, logical_index):
        """列头点击：单列为【未排 → 升序 → 降序 → 未排】三态循环；Ctrl+点击为多列多级排序。"""
        # 三路冗余读取 Ctrl，最大化真实环境命中率，彻底绕开 Qt「鼠标事件读不到 Ctrl」的坑：
        #   1) self.mw._ctrl_down    —— 由 KeyPress/KeyRelease 事件流实时维护（最可靠，主用）
        #   2) self.mw._sort_header._ctrl_held —— SortBadgeHeader.mousePressEvent 按下时捕获（兜底）
        #   3) QApplication.keyboardModifiers() —— 信号触发瞬间查真实键盘态（再兜底）
        ctrl_pressed = bool(getattr(self, "_ctrl_down", False)) \
            or bool(getattr(self.mw._sort_header, "_ctrl_held", False)) \
            or bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        # 列头筛选模式：点列头弹取值勾选浮层（Ctrl+点列头仍走排序；第0列_图标列不参与）
        if self.mw._col_filter_mode and logical_index > 0 and not ctrl_pressed:
            self.mw._open_column_filter(logical_index)
            return
        col = logical_index
        if col <= 0:
            return  # 第一列(_read)不参与排序
        if ctrl_pressed:
            found = False
            for i, (c, asc) in enumerate(self.mw.sort_columns):
                if c == col:
                    self.mw.sort_columns[i] = (col, not asc)
                    found = True
                    break
            if not found:
                self.mw.sort_columns.append((col, True))
        else:
            active = [(c, a) for (c, a) in self.mw.sort_columns if c == col]
            if not active:
                self.mw.sort_columns = [(col, True)]
            elif active[0][1]:
                self.mw.sort_columns = [(col, False)]
            else:
                self.mw.sort_columns = []
        self.mw._apply_multi_sort()
        self.mw._update_sort_indicators()

    def _update_col_filter_hint(self):
        """刷新状态栏「列头筛选」常驻提示：已筛列数 + 列名（截断显示）。

        修复（2026-10-01）：列头筛选后原本只有表头左上角小橙三角，无法判断哪些列被筛过；
        现在状态栏常驻显示「🔽 列头筛选：N 列（列名1、列名2…」，无筛选时显示 0 列。
        列号→列名映射取自 source_model._display_columns（与表头逻辑列对齐）。
        """
        label = getattr(self, "_col_filter_hint_label", None)
        if label is None:
            return
        col_set = getattr(self, "_filtered_col_set", set()) or set()
        if not col_set:
            label.setText("列头筛选：0 列")
            label.show()
            return
        # 列号 → 列名（display_columns 与表头逻辑列一致；取不到的显示列号）
        sm = getattr(self, "source_model", None)
        display_cols = getattr(sm, "_display_columns", []) if sm is not None else []
        names = []
        for c in sorted(col_set):
            if 0 <= c < len(display_cols):
                names.append(str(display_cols[c]))
            else:
                names.append(f"列{c}")
        shown = names[:5]
        more = len(names) - len(shown)
        text = "列头筛选：%d 列（%s" % (len(names), "、".join(shown))
        if more > 0:
            text += " …+%d" % more
        text += "）"
        label.setText(text)
        label.show()
        if getattr(self, "_sort_header", None) is not None:
            # 自绘画在表头本体（Qt6 QHeaderView 的 frame 层），必须 header.update()
            # 触发 paintEvent；viewport().update() 不会重画漏斗/角标
            self.mw._sort_header.update()

    def _toggle_col_filter_mode(self):
        """工具栏「🔽 列头筛选」开关：开启后点列头弹取值勾选浮层（Excel 式筛选）；
        Ctrl+点列头仍走排序。关闭后点列头恢复排序行为。"""
        self.mw._col_filter_mode = not self.mw._col_filter_mode
        btn = self.mw.action_btn_col_filter
        btn.setChecked(self.mw._col_filter_mode)
        # v43.266：工具栏按钮已图标化（funnel 图标 + 「列头筛选」文字），
        # 状态切换走共用函数 set_col_filter_button_on（只改文字、不洗掉图标）
        set_col_filter_button_on(btn, self.mw._col_filter_mode)
        if not self.mw._col_filter_mode:
            # 关闭模式时顺手关掉可能还开着的浮层
            if self.mw._col_filter_popup is not None:
                try:
                    self.mw._col_filter_popup.close()
                except Exception:
                    pass
                self.mw._col_filter_popup = None

    def _open_column_filter(self, logical_index):
        """在点击列头处弹出 Excel 式取值勾选浮层。
        取值取自 source_model 的 DisplayRole（与表格实际显示字符串一致，含偏差率%后缀、(空)占位），
        确保勾选的值和表格中看到的完全一致。确定后调 proxy_model.setValueFilter。"""
        proxy = self.mw.proxy_model
        sm = proxy.sourceModel() if proxy is not None else None
        if sm is None or not hasattr(sm, "_display_columns"):
            return
        if logical_index < 0 or logical_index >= len(sm._display_columns):
            return
        col_name = sm._display_columns[logical_index]

        # 收集本列全部展示值及计数（保持首次出现顺序）
        # 性能（2026-10-02）：向量化取展示键（与 DisplayRole 一致），替代逐行 sm.data()
        n = sm.rowCount()
        key_list = build_display_key_list(sm, logical_index)
        if key_list is None:
            key_list = []
            for r in range(n):
                disp = sm.data(sm.index(r, logical_index), Qt.DisplayRole)
                key_list.append("(空)" if disp in (None, "") else str(disp))
        cnt = {}
        order = []
        for key in key_list:
            if key not in cnt:
                cnt[key] = 0
                order.append(key)
            cnt[key] += 1
        if not order:
            # 修复（v43.143）：本列无任何取值（被其它条件筛空）时原先直接 return，
            # 用户看着空表 + 点列头无反应，无法取消任何筛选。改弹兜底浮层给出出口。
            self.mw._open_empty_column_filter_popup(col_name, logical_index)
            return

        # 已选集合（来自 proxy 已存的取值过滤）
        prev = set(proxy._value_filters.get(col_name, set()))

        # 若已有浮层，先关掉
        if self.mw._col_filter_popup is not None:
            try:
                self.mw._col_filter_popup.close()
            except Exception:
                pass
            self.mw._col_filter_popup = None

        popup = QWidget(self, Qt.Popup)
        popup.setObjectName("colFilterPopup")
        # v43.251：Qt.Popup 默认 WA_InputMethodEnabled=False，浮层不参与输入法 →
        # 里面的搜索框拿不到 IME 焦点 → **打不进汉字**（中文输入法唤不起来）。
        # 打开这个属性后，popup 在 show() 时会把焦点自动交给第一个可聚焦子控件。
        popup.setAttribute(Qt.WA_InputMethodEnabled, True)
        popup.setMinimumWidth(260)
        popup.setMaximumHeight(420)
        outer = QVBoxLayout(popup)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        title = QLabel(f"筛选：{col_name}（共 {n} 行 / {len(order)} 个值）")
        title.setObjectName("columnFilterTitle")
        outer.addWidget(title)

        search = QLineEdit()
        search.setPlaceholderText("搜索取值…")
        outer.addWidget(search)

        # 全选 / 清空 / 清除此列
        btn_row = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_none = QPushButton("清空")
        btn_clear = QPushButton("清除此列")
        btn_clear.setToolTip("取消本列的全部取值过滤（等同恢复未筛选）")
        btn_clear.setEnabled(bool(proxy._value_filters.get(col_name)))
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        # 勾选列表（滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        list_layout = QVBoxLayout(scroll_content)
        list_layout.setContentsMargins(2, 2, 2, 2)
        list_layout.setSpacing(2)
        scroll.setWidget(scroll_content)
        outer.addWidget(scroll, 1)

        items = []  # (key, checkbox)
        for key in order:
            cb = QCheckBox(f"{key}  ({cnt[key]})")
            cb.setChecked(key in prev)
            list_layout.addWidget(cb)
            items.append((key, cb))

        def apply_search(text):
            t = text.strip().lower()
            for key, cb in items:
                cb.setVisible((t in key.lower()) if t else True)

        search.textChanged.connect(apply_search)

        def select_all():
            for _, cb in items:
                cb.setChecked(True)

        def select_none():
            for _, cb in items:
                cb.setChecked(False)

        def do_clear_column():
            """「清除此列」：丢弃本列取值过滤 + 漏斗标 + 本列排序，并关浮层。

            与「清空」区别：「清空」只把勾选全取消，点确定后会因空集被 setValueFilter
            当作「清除」处理（见 do_apply），但用户不知道；这里给一个显式入口。
            v43.144：连带取消本列排序。
            """
            proxy.setValueFilter(col_name, set())
            self.mw._filtered_col_set.discard(logical_index)
            self.mw._drop_sort_columns([logical_index])
            self.mw._update_col_filter_hint()
            self.mw._sort_header.update()
            popup.close()

        btn_all.clicked.connect(select_all)
        btn_none.clicked.connect(select_none)
        btn_clear.clicked.connect(do_clear_column)

        # 确定 / 取消
        ok_row = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        ok_row.addStretch(1)
        ok_row.addWidget(btn_cancel)
        ok_row.addWidget(btn_ok)
        outer.addLayout(ok_row)

        def do_apply():
            selected = {key for key, cb in items if cb.isChecked()}
            if not selected or selected == set(order):
                # 全选 或 一个都没选：都等价于「不过滤」。
                # 修复（v43.143）：原先「一个都没选」会走到 else 分支 _filtered_col_set.add()，
                # 提示栏显示「1 列」但实际无过滤（setValueFilter 空集=清除），状态自相矛盾；
                # 且用户看到漏斗标却找不到地方取消。现统一走清除分支。
                proxy.setValueFilter(col_name, set())
                self.mw._filtered_col_set.discard(logical_index)
                # v43.144：取消筛选时连带取消本列排序
                self.mw._drop_sort_columns([logical_index])
            else:
                proxy.setValueFilter(col_name, selected)
                self.mw._filtered_col_set.add(logical_index)
            self.mw._update_col_filter_hint()  # 其内部已会重画表头
            # 修复（2026-10-02）：Qt6 QHeaderView 自绘画在表头本体（frame 层），
            # viewport().update() 只刷内部 viewport，确定后漏斗/角标不会重画。
            # 与排序角标同款触发方式：header.update()。
            self.mw._sort_header.update()
            popup.close()

        btn_ok.clicked.connect(do_apply)
        btn_cancel.clicked.connect(popup.close)

        self.mw._col_filter_popup = popup

        # 定位到点击列头下方，并避免超出屏幕
        x = self.mw._sort_header.sectionViewportPosition(logical_index)
        y = self.mw._sort_header.height()
        gpos = self.mw._sort_header.viewport().mapToGlobal(QPoint(int(x), int(y)))
        popup.show()
        popup.adjustSize()
        pw = popup.width()
        ph = popup.height()
        screen = QApplication.primaryScreen()
        if screen is not None:
            sg = screen.availableGeometry()
            if gpos.x() + pw > sg.right():
                gpos.setX(max(sg.left(), sg.right() - pw))
            if gpos.y() + ph > sg.bottom():
                gpos.setY(max(sg.top(), gpos.y() - ph - self.mw._sort_header.height()))
        popup.move(gpos)
        # v43.251：把焦点显式交给搜索框。Qt.Popup 显示时焦点默认落在浮层自身
        # （QWidget 默认 NoFocus 策略），子控件拿不到焦点 → IME 唤不起来 →
        # 搜索框打不进汉字。WA_InputMethodEnabled 已让 show() 后焦点自动落到搜索框，
        # 这里再显式设一次兜底；延到事件循环执行，避免与 show 的焦点分配抢先后。
        QTimer.singleShot(0, search.setFocus)

    def _open_empty_column_filter_popup(self, col_name, logical_index):
        """本列无取值时的兜底浮层：只给「清除此列 / 清除全部 / 关闭」三个出口。"""
        if self.mw._col_filter_popup is not None:
            try:
                self.mw._col_filter_popup.close()
            except Exception:
                pass
            self.mw._col_filter_popup = None
        popup = QWidget(self, Qt.Popup)
        popup.setObjectName("colFilterPopup")
        # v43.251：同主浮层，打开输入法支持（此处无搜索框，但保持浮层约定一致）
        popup.setAttribute(Qt.WA_InputMethodEnabled, True)
        popup.setMinimumWidth(300)
        outer = QVBoxLayout(popup)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        tip = QLabel(f"「{col_name}」当前没有任何可选取值\n（表格已被其它筛选条件筛空）")
        tip.setObjectName("columnFilterTitle")
        tip.setWordWrap(True)
        outer.addWidget(tip)

        def _after_clear():
            self.mw._update_col_filter_hint()
            self.mw._sort_header.update()

        def do_clear_col():
            self.mw.proxy_model.setValueFilter(col_name, set())
            self.mw._filtered_col_set.discard(logical_index)
            self.mw._drop_sort_columns([logical_index])
            _after_clear()
            popup.close()

        def do_clear_all():
            hit = sorted(self.mw._filtered_col_set)
            self.mw.proxy_model.clearHeaderFilters()
            self.mw._filtered_col_set.clear()
            self.mw._drop_sort_columns(hit)
            _after_clear()
            popup.close()

        btn_col = QPushButton("清除此列筛选")
        btn_col.clicked.connect(do_clear_col)
        btn_all = QPushButton("清除全部列头筛选")
        btn_all.clicked.connect(do_clear_all)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(popup.close)
        outer.addWidget(btn_col)
        outer.addWidget(btn_all)
        outer.addWidget(btn_close)
        self.mw._col_filter_popup = popup
        x = self.mw._sort_header.sectionViewportPosition(logical_index)
        y = self.mw._sort_header.height()
        gpos = self.mw._sort_header.viewport().mapToGlobal(QPoint(int(x), int(y)))
        popup.show()
        popup.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is not None:
            sg = screen.availableGeometry()
            gpos.setX(min(gpos.x(), max(sg.left(), sg.right() - popup.width())))
            gpos.setY(min(gpos.y(), max(sg.top(), sg.bottom() - popup.height())))
        popup.move(gpos)

    def _apply_multi_sort(self):
        """按 self.mw.sort_columns 重排主表（基于原始顺序，避免多次排序叠加）。
        空列表时恢复加载时的原始顺序（取消排序）。"""
        if not hasattr(self, "source_model") or self.mw.source_model is None:
            return
        if not self.mw.sort_columns:
            # 取消排序：恢复原始（加载时）顺序
            if self.mw._natural_df is not None:
                self.mw._in_sort = True
                try:
                    self.mw.source_model.setDataFrame(self.mw._natural_df.copy())
                finally:
                    self.mw._in_sort = False
                self.mw._apply_column_visibility_by_name()
            return
        natural = self.mw._natural_df if self.mw._natural_df is not None else self.mw.source_model.getDataFrame()
        if natural is None or natural.empty:
            return
        df = natural.copy()
        sort_args = []
        for col, asc in self.mw.sort_columns:
            if col <= 0 or col >= len(df.columns):
                continue
            sort_args.append((df.columns[col], asc))
        if not sort_args:
            return
        cols = [c for c, _ in sort_args]
        asc_list = [a for _, a in sort_args]
        sort_keys = {}
        for c in cols:
            has_pct = df[c].astype(str).str.contains("%", na=False).any()
            if has_pct:
                numeric_vals = pd.to_numeric(df[c].astype(str).str.replace("%", "").str.strip(), errors="coerce").fillna(0)
                sort_keys[c] = numeric_vals
        if sort_keys:
            df_sorted = df.sort_values(by=cols, ascending=asc_list, key=lambda col: sort_keys.get(col.name, col), na_position="last")
        else:
            df_sorted = df.sort_values(by=cols, ascending=asc_list, na_position="last")
        self.mw._in_sort = True
        try:
            self.mw.source_model.setDataFrame(df_sorted)
        finally:
            self.mw._in_sort = False
        self.mw._apply_column_visibility_by_name()

    def _update_sort_indicators(self):
        """刷新列头多级排序角标（见 SortBadgeHeader）。
        纯自绘方案：关闭原生箭头（setSortingEnabled(False) 下原生 setSortIndicator 不可靠、
        且不显示多级），由 SortBadgeHeader.paintEvent 在各级已排序列角上叠「层级数字+▲▼」角标。
        取消排序(sort_columns 为空)时角标自然消失。"""
        header = self.mw.table_view.horizontalHeader()
        header.blockSignals(True)
        try:
            header.setSortIndicatorShown(False)  # 关原生箭头，避免与自绘角标重复
        finally:
            header.blockSignals(False)
        # 触发表头重绘以刷新自绘角标（1▲/2▼ ...）
        header.update()

    # -----------------------------------------------------------
    # 工厂切换
    # -----------------------------------------------------------

    def _show_col_filter_clear_menu(self, label, pos):
        """列头筛选提示标签的清除菜单：逐列清除 + 一键清除全部。

        v43.143 新增：此前提示标签是纯 QLabel，用户想取消筛选只能开浮层重新勾一遍
        （且关掉「🔽 列头筛选」模式开关并不清筛选），观感=「无法取消」。
        """
        menu = QMenu(label)
        col_set = getattr(self, "_filtered_col_set", set()) or set()
        sm = getattr(self, "source_model", None)
        display_cols = getattr(sm, "_display_columns", []) if sm is not None else []
        if not col_set:
            act_none = menu.addAction("当前没有列头筛选")
            act_none.setEnabled(False)
        else:
            menu.addSection("逐列清除")
            for c in sorted(col_set):
                name = str(display_cols[c]) if 0 <= c < len(display_cols) else f"列{c}"
                menu.addAction("清除此列：%s" % name,
                               lambda _=False, n=name: self.mw._clear_col_filter_by_name(n))
            menu.addSeparator()
            menu.addAction("清除全部列头筛选", self.mw._clear_all_col_filters)
        menu.exec(label.mapToGlobal(pos))

    def _clear_col_filter_by_name(self, col_name, clear_sort=True):
        """按列名清除主表的列头取值过滤（含漏斗标与提示刷新）。

        v43.144：`clear_sort=True` 时连带把该列从 sort_columns 移除并重排。
        原先只清筛选不清排序，取消后该列排序角标/箭头仍留着，视觉上像还在筛。
        """
        if self.mw.proxy_model is None:
            return
        self.mw.proxy_model.setValueFilter(col_name, set())
        sm = getattr(self, "source_model", None)
        display_cols = getattr(sm, "_display_columns", []) if sm is not None else []
        hit = []
        if col_name in display_cols:
            hit = [display_cols.index(col_name)]
        else:
            hit = [c for c in list(self.mw._filtered_col_set)
                   if 0 <= c < len(display_cols) and str(display_cols[c]) == col_name]
        for c in hit:
            self.mw._filtered_col_set.discard(c)
        if clear_sort and hit:
            self.mw._drop_sort_columns(hit)
        self.mw._update_col_filter_hint()

    def _clear_all_col_filters(self, clear_sort=True):
        """清除主表全部列头取值过滤（v43.144：连带取消这些列的排序）。"""
        if self.mw.proxy_model is not None:
            self.mw.proxy_model.clearHeaderFilters()
        hit = sorted(self.mw._filtered_col_set)
        self.mw._filtered_col_set.clear()
        if clear_sort and hit:
            self.mw._drop_sort_columns(hit)
        self.mw._update_col_filter_hint()

    def _drop_sort_columns(self, col_indexes):
        """把给定列号从多级排序中移除并重排（移除后为空则整体恢复原始顺序）。"""
        before = len(self.mw.sort_columns)
        self.mw.sort_columns = [(c, asc) for c, asc in self.mw.sort_columns
                             if c not in set(col_indexes)]
        if len(self.mw.sort_columns) == before:
            return          # 本来就没排这些列，不必重排
        self.mw._apply_multi_sort()
        self.mw._update_sort_indicators()
