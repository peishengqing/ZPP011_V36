# -*- coding: utf-8 -*-
"""导出列模板编辑器（模板自定义第一档）—— 勾选导出哪些列、什么顺序、要不要合计行。

裴哥 2026-11-14 · 模板自定义第一档

只服务「导出当前表格」。左侧候选列（df 里可导出的列，内部字段不出现），
右侧已选列（导出顺序，可上下移/拖拽），底部合计行开关。保存即落盘
config/export_template.json，下次导出按此模板走。

不动多 Sheet 完整报告（analysis 层硬编码，第一档范围外，见 core/export_template.py 说明）。
"""
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QCheckBox, QFrame, QMessageBox,
)

from core import export_template as et
from gui_pyside6.components import dialog_chrome


class ExportTemplateDialog(QDialog):
    """导出列模板编辑器。传 owner + 当前 df（决定候选列）。"""

    def __init__(self, owner=None, df=None):
        super().__init__(owner)
        self.owner = owner
        self.df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        dialog_chrome.apply(self, dialog_chrome.TIER_MEDIUM,
                            "导出列模板", "选择 · 排序 · 合计行")
        root = QVBoxLayout(self)
        root.setSpacing(10)

        tip = QLabel("勾选要导出的列并调好顺序（只对「导出当前表格」生效，"
                     "完整多 Sheet 报告不受影响）。内部字段（data_id 等）不参与导出。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#666;")
        root.addWidget(tip)

        # 左右两栏
        cols = QHBoxLayout()
        cols.setSpacing(12)

        # 左：候选列
        left = QVBoxLayout()
        left.addWidget(QLabel("候选列（点「添加」或双击加入导出）"))
        self.cand_list = QListWidget()
        self.cand_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.cand_list.itemDoubleClicked.connect(lambda _: self._add_selected())
        left.addWidget(self.cand_list, 1)
        cols.addLayout(left, 1)

        # 中：加减按钮
        mid = QVBoxLayout()
        mid.addStretch()
        self.add_btn = QPushButton("添加 →")
        self.add_btn.clicked.connect(self._add_selected)
        mid.addWidget(self.add_btn)
        self.remove_btn = QPushButton("← 移除")
        self.remove_btn.clicked.connect(self._remove_selected)
        mid.addWidget(self.remove_btn)
        mid.addStretch()
        cols.addLayout(mid)

        # 右：已选列（导出顺序）
        right = QVBoxLayout()
        right.addWidget(QLabel("导出列（自上而下的顺序，可上下移）"))
        self.sel_list = QListWidget()
        self.sel_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.sel_list.itemDoubleClicked.connect(lambda _: self._remove_selected())
        right.addWidget(self.sel_list, 1)

        # 上下移按钮
        mv = QHBoxLayout()
        self.up_btn = QPushButton("上移")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        mv.addWidget(self.up_btn)
        self.down_btn = QPushButton("下移")
        self.down_btn.clicked.connect(lambda: self._move(1))
        mv.addWidget(self.down_btn)
        right.addLayout(mv)
        cols.addLayout(right, 1)

        root.addLayout(cols, 1)

        # 合计行开关
        self.total_chk = QCheckBox("末尾加「合计」行（对数值列求和，比率列如偏差率不求和）")
        root.addWidget(self.total_chk)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#ddd;")
        root.addWidget(line)

        # 底部按钮
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("恢复默认顺序")
        reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch(1)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("保存模板")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------ 载入
    def _load(self):
        cand = et.presentable_columns(self.df)
        tpl = et.load_template()
        saved_order = [c for c in tpl["order"] if c in cand]  # 过滤掉 df 已没有的
        # 已选 = 模板里还存在的；候选 = 剩下的
        selected = saved_order
        candidates = [c for c in cand if c not in selected]
        for c in candidates:
            self.cand_list.addItem(QListWidgetItem(c))
        for c in selected:
            self.sel_list.addItem(QListWidgetItem(c))
        self.total_chk.setChecked(tpl["include_total"])

    # ------------------------------------------------------------------ 操作
    def _add_selected(self):
        for it in self.cand_list.selectedItems():
            self.sel_list.addItem(QListWidgetItem(it.text()))
        for it in self.cand_list.selectedItems():
            self.cand_list.takeItem(self.cand_list.row(it))

    def _remove_selected(self):
        for it in self.sel_list.selectedItems():
            self.cand_list.addItem(QListWidgetItem(it.text()))
        for it in self.sel_list.selectedItems():
            self.sel_list.takeItem(self.sel_list.row(it))

    def _move(self, delta):
        row = self.sel_list.currentRow()
        if row < 0:
            return
        new = row + delta
        if new < 0 or new >= self.sel_list.count():
            return
        it = self.sel_list.takeItem(row)
        self.sel_list.insertItem(new, it)
        self.sel_list.setCurrentRow(new)

    def _selected_order(self):
        return [self.sel_list.item(i).text() for i in range(self.sel_list.count())]

    def _on_reset(self):
        """恢复默认 = 清空模板（order 空 → 导出用 df 原顺序），并按 df 原顺序重灌两栏。"""
        cand = et.presentable_columns(self.df)
        self.cand_list.clear()
        self.sel_list.clear()
        for c in cand:
            self.sel_list.addItem(QListWidgetItem(c))  # 全选、原顺序
        self.total_chk.setChecked(False)

    def _on_save(self):
        order = self._selected_order()
        include_total = self.total_chk.isChecked()
        if not order:
            QMessageBox.warning(self, "无法保存", "至少要选一列才能导出。")
            return
        try:
            et.save_template(order, include_total)
        except OSError as e:
            QMessageBox.critical(self, "保存失败", f"写入模板配置失败：{e}")
            return
        QMessageBox.information(
            self, "已保存",
            f"导出模板已保存：{len(order)} 列，合计行{'开' if include_total else '关'}。\n"
            "下次「导出当前表格」即按此模板走。")
        self.accept()


def open_export_template_dialog(owner=None, df=None):
    """便捷入口：弹出导出列模板编辑器。"""
    dlg = ExportTemplateDialog(owner, df)
    dlg.exec()
    return dlg