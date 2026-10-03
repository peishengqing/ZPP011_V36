# -*- coding: utf-8 -*-
"""「变动提醒」明细对话框（v43.127 从 main_window.py 抽出）。

背景
----
原先 ``MainWindow._show_audit_changes_dialog`` 是一个 337 行的方法（全文件最大单方法），
UI 构建、数据装载、筛选、复制、导出、标记已读全塞在里面。职责上它属于对话框，
不该待在 GUI 主窗口里。

设计要点
--------
* **本对话框不直接依赖 MainWindow 的任何方法**，只通过 4 个 Signal 与主窗通信：

  ==================  ============================================================
  Signal               主窗侧连接
  ==================  ============================================================
  ``log_requested``    ``self.log``——写状态栏/日志
  ``manual_marked``    ``self._on_manual_marked``——累加状态栏「已手动标记」计数
  ``locate_requested`` ``self._locate_row_in_main_table``——双击行定位主表
  ``read_synced``      主窗侧无需连接（保留给未来的联动），当前由本窗自己改 model
  ==================  ============================================================

  这样对话框可以脱离主窗单测，也避免了对 ``self._xxx`` 的隐式耦合。

* **写入主表已读状态仍在本窗内完成**：``_sync_main_read_status`` 直接改
  ``source_model`` 的 df 并 ``setDataFrame``。这是唯一必须触碰主表数据的地方，
  故 source_model 由构造参数注入。**只改 ``_read`` / ``_read_source`` 两列，
  不改任何业务数据**——即「关掉弹窗后主表不被修改」这条契约成立
  （只有用户在弹窗内主动点「标记为已读」才会写）。

* ``data_service``（``get_audit_changes`` / ``mark_changes_as_read``）由构造参数注入，
  本窗不做任何 SQLite 访问。
"""
import os
import subprocess
from datetime import datetime

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox,
    QProgressDialog, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from gui_pyside6.widgets.toast import toast

# 单次最多渲染行数（超出部分只能靠「导出Excel并打开」拿全量）
MAX_DISPLAY = 3000

_COLS = ["日期", "车间", "流程订单", "物料编码", "物料名称", "变更字段", "旧值", "新值"]


def _open_file(path):
    """跨平台打开文件（与 main_window._open_file 逐行同款）。

    这里**不复用** main_window 的模块级 ``_open_file``——反向 import 会造成
    gui_pyside6.dialogs → main_window 的循环依赖（main_window 本就 import 了
    本模块）。逻辑保持完全一致：Windows 走 os.startfile，macOS/Linux 走
    subprocess.run（注意是 run 不是 Popen，原实现就是 run）。
    """
    import platform
    system = platform.system()
    if system == 'Windows':
        os.startfile(path)
    elif system == 'Darwin':  # macOS
        subprocess.run(['open', path])
    else:  # Linux and others
        subprocess.run(['xdg-open', path])


