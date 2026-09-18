# -*- coding: utf-8 -*-
"""
Excel 式列头取值筛选控制器（方案 B：就地过滤，不依赖 AuditProxyModel）。

设计要点
--------
- 复用各对话框已有的「_apply_filter() + original_df」管线：本控制器只负责维护
  "每列允许显示的展示值集合"，确定时回调对话框的 apply_filter_cb 重新算 filtered
  （在 DataFrame 层叠加列取值成员过滤）。视图行号始终 == 源行号，
  选中 / 双击 / 导出 / 定位全部零回归。
- 表头漏斗标由 SortBadgeHeader 负责（通过 set_filtered_columns_getter 注入本控制器的列集合）。
- 弹层取值取自【当前显示在表格里的】DataFrameModel 的 DisplayRole（与表格实际字符串一致），
  每次打开实时计算，不预存 keys —— 天然规避 AuditProxyModel._value_keys 在 setDataFrame
  后失步的坑。

与方案 A（插 AuditProxyModel）的区别：方案 A 会让视图行号与源行号脱钩，
要求改约 15 处选中/双击/定位的行号解析（加 mapToSource），回归面大；
本方案在 DataFrame 层就地过滤，对话框既有行号解析逻辑一行都不用动。
"""
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QScrollArea, QApplication,
)


class ColumnFilterController:
    """Excel 式列头取值筛选控制器。"""

    def __init__(self, table_view, header, sort_ctrl, source_model_getter,
                 apply_filter_cb, skip_cols=(0,)):
        """
        :param table_view: 目标 QTableView
        :param header: 表头（SortBadgeHeader 或带 funnel 的 FilterHeader），用于漏斗绘制与浮层定位
        :param sort_ctrl: HeaderSortController（非筛选模式下委托其处理排序）
        :param source_model_getter: callable -> 当前显示的 DataFrameModel（用于实时读取 DisplayRole 取值）
        :param apply_filter_cb: callable -> 重新执行对话框过滤（会读取本控制器的 value_filters 叠加过滤）
        :param skip_cols: 不参与筛选/排序的列号集合（如内部 _read 列）
        """
        self.table_view = table_view
        self.header = header
        self.sort_ctrl = sort_ctrl
        self.source_model_getter = source_model_getter
        self.apply_filter_cb = apply_filter_cb
        self.skip_cols = set(skip_cols)
        self._col_filter_mode = False
        self._filtered_col_set = set()   # 已设取值过滤的列号集合（供表头画漏斗标）
        self._value_filters = {}         # col_name -> set(允许显示的展示值字符串)
        self._popup = None

    # ---- 状态查询 ----
    @property
    def filtered_col_set(self):
        return self._filtered_col_set

    def get_value_filters(self):
        return self._value_filters

    def has_any(self):
        return bool(self._value_filters)

    # ---- 模式开关 ----
    def toggle_mode(self):
        """切换 🔽 列头筛选模式，返回新模式（True=开）。"""
        self._col_filter_mode = not self._col_filter_mode
        if not self._col_filter_mode and self._popup is not None:
            try:
                self._popup.close()
            except Exception:
                pass
            self._popup = None
        return self._col_filter_mode

    # ---- 列头点击路由（替代 enable_click_sort 的 sectionClicked 连接）----
    def on_header_clicked(self, logical_index):
        ctrl = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        if self._col_filter_mode and logical_index > 0 and not ctrl:
            self.open_filter(logical_index)
            return
        # 非筛选模式（或第0列 / Ctrl+点）：委托给排序控制器
        self.sort_ctrl._on_click(logical_index)

    # ---- 取值过滤在 DataFrame 层落地（被对话框 _apply_filter 调用）----
    def mask_dataframe(self, df):
        """在对话框已算好的 filtered(df) 上叠加列取值成员过滤，返回新 df。

        展示键用 DataFrameModel 的真实 DisplayRole 计算（临时模型，无视图附着，零副作用），
        保证与表格中看到的字符串完全一致（含偏差率%后缀、(空)占位等）。
        """
        if not self._value_filters or df is None or len(df) == 0:
            return df
        from gui_pyside6.models.data_frame_model import DataFrameModel
        import pandas as pd
        tmp = DataFrameModel()
        tmp.setDataFrame(df)
        keep = None
        for col_name, allowed in self._value_filters.items():
            if col_name not in df.columns or col_name not in tmp._display_columns:
                continue
            ci = tmp._display_columns.index(col_name)
            n = tmp.rowCount()
            keys = []
            for r in range(n):
                disp = tmp.data(tmp.index(r, ci), Qt.DisplayRole)
                keys.append("(空)" if disp in (None, "") else str(disp))
            mask = pd.Series(keys, index=df.index).isin(allowed)
            keep = mask if keep is None else (keep & mask)
        if keep is None:
            return df
        return df[keep]

    # ---- 弹层 ----
    def open_filter(self, logical_index):
        """在点击列头处弹出 Excel 式取值勾选浮层。"""
        sm = self.source_model_getter()
        if sm is None or not hasattr(sm, "_display_columns"):
            return
        if logical_index < 0 or logical_index >= len(sm._display_columns):
            return
        col_name = sm._display_columns[logical_index]

        # 收集本列全部展示值及计数（保持首次出现顺序）
        n = sm.rowCount()
        cnt = {}
        order = []
        for r in range(n):
            disp = sm.data(sm.index(r, logical_index), Qt.DisplayRole)
            key = "(空)" if disp in (None, "") else str(disp)
            if key not in cnt:
                cnt[key] = 0
                order.append(key)
            cnt[key] += 1
        if not order:
            return

        prev = set(self._value_filters.get(col_name, set()))

        if self._popup is not None:
            try:
                self._popup.close()
            except Exception:
                pass
            self._popup = None

        popup = QWidget(self.table_view, Qt.Popup)
        popup.setObjectName("colFilterPopup")
        popup.setMinimumWidth(260)
        popup.setMaximumHeight(420)
        outer = QVBoxLayout(popup)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        title = QLabel(f"筛选：{col_name}（共 {n} 行 / {len(order)} 个值）")
        title.setStyleSheet("font-weight:bold;color:#15598c;")
        outer.addWidget(title)

        search = QLineEdit()
        search.setPlaceholderText("搜索取值…")
        outer.addWidget(search)

        btn_row = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_none = QPushButton("清空")
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

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

        btn_all.clicked.connect(select_all)
        btn_none.clicked.connect(select_none)

        ok_row = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        ok_row.addStretch(1)
        ok_row.addWidget(btn_cancel)
        ok_row.addWidget(btn_ok)
        outer.addLayout(ok_row)

        def do_apply():
            selected = {key for key, cb in items if cb.isChecked()}
            if selected == set(order):
                # 全选等价于不过滤：清掉该列取值过滤与漏斗标
                self._value_filters.pop(col_name, None)
                self._filtered_col_set.discard(logical_index)
            else:
                self._value_filters[col_name] = selected
                self._filtered_col_set.add(logical_index)
            self._popup = None
            self.apply_filter_cb()
            try:
                self.header.viewport().update()
            except Exception:
                pass
            popup.close()

        btn_ok.clicked.connect(do_apply)
        btn_cancel.clicked.connect(popup.close)

        self._popup = popup

        # 定位到点击列头下方，并避免超出屏幕
        x = self.header.sectionViewportPosition(logical_index)
        y = self.header.height()
        gpos = self.header.viewport().mapToGlobal(QPoint(int(x), int(y)))
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
                gpos.setY(max(sg.top(), gpos.y() - ph - self.header.height()))
        popup.move(gpos)
