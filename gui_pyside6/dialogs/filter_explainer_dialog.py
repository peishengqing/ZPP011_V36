# -*- coding: utf-8 -*-
"""
筛选解释器（Phase 6 / v43.271）

用途：
    用户在筛选后想弄清楚"为什么这几行没显示"——打开本对话框：
      · 左侧：列出被筛选排除掉的原始行（默认取前 500 行）
      · 右侧：选中若干行后，展示每条筛选规则对它们的匹配结果（✓/✗ + 实际值）
      · 底部：一键复制当前摘要（方便贴到工单/群里问同事）

调用方式（main_window）：
    dialog = FilterExplainerDialog(parent, self.filter_controller)
    dialog.exec_()
"""

from typing import Optional
import pandas as pd

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QWidget,
)

from gui_pyside6.controllers.filter_controller import FilterController
from gui_pyside6.models.store import AppState


# 被排除行最多显示多少条（性能保护）
MAX_EXCLUDED_ROWS = 500


class FilterExplainerDialog(QDialog):
    """筛选解释器对话框"""

    def __init__(self, parent, filter_controller: FilterController):
        super().__init__(parent)
        self.controller = filter_controller
        self.app_state: Optional[AppState] = filter_controller.app_state

        self.setWindowTitle("筛选解释器 · 为什么这 X 条没显示")
        self.resize(1280, 640)

        self._source_df = None        # 原始 DataFrame
        self._excluded_df = None      # 被排除的 DataFrame（视图）
        self._selected_indices = set()

        self._setup_ui()
        self._refresh_data()

    # ================ UI 搭建 ================

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)

        # ---------- 顶部：搜索 + 摘要 ----------
        top = QHBoxLayout()
        top.setSpacing(8)

        title_lbl = QLabel("🔍 筛选解释器")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_lbl.setFont(title_font)
        top.addWidget(title_lbl)

        top.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("在被排除行中搜索（物料编码 / 流程订单 / 备注…）")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_search)
        top.addWidget(self.search_edit, 1)

        self.summary_label = QLabel("加载中…")
        self.summary_label.setStyleSheet("color: #444; padding: 2px 8px; background: #f0f0f0; border-radius: 3px;")
        top.addWidget(self.summary_label)
        main.addLayout(top)

        # ---------- 中间：左右两栏 ----------
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)

        # 左：被排除行列表
        left_wrap = QWidget()
        left_v = QVBoxLayout(left_wrap)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(4)

        left_head = QLabel("<b>被排除的行</b> · 点击勾选，右侧会显示逐条规则解释（Ctrl/Ctrl+Shift 多选）")
        left_head.setStyleSheet("color: #666; font-size: 11px;")
        left_v.addWidget(left_head)

        self.list_table = QTableWidget()
        self.list_table.setAlternatingRowColors(True)
        self.list_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_table.verticalHeader().setVisible(False)
        self.list_table.setSortingEnabled(False)
        self.list_table.itemSelectionChanged.connect(self._on_selection_changed)
        left_v.addWidget(self.list_table, 1)

        left_footer = QLabel("提示：只展示前 %d 行（性能保护），如需更多请先减少筛选条件。" % MAX_EXCLUDED_ROWS)
        left_footer.setStyleSheet("color: #999; font-size: 10px; padding-left: 4px;")
        left_footer.setWordWrap(True)
        left_v.addWidget(left_footer)

        splitter.addWidget(left_wrap)

        # 右：解释表
        right_wrap = QWidget()
        right_v = QVBoxLayout(right_wrap)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(4)

        right_head = QLabel("<b>逐条规则解释</b> · ✓=通过（保留）✗=未通过（排除）")
        right_head.setStyleSheet("color: #666; font-size: 11px;")
        right_v.addWidget(right_head)

        self.explain_table = QTableWidget()
        self.explain_table.setAlternatingRowColors(True)
        self.explain_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.explain_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.explain_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.explain_table.verticalHeader().setVisible(False)
        right_v.addWidget(self.explain_table, 1)

        splitter.addWidget(right_wrap)

        splitter.setSizes([520, 720])
        main.addWidget(splitter, 1)

        # ---------- 底部：按钮 ----------
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.select_all_btn = QPushButton("全选当前可见")
        self.select_all_btn.clicked.connect(self._select_all_visible)
        btn_row.addWidget(self.select_all_btn)

        self.clear_sel_btn = QPushButton("清空选择")
        self.clear_sel_btn.clicked.connect(self._clear_selection)
        btn_row.addWidget(self.clear_sel_btn)

        btn_row.addStretch()

        self.copy_btn = QPushButton("📋 复制摘要")
        self.copy_btn.clicked.connect(self._copy_summary)
        btn_row.addWidget(self.copy_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.close_btn)

        main.addLayout(btn_row)

    # ================ 数据刷新 ================

    def _refresh_data(self):
        """重新加载原始数据、计算被排除行、刷新左侧列表"""
        self._source_df = self.app_state.get_data()
        if self._source_df is None or len(self._source_df) == 0:
            self.summary_label.setText("无原始数据，无法解释。请先导入数据。")
            self.list_table.setRowCount(0)
            self.list_table.setColumnCount(0)
            self.explain_table.setRowCount(0)
            self.explain_table.setColumnCount(0)
            return

        filtered = self.app_state.get_filtered_data()
        filtered_set = set(filtered.index.tolist()) if filtered is not None else set()
        excluded_idx = [i for i in self._source_df.index.tolist() if i not in filtered_set]

        if excluded_idx:
            excluded_df = self._source_df.loc[excluded_idx]
        else:
            # 无排除行（筛选为空或全部通过）
            excluded_df = self._source_df.iloc[0:0].copy()
        self._excluded_df = excluded_df

        total = len(self._source_df)
        kept = 0 if filtered is None else len(filtered)
        excluded = total - kept

        # 尝试获取排除原因摘要
        top_reason = ""
        try:
            summary = self.controller.summarize_exclusions()
            top_reason = summary.get('top_reason') or ""
        except Exception:
            pass

        hint = f"共 {total} 行 · 保留 {kept} · 排除 {excluded}"
        if top_reason:
            hint += f" · 主要因: {top_reason}"
        if excluded > MAX_EXCLUDED_ROWS:
            hint += f"（列表只显示前 {MAX_EXCLUDED_ROWS} 行）"
        self.summary_label.setText(hint)

        self._refresh_list()
        self._refresh_explain()

    def _refresh_list(self):
        """刷新左侧被排除行列表"""
        df = self._excluded_df if self._excluded_df is not None else self._source_df.iloc[0:0]
        df_view = df.head(MAX_EXCLUDED_ROWS)

        # 挑选展示列：优先业务常用列，最多 8 列
        preferred = [
            '工厂', '工厂名称', '车间', '流程订单', '订单日期',
            '物料编码', '物料名称', '偏差金额(含税)', '偏差率',
            '是否替代料', '备注原因',
        ]
        cols = [c for c in preferred if c in df_view.columns]
        if len(cols) < 5:
            for c in df_view.columns:
                if c not in cols:
                    cols.append(c)
                if len(cols) >= 8:
                    break

        self.list_table.setSortingEnabled(False)
        self.list_table.clear()
        self.list_table.setColumnCount(len(cols))
        self.list_table.setHorizontalHeaderLabels(cols)
        self.list_table.setRowCount(len(df_view))

        for r, (orig_idx, row) in enumerate(df_view.iterrows()):
            for c, col in enumerate(cols):
                v = row.get(col)
                text = self._fmt_cell(v)
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, orig_idx)
                # 让每一列都可触发选中（但整行一起选）
                self.list_table.setItem(r, c, item)

        # 列宽自适应，但设置合理上下限
        hh = self.list_table.horizontalHeader()
        for c in range(len(cols)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        # 表头行高
        self.list_table.verticalHeader().setDefaultSectionSize(22)
        self.list_table.setSortingEnabled(True)

    def _refresh_explain(self):
        """根据左侧选中，刷新右侧逐条规则解释表"""
        self.explain_table.setSortingEnabled(False)
        self.explain_table.clear()

        rules = self.controller.get_filters()

        if not rules:
            self.explain_table.setColumnCount(1)
            self.explain_table.setRowCount(1)
            self.explain_table.setHorizontalHeaderLabels(["提示"])
            tip = QTableWidgetItem("当前没有任何筛选规则 —— 所有行都会显示。请先在筛选面板添加至少一个条件。")
            tip.setForeground(QColor(180, 60, 60))
            self.explain_table.setItem(0, 0, tip)
            self.explain_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            self.explain_table.setSortingEnabled(True)
            return

        if not self._selected_indices:
            self.explain_table.setColumnCount(1)
            self.explain_table.setRowCount(1)
            self.explain_table.setHorizontalHeaderLabels(["提示"])
            tip = QTableWidgetItem("← 请在左侧勾选若干行被排除的记录，这里将逐条列出为什么被排除。")
            tip.setForeground(QColor(120, 120, 120))
            self.explain_table.setItem(0, 0, tip)
            self.explain_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            self.explain_table.setSortingEnabled(True)
            return

        # 调 controller 计算
        try:
            explanations = self.controller.explain_rows(sorted(self._selected_indices))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.explain_table.setColumnCount(1)
            self.explain_table.setRowCount(1)
            self.explain_table.setHorizontalHeaderLabels(["错误"])
            err = QTableWidgetItem(f"解释失败: {e}")
            err.setForeground(QColor(180, 60, 60))
            self.explain_table.setItem(0, 0, err)
            self.explain_table.setSortingEnabled(True)
            return

        # 构建表头：行摘要 + N 条规则
        headers = ["#  原始行摘要"]
        for i, r in enumerate(rules):
            val_disp = self._fmt_cell(r.value)
            headers.append(f"规则{i+1}\n{r.column} {r.condition} {val_disp}")

        col_count = 1 + len(rules)
        row_count = len(explanations)

        self.explain_table.setColumnCount(col_count)
        self.explain_table.setRowCount(row_count)
        self.explain_table.setHorizontalHeaderLabels(headers)

        # 表格样式
        self.explain_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.explain_table.verticalHeader().setDefaultSectionSize(56)

        pass_bg = QColor(220, 245, 220)
        fail_bg = QColor(255, 224, 220)
        pass_fg = QColor(30, 100, 30)
        fail_fg = QColor(140, 30, 30)

        for r, exp in enumerate(explanations):
            # 第 0 列：行摘要
            summary_text = f"[#{exp['row_index']}]\n{exp['summary']}"
            sum_item = QTableWidgetItem(summary_text)
            sum_item.setData(Qt.UserRole, exp['row_index'])
            sum_item.setFlags(Qt.NoItemFlags)  # 不可选
            sum_item.setForeground(QColor(60, 60, 60))
            self.explain_table.setItem(r, 0, sum_item)

            # 每条规则
            for i, rr in enumerate(exp['rule_results']):
                passed = rr['passed']
                icon = "✓" if passed else "✗"
                cell_text = (
                    f"{icon}\n"
                    f"期望: {rr['expected']}\n"
                    f"实际: {rr['actual']}"
                )
                item = QTableWidgetItem(cell_text)
                item.setBackground(pass_bg if passed else fail_bg)
                item.setForeground(pass_fg if passed else fail_fg)
                item.setFlags(Qt.NoItemFlags)
                item.setToolTip(
                    f"规则 {rr['rule_index']+1}\n"
                    f"字段: {rr['column']}\n"
                    f"条件: {rr['condition']} {rr['expected']}\n"
                    f"实际值: {rr['actual']}\n"
                    f"结果: {'通过（保留）' if passed else '未通过（排除）'}"
                )
                self.explain_table.setItem(r, i + 1, item)

        # 列宽
        self.explain_table.setColumnWidth(0, 280)
        for c in range(1, col_count):
            self.explain_table.setColumnWidth(c, 140)
        self.explain_table.setSortingEnabled(True)

    # ================ 事件处理 ================

    def _on_selection_changed(self):
        items = self.list_table.selectedItems()
        indices = set()
        for item in items:
            v = item.data(Qt.UserRole)
            if v is not None:
                try:
                    indices.add(int(v))
                except (TypeError, ValueError):
                    continue
        self._selected_indices = indices
        self._update_footer()
        self._refresh_explain()

    def _update_footer(self):
        excluded = len(self._excluded_df) if self._excluded_df is not None else 0
        total = len(self._source_df) if self._source_df is not None else 0
        sel = len(self._selected_indices)
        text = f"共 {total} 行 · 排除 {excluded} · 已选 {sel} 行"
        if excluded > MAX_EXCLUDED_ROWS:
            text += f"（列表截断显示前 {MAX_EXCLUDED_ROWS}）"
        # 主摘要里也带上主要因
        try:
            summary = self.controller.summarize_exclusions()
            top = summary.get('top_reason')
            if top:
                text += f" · 主要因: {top}"
        except Exception:
            pass
        self.summary_label.setText(text)

    def _apply_search(self):
        # 简单过滤：把当前表按搜索词隐藏不匹配的行
        keyword = self.search_edit.text().strip().lower()
        for r in range(self.list_table.rowCount()):
            row_visible = not keyword
            if not row_visible:
                for c in range(self.list_table.columnCount()):
                    cell = self.list_table.item(r, c)
                    if cell and keyword in (cell.text() or "").lower():
                        row_visible = True
                        break
            self.list_table.setRowHidden(r, not row_visible)

    def _select_all_visible(self):
        # 选中所有未隐藏的行
        for r in range(self.list_table.rowCount()):
            if not self.list_table.isRowHidden(r):
                self.list_table.selectRow(r)

    def _clear_selection(self):
        self.list_table.clearSelection()
        self._selected_indices = set()
        self._update_footer()
        self._refresh_explain()

    def _copy_summary(self):
        """复制当前解释结果到剪贴板（纯文本，便于贴工单）"""
        rules = self.controller.get_filters()
        lines = []
        lines.append("=== ZPP011 筛选解释器 ===")
        if not rules:
            lines.append("(当前无筛选规则)")
            self._set_clipboard("\n".join(lines))
            return

        lines.append(f"规则总数: {len(rules)}")
        for i, r in enumerate(rules):
            lines.append(f"  规则{i+1}: {r.column} {r.condition} {self._fmt_cell(r.value)}")
        lines.append("")

        try:
            summary = self.controller.summarize_exclusions()
            lines.append(f"总计: {summary['total']} 行 · 保留 {summary['kept']} · 排除 {summary['excluded']}")
            lines.append(f"主要因: {summary.get('top_reason') or '(无排除)'}")
            lines.append("")
            lines.append("--- 每条规则单独排除的行数 ---")
            for pr in summary.get('per_rule', [])[:10]:
                lines.append(f"  规则{pr['rule_index']+1} {pr['column']} {pr['condition']} {pr['value']}  →  排除 {pr['fail_count']} 行")
        except Exception as e:
            lines.append(f"(统计失败: {e})")

        lines.append("")
        if self._selected_indices:
            lines.append(f"=== 选中 {len(self._selected_indices)} 行的逐条解释 ===")
            try:
                explanations = self.controller.explain_rows(sorted(self._selected_indices))
                for exp in explanations:
                    lines.append(f"\n[行 {exp['row_index']}]  {exp['summary']}")
                    for rr in exp['rule_results']:
                        mark = "✓" if rr['passed'] else "✗"
                        lines.append(f"  规则{rr['rule_index']+1} {mark} {rr['column']} {rr['condition']} {rr['expected']}  → 实际: {rr['actual']}")
            except Exception as e:
                lines.append(f"(解释失败: {e})")
        else:
            lines.append("(未选中任何行，跳过逐条解释)")

        self._set_clipboard("\n".join(lines))

    def _set_clipboard(self, text):
        app = QApplication.instance()
        if app is None:
            return
        clipboard = app.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    # ================ 工具 ================

    @staticmethod
    def _fmt_cell(v) -> str:
        if v is None:
            return "(空)"
        try:
            if pd.isna(v):
                return "(空)"
        except (TypeError, ValueError):
            pass
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        s = str(v)
        return s if len(s) <= 60 else s[:57] + "..."

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)
