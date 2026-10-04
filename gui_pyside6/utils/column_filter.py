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
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QScrollArea, QApplication, QMenu,
)
from gui_pyside6.utils.click_debug import click_log


def _click_log(msg):
    """点击链路诊断日志：默认关闭，设 ZPP011_CLICK_DEBUG=1 才写盘（见 click_debug）。"""
    click_log(msg)


class ColumnFilterController(QObject):
    """Excel 式列头取值筛选控制器。"""

    filtered_cols_changed = Signal()  # 筛选列集合变化（供 UI 显示「已筛 N 列 / 哪些列」提示）

    def __init__(self, table_view, header, sort_ctrl, source_model_getter,
                 apply_filter_cb, skip_cols=(0,), parent=None):
        """
        :param table_view: 目标 QTableView
        :param header: 表头（SortBadgeHeader），用于漏斗绘制与浮层定位
        :param sort_ctrl: HeaderSortController（非筛选模式下委托其处理排序）
        :param source_model_getter: callable -> 当前显示的 DataFrameModel（用于实时读取 DisplayRole 取值）
        :param apply_filter_cb: callable -> 重新执行对话框过滤（会读取本控制器的 value_filters 叠加过滤）
        :param skip_cols: 不参与筛选/排序的列号集合（如内部 _read 列）
        """
        super().__init__(parent)
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
        # 已筛选列表头左侧漏斗图标：点击直接打开该列取值筛选浮层（无需先开启「列头筛选」模式）
        try:
            self.header.set_funnel_clicked(self._on_funnel_clicked)
        except Exception:
            pass

    def _on_funnel_clicked(self, logical_index):
        """点击表头左侧漏斗图标：直接打开该列取值筛选浮层（无需先开启「列头筛选」模式）。"""
        if logical_index in self.skip_cols:
            return
        _click_log(f"[funnel] 点击漏斗 col={logical_index} → 直接打开筛选浮层")
        # 延到下一事件循环再弹层，规避 mouseReleaseEvent 同步 show Qt.Popup 被立即 dismiss 的坑
        QTimer.singleShot(0, lambda: self.open_filter(logical_index))

    # ---- 状态查询 ----
    @property
    def filtered_col_set(self):
        return self._filtered_col_set

    def get_value_filters(self):
        return self._value_filters

    def has_any(self):
        return bool(self._value_filters)

    def get_filtered_col_names(self, display_cols=None):
        """已设取值过滤的列名列表（按列号升序），供提示菜单/清除菜单显示。"""
        cols = list(display_cols or [])
        names = []
        for c in sorted(self._filtered_col_set):
            if 0 <= c < len(cols):
                names.append(str(cols[c]))
            else:
                names.append("列%d" % c)
        return names

    def clear_column(self, col_name, clear_sort=True):
        """清除单列取值过滤（= Excel 式「取消此列筛选」）。返回是否确有清除。

        v43.144：`clear_sort=True` 时连带取消该列的排序。原先只清筛选不清排序，
        用户取消后该列的排序箭头仍留着，视觉上像「还在筛」这一列。
        """
        if col_name not in self._value_filters:
            return False
        self._value_filters.pop(col_name, None)
        idxs = [c for c, n in self._col_name_to_index(col_name)]
        for c in idxs:
            self._filtered_col_set.discard(c)
        if clear_sort and idxs:
            self._clear_sort_for_cols(idxs)
        self.filtered_cols_changed.emit()
        self._safe_repaint()
        self.apply_filter_cb()
        return True

    def clear_all(self, clear_sort=True):
        """清除全部列头取值过滤。返回是否确有清除。

        v43.144：`clear_sort=True` 时连带取消被筛列的排序。
        """
        if not self._value_filters and not self._filtered_col_set:
            return False
        idxs = sorted(self._filtered_col_set)
        self._value_filters.clear()
        self._filtered_col_set.clear()
        if clear_sort and idxs:
            self._clear_sort_for_cols(idxs)
        self.filtered_cols_changed.emit()
        self._safe_repaint()
        self.apply_filter_cb()
        return True

    def _clear_sort_for_cols(self, col_indexes):
        """取消指定列号上的排序（走 sort_ctrl，失败静默，不影响筛选主流程）。"""
        sc = self.sort_ctrl
        if sc is None:
            return
        for c in col_indexes:
            try:
                sc.clear_column_sort(c)
            except Exception:
                pass

    def _col_name_to_index(self, col_name):
        """列名 -> [(列号, 列名)]，用于反查 _filtered_col_set 里的列号。"""
        sm = self.source_model_getter()
        cols = getattr(sm, "_display_columns", []) if sm is not None else []
        out = []
        if col_name in cols:
            out.append((cols.index(col_name), col_name))
        # 兜底：列名不在当前显示列里（列被隐藏/改名），按字符串兜底匹配漏斗标
        for c in sorted(self._filtered_col_set):
            if 0 <= c < len(cols) and str(cols[c]) == col_name:
                out.append((c, col_name))
        return out

    def _safe_repaint(self):
        """触发表头重画（Qt6 自绘画在表头本体，必须 header.update() 而非 viewport）。"""
        try:
            self.header.update()
        except Exception:
            pass

    def attach_clear_menu(self, label, display_cols_getter=None):
        """给「🔽 列头筛选：N 列」提示标签挂上清除菜单（右键弹出）。

        v43.143：此前该标签是纯 QLabel，用户想取消筛选只能开浮层重新勾一遍
        （且关掉筛选模式开关并不清筛选），观感=「无法取消」。现右键标签即可
        逐列清除 / 一键清除全部。
        """
        if label is None:
            return
        label.setContextMenuPolicy(Qt.CustomContextMenu)
        label.customContextMenuRequested.connect(
            lambda pos: self._show_clear_menu(label, pos, display_cols_getter))

    def _show_clear_menu(self, label, pos, display_cols_getter=None):
        cols = []
        if callable(display_cols_getter):
            try:
                cols = display_cols_getter() or []
            except Exception:
                cols = []
        if not cols:
            sm = self.source_model_getter()
            cols = getattr(sm, "_display_columns", []) if sm is not None else []
        menu = QMenu(label)
        if not self._filtered_col_set:
            act = menu.addAction("当前没有列头筛选")
            act.setEnabled(False)
        else:
            menu.addSection("逐列清除")
            for name in self.get_filtered_col_names(cols):
                menu.addAction("清除此列：%s" % name,
                               lambda _=False, n=name: self.clear_column(n))
            menu.addSeparator()
            menu.addAction("清除全部列头筛选", self.clear_all)
        menu.exec(label.mapToGlobal(pos))

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
        # v43.116 诊断：真实鼠标点列头无反应时，先确认信号是否到达 + 走的哪个分支
        _click_log(f"[route] on_header_clicked idx={logical_index} filter_mode={self._col_filter_mode} "
                   f"ctrl={ctrl} skip={self.skip_cols}")
        if self._col_filter_mode and logical_index > 0 and not ctrl:
            # 延到下一事件循环再弹层：表头 sectionClicked 在 QHeaderView.mouseReleaseEvent
            # 内部触发，若同步 show Qt.Popup 浮层会被本次鼠标交互立即 dismiss（主表用按钮
            # 触发则无此问题）。singleShot(0) 等鼠标事件完全退栈后再弹，规避该坑。
            QTimer.singleShot(0, lambda: self.open_filter(logical_index))
            return
        # 非筛选模式（或第0列 / Ctrl+点）：委托给排序控制器
        _click_log(f"[route] 委托排序 idx={logical_index}")
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

    def _open_empty_col_filter_popup(self, col_name, logical_index):
        """无取值时的兜底浮层：只提供「清除此列筛选」/「清除全部列头筛选」两个出口。"""
        if self._popup is not None:
            try:
                self._popup.close()
            except Exception:
                pass
            self._popup = None

        popup = QWidget(self.table_view, Qt.Popup)
        popup.setObjectName("colFilterPopup")
        popup.setMinimumWidth(280)
        outer = QVBoxLayout(popup)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        tip = QLabel(f"「{col_name}」当前没有任何可选取值\n（表格已被其它筛选条件筛空）")
        tip.setStyleSheet("font-weight:bold;color:#15598c;")
        tip.setWordWrap(True)
        outer.addWidget(tip)

        def do_clear_col():
            self._value_filters.pop(col_name, None)
            self._filtered_col_set.discard(logical_index)
            self._clear_sort_for_cols([logical_index])
            self.filtered_cols_changed.emit()
            self._popup = None
            self._safe_repaint()
            self.apply_filter_cb()
            popup.close()

        def do_clear_all():
            idxs = sorted(self._filtered_col_set)
            self._value_filters.clear()
            self._filtered_col_set.clear()
            self._clear_sort_for_cols(idxs)
            self.filtered_cols_changed.emit()
            self._popup = None
            self._safe_repaint()
            self.apply_filter_cb()
            popup.close()

        btn_col = QPushButton("清除此列筛选")
        btn_col.clicked.connect(do_clear_col)
        btn_all2 = QPushButton("清除全部列头筛选")
        btn_all2.clicked.connect(do_clear_all)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(popup.close)
        outer.addWidget(btn_col)
        outer.addWidget(btn_all2)
        outer.addWidget(btn_close)

        self._popup = popup
        x = self.header.sectionViewportPosition(logical_index)
        y = self.header.height()
        gpos = self.header.viewport().mapToGlobal(QPoint(int(x), int(y)))
        popup.show()
        popup.adjustSize()
        screen = QApplication.primaryScreen()
        if screen is not None:
            sg = screen.availableGeometry()
            gpos.setX(min(gpos.x(), max(sg.left(), sg.right() - popup.width())))
            gpos.setY(min(gpos.y(), max(sg.top(), sg.bottom() - popup.height())))
        popup.move(gpos)

    # ---- 弹层 ----
    def open_filter(self, logical_index):
        """在点击列头处弹出 Excel 式取值勾选浮层。"""
        sm = self.source_model_getter()
        if sm is None or not hasattr(sm, "_display_columns"):
            _click_log(f"[popup] open_filter({logical_index}) 无源模型，直接返回")
            return
        if logical_index < 0 or logical_index >= len(sm._display_columns):
            _click_log(f"[popup] open_filter({logical_index}) 列号越界(cols={len(sm._display_columns)})")
            return
        col_name = sm._display_columns[logical_index]

        # 收集本列全部展示值及计数（保持首次出现顺序）
        # 性能（2026-10-02）：向量化取展示键（与 DisplayRole 一致），替代逐行 sm.data()
        n = sm.rowCount()
        from gui_pyside6.models.data_frame_model import build_display_key_list
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
            # 修复（v43.143）：本列在当前视图下没有任何取值（典型场景：被别的列筛成 0 行，
            # 或上一轮误留了空集过滤）。原先直接 return 不弹层 → 用户看着空表且点列头毫无
            # 反应，彻底无法取消。现弹一个只含「清除此列筛选」的浮层，给出逃生出口。
            _click_log(f"[popup] open_filter({logical_index}) 无数据行，弹清除浮层")
            self._open_empty_col_filter_popup(col_name, logical_index)
            return
        _click_log(f"[popup] open_filter({logical_index}) 弹层 '{col_name}' 共{n}行/{len(order)}值")

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
        btn_clear = QPushButton("清除此列")
        btn_clear.setToolTip("取消本列的全部取值过滤（等同恢复未筛选）")
        btn_clear.setEnabled(bool(self._value_filters.get(col_name)))
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addWidget(btn_clear)
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

        def do_clear_column():
            """「清除此列」：直接丢弃本列取值过滤 + 本列排序并关浮层。

            与「清空」区别：「清空」只是把勾选全取消，点确定后会因空集被当作
            「清除」处理，但用户不知道；这里给一个显式入口。
            v43.144：连带取消本列排序（原先箭头留着，像还在筛这一列）。
            """
            self._value_filters.pop(col_name, None)
            self._filtered_col_set.discard(logical_index)
            self._clear_sort_for_cols([logical_index])
            self.filtered_cols_changed.emit()
            self._popup = None
            self._safe_repaint()
            self.apply_filter_cb()
            popup.close()

        btn_all.clicked.connect(select_all)
        btn_none.clicked.connect(select_none)
        btn_clear.clicked.connect(do_clear_column)

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
                # 修复（v43.143）：原先「一个都没选」会写入空 set，mask_dataframe 里
                # `key not in allowed` 恒真 → 全表 0 行；此时再开浮层因 order 为空直接
                # 「不弹」，用户彻底无法取消（死锁）。现与主表 setValueFilter 语义对齐：
                # 空集 = 清除该列过滤。
                # v43.144：取消筛选时连带取消本列排序。
                self._value_filters.pop(col_name, None)
                self._filtered_col_set.discard(logical_index)
                self._clear_sort_for_cols([logical_index])
            else:
                self._value_filters[col_name] = selected
                self._filtered_col_set.add(logical_index)
            self.filtered_cols_changed.emit()
            self._popup = None
            self._safe_repaint()
            self.apply_filter_cb()
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