class AuditChangesDialog(QDialog):
    """已审核记录变动明细：表格展示 + 字段筛选/关键字搜索/排序/复制 + 双击定位主表 + 手动导出。"""

    log_requested = Signal(str, str)      # (msg, level)——主窗写日志/状态栏
    manual_marked = Signal(int)           # (n)——主窗累加「手动标记已读」计数
    locate_requested = Signal(str)        # (data_id)——主窗定位该行，成功返回 True

    def __init__(self, changes, source_model=None, view_model=None,
                 data_service=None, parent=None):
        """
        :param changes: ``data_service.get_audit_changes()`` 返回的变动明细 list[dict]
        :param source_model: 主表 DataFrameModel（标记已读后回写 _read 列用）
        :param view_model: 主表 AnalysisViewModel（source_model 为空时兜底取 df）
        :param data_service: DataService 实例，提供 mark_changes_as_read
        :param parent: 父窗口（QDialog 的 parent，用于模态归属）
        """
        super().__init__(parent)
        self.changes = list(changes)
        self.source_model = source_model
        self.view_model = view_model
        self.data_service = data_service

        count = len(self.changes)
        display_len = min(count, MAX_DISPLAY)
        self.setWindowTitle(f"变动提醒（{count} 条）")
        self.resize(1100, 600)
        # 允许最大化/最小化（Windows 上最大化按钮需与最小化成对才稳定显示）
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        layout = QVBoxLayout(self)

        # ---- 工具栏：字段筛选 + 关键字搜索 ----
        tool_bar = QHBoxLayout()
        tool_bar.addWidget(QLabel("字段:"))
        self.field_combo = QComboBox()
        self.field_combo.addItems(["全部字段", "实际数量", "备注原因"])
        tool_bar.addWidget(self.field_combo)
        tool_bar.addSpacing(12)
        tool_bar.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("日期 / 车间 / 流程订单 / 物料编码 / 物料名称")
        tool_bar.addWidget(self.search_edit, 1)
        layout.addLayout(tool_bar)

        extra = (f"（仅显示前 {display_len} 条，共 {count} 条；导出按钮可导出全部）"
                 if count > display_len else "")
        tip = QLabel(
            f"发现 {count} 条已审核记录的实际数量/备注原因发生变动，已强制设为'未读'。\n"
            f"（表格可排序/筛选/搜索，右键复制单元格或整行，双击定位到主表对应行）{extra}")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Ctrl/Shift 多选
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # 待处理变动列表（标记已读后从此移除并刷新表格）；
        # 行内 UserRole 存 remaining 索引，排序/部分标记后仍可正确映射
        self.remaining = list(self.changes)

        # 主窗侧 connect(locate_requested) 时会覆写此属性，返回「定位是否成功」。
        # 默认 False：未被主窗接管时双击不关窗（宁可不关，也不要在无主窗时误关）。
        self.locate_succeeded = lambda: False

        # ---- 右键菜单 ----
        self._ctx_index = [None]  # 记录右键所在单元格，避免整行选中导致取错列
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context)
        # ---- 过滤（字段筛选 + 关键字搜索）----
        self.search_edit.textChanged.connect(self._apply_filter)
        self.field_combo.currentTextChanged.connect(self._apply_filter)

        # ---- 双击定位到主表对应行（按当前行单元格重建 data_id，排序后仍正确）----
        self.table.doubleClicked.connect(self._on_double_click)

        # ---- 底部按钮 ----
        btn_box = QDialogButtonBox(self)
        self.export_btn = QPushButton("导出Excel并打开")
        self.mark_sel_btn = QPushButton("选中标记为已读")
        self.mark_read_btn = QPushButton("全部标记为已读（不再提醒）")
        ok_btn = QPushButton("确定")
        btn_box.addButton(self.export_btn, QDialogButtonBox.ActionRole)
        btn_box.addButton(self.mark_sel_btn, QDialogButtonBox.ActionRole)
        btn_box.addButton(self.mark_read_btn, QDialogButtonBox.ActionRole)
        btn_box.addButton(ok_btn, QDialogButtonBox.AcceptRole)
        layout.addWidget(btn_box)
        self.export_btn.clicked.connect(self._export)
        self.mark_sel_btn.clicked.connect(self._mark_selected_read)
        self.mark_read_btn.clicked.connect(self._mark_all_read)
        ok_btn.clicked.connect(self.accept)

        self._populate(self.remaining[:MAX_DISPLAY], with_progress=True)

    # ------------------------------------------------------------------ #
    # 表格填充
    # ------------------------------------------------------------------ #
    def _populate(self, show_list, with_progress=False):
        """按 show_list 重建表格内容。

        :param with_progress: 首次加载（数据量大）时显示进度对话框。
            标记已读后的增量刷新传False，避免闪一下进度条。
        """
        table = self.table
        table.setSortingEnabled(False)
        table.setRowCount(len(show_list))
        prog = None
        if with_progress and len(show_list) > 0:
            prog = QProgressDialog("正在加载变更明细...", None, 0, len(show_list), self)
            prog.setWindowTitle("加载变动提醒")
            prog.setWindowModality(Qt.WindowModal)
            prog.setMinimumDuration(300)
            prog.setValue(0)
        for i, c in enumerate(show_list):
            did = str(c.get('data_id', ''))
            parts = did.split('|')
            # 兼容 4 段（工厂|日期|流程订单|物料编码）和 3 段（日期|流程订单|物料编码）格式
            if len(parts) == 4:
                date, order, mat = parts[1], parts[2], parts[3]
            elif len(parts) >= 3:
                date, order, mat = parts[0], parts[1], parts[2]
            else:
                date, order, mat = '', '', ''
            wk = c.get('workshop', '') or ''
            old_v = c.get('old_value', '')
            new_v = c.get('new_value', '')
            it0 = QTableWidgetItem(date)
            it0.setData(Qt.UserRole, i)  # 存 remaining 索引
            table.setItem(i, 0, it0)
            table.setItem(i, 1, QTableWidgetItem(str(wk)))
            table.setItem(i, 2, QTableWidgetItem(order))
            table.setItem(i, 3, QTableWidgetItem(mat))
            table.setItem(i, 4, QTableWidgetItem(str(c.get('material_name', '') or '')))
            table.setItem(i, 5, QTableWidgetItem(str(c.get('field', ''))))
            table.setItem(i, 6, QTableWidgetItem('' if old_v is None else str(old_v)))
            table.setItem(i, 7, QTableWidgetItem('' if new_v is None else str(new_v)))
            if prog and (i + 1) % 200 == 0:
                prog.setValue(i + 1)
                QApplication.processEvents()
        if prog:
            prog.setValue(len(show_list))
            prog.close()
        # 列宽：手动设定固定/拉伸，避免 ResizeToContents 在大量行时逐行测量导致卡顿
        header = table.horizontalHeader()
        fixed_widths = {0: 100, 1: 90, 2: 100, 3: 110, 4: 200, 5: 90}
        for col, w in fixed_widths.items():
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            table.setColumnWidth(col, w)
        name_col = 4
        name_max_w = 200
        header.setSectionResizeMode(6, QHeaderView.Stretch)  # 旧值
        header.setSectionResizeMode(7, QHeaderView.Stretch)  # 新值
        # 仅在小数据量时做逐行字号缩放（大数据量跳过，避免逐行 QFontMetrics 卡顿）
        n = len(show_list)
        if n <= 2000:
            base_font = table.font()
            fm = QFontMetrics(base_font)
            pad = 12
            avail = name_max_w - pad
            max_text_w = 0
            for r in range(n):
                it = table.item(r, name_col)
                if it:
                    max_text_w = max(max_text_w, fm.horizontalAdvance(it.text()))
            if max_text_w > avail:
                ps = base_font.pointSizeF() or 9.0
                new_size = max(7.0, ps * avail / max_text_w)
                shrink_font = QFont(base_font)
                shrink_font.setPointSizeF(new_size)
                for r in range(n):
                    it = table.item(r, name_col)
                    if it:
                        it.setFont(shrink_font)
        table.setSortingEnabled(True)

    # ------------------------------------------------------------------ #
    # 筛选
    # ------------------------------------------------------------------ #
    def _apply_filter(self):
        """按「字段」下拉 + 「搜索」关键字过滤行（隐藏而非删除，索引保持稳定）。"""
        table = self.table
        kw = self.search_edit.text().strip().lower()
        fsel = self.field_combo.currentText()
        for r in range(table.rowCount()):
            show = True
            if fsel != "全部字段" and table.item(r, 5).text() != fsel:
                show = False
            if show and kw:
                hay = ' '.join(table.item(r, cc).text().lower() for cc in (0, 1, 2, 3, 4))
                if kw not in hay:
                    show = False
            table.setRowHidden(r, not show)

    # ------------------------------------------------------------------ #
    # 右键：复制单元格 / 复制整行 / 标记已读
    # ------------------------------------------------------------------ #
    def _copy_cell(self):
        idx = self._ctx_index[0]
        if idx is None or not idx.isValid():
            idxs = self.table.selectedIndexes()
            idx = idxs[0] if idxs else None
        if idx is not None and idx.isValid():
            QApplication.clipboard().setText(str(idx.data() or ''))
            toast("已复制单元格", parent=self)

    def _copy_row(self):
        table = self.table
        r = table.currentRow()
        if r < 0:
            return
        vals = []
        for cc in range(table.columnCount()):
            it = table.item(r, cc)
            vals.append(it.text() if it else '')
        QApplication.clipboard().setText('\t'.join(vals))
        toast("已复制整行", parent=self)

    def _on_context(self, pos):
        self._ctx_index[0] = self.table.indexAt(pos)
        menu = QMenu()
        a_cell = menu.addAction("复制单元格")
        a_row = menu.addAction("复制整行")
        menu.addSeparator()
        a_mark_read = menu.addAction("标记为已读（选中行）")
        act = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if act == a_cell:
            self._copy_cell()
        elif act == a_row:
            self._copy_row()
        elif act == a_mark_read:
            self._mark_selected_read()

    # ------------------------------------------------------------------ #
    # 双击定位主表
    # ------------------------------------------------------------------ #
    def _on_double_click(self, idx):
        """双击行 → emit locate_requested(data_id)；主窗定位成功才关窗。

        Qt 的 ``Signal.emit()`` 恒返回 None，拿不到主窗定位的结果。
        故主窗侧 connect 时会往本窗的 ``locate_succeeded`` 挂一个闭包，
        返回 ``_locate_row_in_main_table(data_id)`` 的布尔结果，这里据此决定是否关窗。
        """
        if not idx.isValid():
            return
        r = idx.row()
        if r < 0:
            return
        d = self.table.item(r, 0).text()
        o = self.table.item(r, 2).text()
        m = self.table.item(r, 3).text()
        did = '|'.join([d, o, m])
        self.locate_requested.emit(did)
        if self.locate_succeeded():
            self.accept()

    # ------------------------------------------------------------------ #
    # 导出
    # ------------------------------------------------------------------ #
    def _export(self):
        """把**全部**变动（不受 MAX_DISPLAY 限制）导出到临时目录的 xlsx 并打开。"""
        try:
            tmp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp",
                                   "zpp011_audit_changes")
            os.makedirs(tmp_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(tmp_dir, f"audit_changes_{ts}.xlsx")
            rows = []
            for c in self.changes:
                did = str(c.get('data_id', ''))
                parts = did.split('|')
                rows.append({
                    '日期': parts[0] if len(parts) > 0 else '',
                    '车间': c.get('workshop', '') or '',
                    '流程订单': parts[1] if len(parts) > 1 else '',
                    '物料编码': parts[2] if len(parts) > 2 else '',
                    '物料名称': c.get('material_name', '') or '',
                    '变更字段': c.get('field', ''),
                    '旧值': '' if c.get('old_value') is None else c.get('old_value'),
                    '新值': '' if c.get('new_value') is None else c.get('new_value'),
                })
            pd.DataFrame(rows).to_excel(path, index=False)
            _open_file(path)
            toast(f"已导出并打开：{path}", parent=self)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出失败：{e}")

    # ------------------------------------------------------------------ #
    # 标记已读
    # ------------------------------------------------------------------ #
    def _get_df_for_mark(self):
        """构造用于标记已读的主表快照 df（优先 source_model，其次 view_model.df，最后最小 data_id df）。"""
        df = None
        if self.source_model:
            df = self.source_model.getDataFrame()
        if df is None or (hasattr(df, 'empty') and df.empty):
            df = getattr(self.view_model, 'df', None)
            if df is not None and not (hasattr(df, 'empty') and df.empty):
                self.log_requested.emit(
                    "source_model 为空，使用 view_model.df 作为已读快照", "warning")
        if df is None or (hasattr(df, 'empty') and df.empty):
            data_ids = list(dict.fromkeys(
                [str(c.get('data_id', '')) for c in self.remaining if c.get('data_id')]))
            if not data_ids:
                return None
            df = pd.DataFrame({'data_id': data_ids})
            self.log_requested.emit(
                "主表数据为空，以最小 data_id 列标记变动已读（不保存当前值快照）", "warning")
        return df

    def _sync_main_read_status(self, dids):
        """把一组 data_id 对应的主表行 _read 设为 1 并触发界面刷新。

        只写 ``_read`` / ``_read_source`` 两列，**不动任何业务列**——
        这是「关掉弹窗主表不被修改」这条契约的实现处。
        """
        if not dids or not self.source_model:
            return
        df = self.source_model.getDataFrame()
        if df is None or (hasattr(df, 'empty') and df.empty):
            return
        if 'data_id' not in df.columns or '_read' not in df.columns:
            return
        mask = df['data_id'].astype(str).isin(dids)
        if mask.any():
            df.loc[mask, '_read'] = 1
            df.loc[mask, '_read_source'] = 'manual'
            self.source_model.setDataFrame(df)

    def _mark_selected_read(self):
        """把当前选中的行（点击高亮即选中，Ctrl/Shift 可多选）标记为已读，并从列表移除。"""
        table = self.table
        sel = table.selectedIndexes()
        if not sel:
            QMessageBox.information(
                self, "提示", "请先选中要标记的行（点击行即高亮选中，Ctrl/Shift 可多选）。")
            return
        rows = sorted({idx.row() for idx in sel})
        idxs = []
        for r in rows:
            ud = table.item(r, 0).data(Qt.UserRole)
            if isinstance(ud, int) and 0 <= ud < len(self.remaining):
                idxs.append(ud)
        if not idxs:
            return
        idxs = sorted(set(idxs))
        sub_changes = [self.remaining[i] for i in idxs]
        df = self._get_df_for_mark()
        if df is None:
            QMessageBox.warning(self, "提示", "主表数据为空且无有效 data_id，无法标记已读。")
            return
        n, marked_dids = self.data_service.mark_changes_as_read(sub_changes, df)
        if n > 0:
            self._sync_main_read_status(marked_dids)
            self.manual_marked.emit(n)  # 累加主窗状态栏「手动标记」计数
            # 从 remaining 移除已标记行（按 data_id+变更字段 去重，避免误删未选中的同名行）
            marked_keys = {(str(c.get('data_id', '')), str(c.get('field', '')))
                           for c in sub_changes}
            new_remaining = [c for c in self.remaining
                             if (str(c.get('data_id', '')), str(c.get('field', '')))
                             not in marked_keys]
            self.remaining[:] = new_remaining
            self.setWindowTitle(f"变动提醒（{len(self.remaining)} 条）")
            self._populate(self.remaining[:MAX_DISPLAY])
            self._apply_filter()
            toast(f"已把 {n} 条标记为已读（剩余 {len(self.remaining)} 条）", parent=self)
            if not self.remaining:
                toast("已全部标记为已读", parent=self)
                self.accept()
        else:
            QMessageBox.warning(self, "标记失败", "未能标记所选行为已读，请检查数据。")

    def _mark_all_read(self):
        """把剩余全部变动标记为已读并关窗（下次不再提醒）。"""
        try:
            df = self._get_df_for_mark()
            if df is None:
                QMessageBox.warning(self, "提示", "主表数据为空且无有效 data_id，无法标记已读。")
                return
            marked_dids = {str(c.get('data_id', '')) for c in self.remaining if c.get('data_id')}
            n, _ = self.data_service.mark_changes_as_read(self.remaining, df)
            if n > 0:
                self._sync_main_read_status(marked_dids)
                self.manual_marked.emit(n)  # 累加主窗状态栏计数
                toast(f"已把 {n} 条记录标记为已读，下次不再提醒", parent=self)
            self.remaining[:] = []
            self.setWindowTitle("变动提醒（0 条）")
            self._populate([])
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "标记失败", f"标记已读失败：{e}")
