# -*- coding: utf-8 -*-
"""交互控制层（ARC-003 第六刀，v43.199）。

定位 / 选中 / 复制 相关职责从 MainWindow 切出，避免 God Object 持续膨胀。

模式：组合式。本控制器持有 MainWindow 引用（self.mw），方法体从 MainWindow
原样搬迁、逻辑零改动；MainWindow 侧保留同名薄壳转发方法，保证外部既有调用
（看板 dialog 的 self.main_window._locate_row_in_main_table() 等）签名不变。

import 来源说明：原方法体依赖 main_window.py 顶部的 logging / numpy / Qt /
QApplication / QGroupBox，本模块自行 import 同名对象，行为完全一致。
"""
import logging
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QGroupBox, QMessageBox

from gui_pyside6.widgets.toast import toast
from gui_pyside6.utils.icons import make_button


class InteractionController:
    """整合了 MainWindow 中多个交互相关方法。"""

    def __init__(self, mw: Any):
        self.mw = mw

    # ─────────── 定位相关 ───────────

    def _select_source_row(self, src_row: int):
        """选中主表某一行（源行位置 → 代理行映射），供各定位方法复用。"""
        src_idx = self.mw.source_model.index(src_row, 0)
        proxy = self.mw.table_view.model()
        proxy_idx = proxy.mapFromSource(src_idx) if hasattr(proxy, 'mapFromSource') else src_idx
        self.mw.table_view.selectRow(proxy_idx.row())
        self.mw.table_view.scrollTo(proxy_idx)
        self.mw.table_view.setFocus()
        self.mw.activateWindow()
        self.mw.raise_()
        return True

    def _locate_row_by_index(self, row_index: int):
        """按 DataFrame index 标签定位主表行（兼容旧调用方）"""
        try:
            if self.mw.source_model is None:
                return False
            df = self.mw.source_model.getDataFrame()
            if df is None or row_index not in df.index:
                return False
            return self._select_source_row(df.index.get_loc(row_index))
        except Exception as e:
            self.mw.log(f"定位主表失败: {e}", "error")
            return False

    def _locate_row_by_excel_no(self, excel_row: int):
        """按「原表行号」列的取值定位主表行。

        与 _locate_row_by_index 的区别：后者按 DataFrame 索引标签匹配，而主表索引是
        RangeIndex，拿 Excel 行号去匹配会失配或错位（行号 5 → 第 6 行）；这里按列值
        精确匹配，是看板双击定位最可靠的一条路径。
        """
        try:
            if self.mw.source_model is None:
                return False
            df = self.mw.source_model.getDataFrame()
            if df is None or df.empty or '原表行号' not in df.columns:
                return False
            key = str(excel_row).strip()
            if not key:
                return False
            hits = df.index[df['原表行号'].astype(str).str.strip() == key].tolist()
            if not hits:
                return False
            return self._select_source_row(df.index.get_loc(hits[0]))
        except Exception as e:
            self.mw.log(f"定位主表失败: {e}", "error")
            return False

    def _locate_row_in_main_table(self, data_id: str, silent: bool = False):
        """变动提醒弹窗双击某行时，定位并选中主表对应行（经 proxy_model 映射）"""
        try:
            if self.mw.source_model is None:
                return False
            df = self.mw.source_model.getDataFrame()
            if df is None or 'data_id' not in df.columns:
                return False
            matches = df.index[df['data_id'].astype(str) == str(data_id)].tolist()
            if not matches:
                if not silent:
                    toast("主表中未找到该记录", parent=self.mw)
                return False
            return self._select_source_row(df.index.get_loc(matches[0]))
        except Exception as e:
            self.mw.log(f"定位主表失败: {e}", "error")
            return False

    # ─────────── 选中相关 ───────────

    def _on_selection_changed(self, selected: Any, deselected: Any):
        """选中变化时，显示选中合计"""
        if self.mw.proxy_model is None or self.mw.view_model.df is None:
            self.mw.statusBar().showMessage("")
            return

        # 如果选中清空，无需恢复底部合计（v43.281：合计标签已整体移除，
        # _update_all_summary 现为空壳，保留调用仅为兼容信号链）
        if not selected:
            self.mw._update_all_summary()
            return

        indexes = self.mw.table_view.selectionModel().selectedIndexes()
        if not indexes:
            self.mw.statusBar().showMessage("")
            return
        df = self.mw.source_model.getDataFrame()
        # 收集选中行中的唯一行号
        selected_rows = set()
        for idx in indexes:
            source_idx = self.mw.proxy_model.mapToSource(idx)
            selected_rows.add(source_idx.row())

        # 按列累加选中行的值
        col_sums = {}
        # 从 df 中找出所有可能的数值列
        numeric_candidates = ["配额", "定额", "数量-定额", "实际", "数量-实际", "偏差金额", "偏差金额(含税)", "偏差数量", "数量偏差", "净偏差数量", "净偏差金额"]

        for row in selected_rows:
            for col_idx, col_name in enumerate(df.columns):
                if col_idx == 0:  # 跳过行号列
                    continue
                if col_name not in numeric_candidates:
                    continue
                val = df.iloc[row, col_idx]
                if pd.notna(val) and isinstance(val, (int, float, np.integer, np.floating)):
                    col_sums[col_name] = col_sums.get(col_name, 0) + val

        if col_sums:
            # 更新选中合计显示
            self.mw._update_selection_summary(col_sums)
        else:
            self.mw.statusBar().showMessage("选中合计：无有效数值", 2000)
            self.mw._clear_selection_summary()

    def _update_selection_summary(self, col_sums: dict):
        """更新选中行合计。

        v43.281：底部合计标签（配额/实际/偏差金额/偏差量）已按用户要求移除，
        这里只保留状态栏「选中合计：…」提示（选中行时的即时反馈，无落点控件）。
        """
        # 收集显示的列名和值
        display_map = {}
        for k, v in col_sums.items():
            # 映射到标准名称
            if k in ("配额", "定额", "数量-定额"):
                display_map["配额"] = v
            elif k in ("实际", "数量-实际"):
                display_map["实际"] = v
            elif k in ("偏差金额", "偏差金额(含税)"):
                display_map["偏差金额"] = v
            elif k in ("偏差数量", "数量偏差"):
                display_map["偏差数量"] = v
            else:
                display_map[k] = v

        if display_map:
            # 状态栏显示详细合计
            parts = []
            for k, v in display_map.items():
                if "%" in k:
                    parts.append(f"{k}: {v:.2f}")
                else:
                    parts.append(f"{k}: {v:,.2f}")
            self.mw.statusBar().showMessage("选中合计：" + " | ".join(parts))

    def _clear_selection_summary(self):
        """清空选中合计提示（v43.281：底部标签已移除，仅清状态栏消息）"""
        self.mw.statusBar().showMessage("", 1)

    # ─────────── 复制相关 ───────────

    def _copy_selected_cells(self):
        """复制选中区域到剪贴板（Excel 式：按选中矩形输出，空洞填空）。

        原先 main_window 有两份实现：菜单连这份、Ctrl+C 连 _copy_selected_cells，
        两者行为不一致；现统一为本实现，两条入口共用。
        """
        tv = self.mw.table_view
        selection = tv.selectionModel()
        indexes = selection.selectedIndexes()
        if not indexes:
            return
        cells = {}
        min_row, max_row = float('inf'), -1
        min_col, max_col = float('inf'), -1
        for idx in indexes:
            r, c = idx.row(), idx.column()
            cells[(r, c)] = idx.data(Qt.DisplayRole) or ""
            min_row = min(min_row, r)
            max_row = max(max_row, r)
            min_col = min(min_col, c)
            max_col = max(max_col, c)
        lines = []
        for r in range(min_row, max_row + 1):
            row_vals = []
            for c in range(min_col, max_col + 1):
                row_vals.append(str(cells.get((r, c), "")))
            lines.append("\t".join(row_vals))
        QApplication.clipboard().setText("\n".join(lines))
        self.mw.statusBar().showMessage(f"已复制 {max_row - min_row + 1} 行 × {max_col - min_col + 1} 列", 2000)

    def _on_cell_double_clicked(self, index: Any):
        import logging
        self.mw.log("InteractionController: _on_cell_double_clicked 被调用", "info")
        try:
            if self.mw.proxy_model and self.mw.source_model:
                source_index = self.mw.proxy_model.mapToSource(index)
                row = source_index.row()
                df = self.mw.source_model.getDataFrame()
                self.mw.log(f"双击: row={row}, len(df)={len(df)}", "info")
                if row < len(df):
                    row_data = df.iloc[row]
                    self.mw.log(f"双击: 找到行数据，调用_show_row_detail", "info")
                    self.mw._show_row_detail(row_data)
                else:
                    self.mw.log(f"双击弹窗失败: row={row} 超出范围 len={len(df)}", "warn")
                    QMessageBox.warning(self.mw, "提示", f"行号 {row} 超出数据范围 (最大 {len(df)-1})")
            else:
                msg = f"双击弹窗失败: 缺少表格模型 (proxy={self.mw.proxy_model}, source={self.mw.source_model})"
                self.mw.log(msg, "error")
                QMessageBox.warning(self.mw, "提示", msg)
        except Exception as e:
            import traceback
            msg = f"双击弹窗失败: {e}"
            self.mw.log(f"{msg}\n{traceback.format_exc()}", "error")
            QMessageBox.critical(self.mw, "错误", f"双击 failed:\n{e}")

    def _show_row_detail(self, row_data):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QDialogButtonBox
        from PySide6.QtCore import Qt

        def _val(*keys):
            for k in keys:
                if k in row_data.index:
                    v = row_data[k]
                    if not (v is None or (pd.isna(v) if not isinstance(v, str) else False)):
                        return v
                for col in row_data.index:
                    if col.strip() == k:
                        v = row_data[col]
                        if not (v is None or (pd.isna(v) if not isinstance(v, str) else False)):
                            return v
            return ""

        # 创建对话框
        dialog = QDialog(self.mw)
        mat_code = _val("物料编码", "物料号")
        mat_name = _val("物料描述", "物料名称", "物料")
        dialog.setWindowTitle(f"明细 - {mat_code} {mat_name}")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)

        def _mk_label(text=""):
            lbl = QLabel(str(text))
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return lbl

        gb1 = QGroupBox("基本信息")
        fl1 = QFormLayout(gb1)
        for label, keys in [("工厂", ["工厂", "工厂名称"]), ("车间", ["车间"]), ("订单日期", ["订单日期"]), ("流程订单", ["流程订单"]), ("物料编码", ["物料编码", "物料号"]), ("物料描述", ["物料描述", "物料名称"]), ("组件物料类型", ["组件物料类型"]), ("组件物料类型描述", ["组件物料类型描述"])]:
            fl1.addRow(f"{label}：", _mk_label(_val(*keys)))
        layout.addWidget(gb1)

        gb2 = QGroupBox("偏差数据")
        fl2 = QFormLayout(gb2)
        for label, keys in [("定额用量", ["定额"]), ("实际用量", ["实际"]), ("偏差数量", ["偏差数量"]), ("偏差率", ["偏差率", "偏差率(%)"]), ("偏差金额", ["偏差金额"]), ("总偏差金额(含税)", ["总偏差金额(含税)", "偏差金额"]), ("审核结果", ["审核结果", "audit_result"]), ("备注来源", ["备注来源"])]:
            val = _val(*keys)
            display = str(val)
            if "偏差率" in label and val:
                try:
                    display = f"{float(val):.2f}%"
                except Exception as e:
                    logging.warning("偏差率格式转换失败: %s", e)
            fl2.addRow(f"{label}：", _mk_label(display))
        layout.addWidget(gb2)

        gb3 = QGroupBox("备注与建议")
        fl3 = QFormLayout(gb3)
        remark_label = _mk_label(_val("备注原因", "备注"))
        remark_label.setWordWrap(True)
        fl3.addRow("备注：", remark_label)
        layout.addWidget(gb3)

        # 按钮区域：复制图片 + OK
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # 复制图片按钮
        copy_img_btn = make_button("📋 复制图片")
        def _copy_dialog_as_image():
            # 捕获对话框的屏幕图像
            try:
                # Qt6 已移除 QPixmap.grabWindow，改用 QWidget.grab() 捕获窗口像素
                pixmap = dialog.grab()
                if pixmap is None or pixmap.isNull():
                    raise RuntimeError("widget.grab() 未生成图像")
                # 复制到剪贴板
                QApplication.clipboard().setPixmap(pixmap)
                # 显示提示
                self.mw.statusBar().showMessage("已复制到剪贴板", 2000)
            except Exception as e:
                self.mw.statusBar().showMessage(f"复制图片失败: {e}", 5000)

        copy_img_btn.clicked.connect(_copy_dialog_as_image)
        btn_layout.addWidget(copy_img_btn)

        # OK 按钮
        btn = QDialogButtonBox(QDialogButtonBox.Ok)
        btn.accepted.connect(dialog.accept)
        btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)
        dialog.exec()
