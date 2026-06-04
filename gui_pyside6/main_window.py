# -*- coding: utf-8 -*-
"""
ZPP011 主窗口 (PySide6 迁移版 v42.0)
包含：菜单栏、工具栏、表格、筛选行、右键菜单、AI审核、分析功能
裴哥 | 2026-06-04
"""
import sys
import pandas as pd

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QVBoxLayout, QWidget,
    QStatusBar, QMenuBar, QToolBar, QProgressBar, QMessageBox,
    QFileDialog, QLineEdit, QHBoxLayout, QMenu, QAbstractItemView
)

from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
from gui_pyside6.models.workers import AnalysisWorker, AIAuditWorker
from gui_pyside6.dialogs.rule_config_dialog import RuleConfigDialog
from gui_pyside6.dialogs.dashboard_dialog import DashboardDialog
from gui_pyside6.dialogs.import_wizard_dialog import ImportWizard
from core.rule_engine import RuleEngine
from core.ai_client import AIClient


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZPP011 生产偏差分析器 (PySide6 迁移版 v42.0)")
        self.resize(1200, 800)

        # 状态变量
        self.audit_data: pd.DataFrame = None
        self.source_model = None
        self.proxy_model = None
        self.current_input_file = None
        self.alt_pairs = []           # 替代料配对（可从配置加载）
        self.analysis_worker = None
        self.ai_worker = None

        # 核心组件
        self.rule_engine = RuleEngine()
        self.ai_client = AIClient()

        # UI 搭建
        self._setup_menu_bar()
        self._setup_tool_bar()
        self._setup_status_bar()
        self._setup_central_widget()

        # 进度条（默认隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)

        # 加载示例数据
        self._load_sample_data()

    # ---------- UI 搭建 ----------
    def _setup_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        open_action = QAction("打开 Excel 文件", self)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        analysis_menu = menubar.addMenu("分析")
        start_action = QAction("开始分析", self)
        start_action.triggered.connect(self._start_analysis)
        analysis_menu.addAction(start_action)

        audit_menu = menubar.addMenu("审核")
        ai_audit_action = QAction("AI 审核备注", self)
        ai_audit_action.triggered.connect(self._run_ai_audit)
        audit_menu.addAction(ai_audit_action)

        history_menu = menubar.addMenu("历史")
        compare_action = QAction("历史对比", self)
        compare_action.triggered.connect(self._show_history_compare)
        history_menu.addAction(compare_action)

        tools_menu = menubar.addMenu("工具")
        rule_config_action = QAction("规则配置", self)
        rule_config_action.triggered.connect(self._open_rule_config)
        tools_menu.addAction(rule_config_action)
        dashboard_action = QAction("管理看板", self)
        dashboard_action.triggered.connect(self._open_dashboard)
        tools_menu.addAction(dashboard_action)
        import_action = QAction("模板导入向导", self)
        import_action.triggered.connect(self._open_import_wizard)
        tools_menu.addAction(import_action)

        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_tool_bar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        start_btn = QAction("开始分析", self)
        start_btn.triggered.connect(self._start_analysis)
        toolbar.addAction(start_btn)
        ai_btn = QAction("AI 审核备注", self)
        ai_btn.triggered.connect(self._run_ai_audit)
        toolbar.addAction(ai_btn)

    def _setup_status_bar(self):
        self.statusBar().showMessage("就绪")

    def _setup_central_widget(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        # 筛选行
        self.filter_layout = QHBoxLayout()
        self.filter_widgets = []
        layout.addLayout(self.filter_layout)
        # 表格
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(True)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        # 多选支持
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.table_view)
        self.setCentralWidget(central)

    # ---------- 右键菜单 ----------
    def _show_context_menu(self, pos: QPoint):
        # 获取所有选中行
        selection = self.table_view.selectionModel().selectedRows()
        source_indices = []
        for idx in selection:
            source_idx = self.proxy_model.mapToSource(idx)
            source_indices.append(source_idx.row())
        source_indices = list(set(source_indices))

        if not source_indices:
            # 没有选中行，取右键所在行
            index = self.table_view.indexAt(pos)
            if not index.isValid():
                return
            source_idx = self.proxy_model.mapToSource(index)
            source_indices = [source_idx.row()]

        row_data = self.source_model.getDataFrame().iloc[source_indices[0]]

        menu = QMenu()
        copy_action = menu.addAction("复制物料编码")
        copy_action.triggered.connect(lambda: self._copy_material_code(row_data))
        menu.addSeparator()
        batch_status = menu.addAction("批量改状态")
        batch_status.triggered.connect(lambda: self._batch_change_status(source_indices))
        batch_remark = menu.addAction("批量填备注")
        batch_remark.triggered.connect(lambda: self._batch_remark(source_indices))
        batch_export = menu.addAction("批量导出")
        batch_export.triggered.connect(lambda: self._batch_export(source_indices))
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _copy_material_code(self, row_data):
        code = row_data.get('物料编码', '')
        if code:
            QApplication.clipboard().setText(str(code))
            self.statusBar().showMessage(f"已复制物料编码: {code}", 2000)

    def _batch_change_status(self, rows):
        from gui_pyside6.dialogs.batch_operations_dialog import BatchChangeStatusDialog
        def on_finished(updated_df):
            self._set_audit_data(updated_df)
        dialog = BatchChangeStatusDialog(self, rows, self.audit_data, on_finished)
        dialog.exec()

    def _batch_remark(self, rows):
        from gui_pyside6.dialogs.batch_operations_dialog import BatchRemarkDialog
        def on_finished(updated_df):
            self._set_audit_data(updated_df)
        dialog = BatchRemarkDialog(self, rows, self.audit_data, on_finished)
        dialog.exec()

    def _batch_export(self, rows):
        from gui_pyside6.dialogs.batch_operations_dialog import BatchExportDialog
        df_subset = self.audit_data.iloc[rows].copy()
        dialog = BatchExportDialog(self, df_subset)
        dialog.exec()

    # ---------- 数据 ----------
    def _load_sample_data(self):
        sample = pd.DataFrame({
            "订单日期": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "物料编码": ["M001", "M002", "M003"],
            "物料名称": ["白糖", "面粉", "食用油"],
            "偏差率(%)": [3.2, 8.5, 15.0],
            "审核结果": ["合格", "需关注", "需补备注"],
            "备注": ["", "", "用量异常"],
            "替代料": ["", "", "是"]
        })
        self._set_audit_data(sample)

    def _set_audit_data(self, df: pd.DataFrame):
        self.audit_data = df
        self.source_model = DataFrameModel(df)
        self.proxy_model = AuditProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.table_view.setModel(self.proxy_model)

        # 动态创建筛选输入框
        for w in self.filter_widgets:
            w.deleteLater()
        self.filter_widgets.clear()
        for i, col in enumerate(df.columns):
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"筛选 {col}")
            line_edit.textChanged.connect(lambda text, idx=i: self.proxy_model.setFilter(idx, text))
            self.filter_layout.addWidget(line_edit)
            self.filter_widgets.append(line_edit)
        self.filter_layout.addStretch()

        self.table_view.resizeColumnsToContents()
        self.source_model.dataChanged.connect(self._on_data_changed)
        self.statusBar().showMessage(f"已加载 {len(df)} 条记录")

    def _on_data_changed(self, top_left, bottom_right):
        self.statusBar().showMessage("数据已修改", 1500)
        # TODO: 保存到数据库

    def _open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 SAP Excel 文件", "", "Excel files (*.xlsx *.xls)"
        )
        if file_path:
            self.current_input_file = file_path
            try:
                df = pd.read_excel(file_path, sheet_name="Data")
                if '偏差率(%)' in df.columns:
                    df['偏差率(%)'] = pd.to_numeric(df['偏差率(%)'], errors='coerce')
                    df = df[df['偏差率(%)'].abs() > 10]
                self._set_audit_data(df)
                QMessageBox.information(self, "成功", f"已加载 {len(df)} 条记录")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件失败: {e}")

    # ---------- 分析 ----------
    def _get_input_file(self):
        if not self.current_input_file:
            QMessageBox.warning(self, "提示", "请先通过「文件」->「打开 Excel 文件」选择输入文件")
            return None
        return self.current_input_file

    def _start_analysis(self):
        input_file = self._get_input_file()
        if not input_file:
            return
        if self.analysis_worker and self.analysis_worker.isRunning():
            QMessageBox.information(self, "提示", "分析任务已在后台运行，请稍后")
            return

        # TODO: 可从 UI 获取日期范围和物料搜索条件，此处先留空
        start_date = ''
        end_date = ''
        material_search = ''

        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("分析中...")

        self.analysis_worker = AnalysisWorker(
            input_file, self.alt_pairs, start_date, end_date, material_search
        )
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)
        self.analysis_worker.start()

    def _on_analysis_progress(self, percent, step_name):
        self.progress_bar.setValue(percent)
        self.statusBar().showMessage(f"分析中: {step_name} ({percent}%)")

    def _on_analysis_finished(self, output_path):
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("分析完成，正在加载结果...")
        try:
            df = pd.read_excel(output_path, sheet_name='完整偏差明细')
            if '偏差率(%)' in df.columns:
                df['偏差率(%)'] = pd.to_numeric(df['偏差率(%)'], errors='coerce')
                df = df[df['偏差率(%)'].abs() > 10]
            self._set_audit_data(df)
            self.statusBar().showMessage("分析完成，数据已加载")
            QMessageBox.information(self, "完成", f"分析完成，共加载 {len(df)} 条记录")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载分析结果失败: {e}")

    def _on_analysis_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("分析失败")
        QMessageBox.critical(self, "错误", error_msg)

    # ---------- AI 审核 ----------
    def _run_ai_audit(self):
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(self, "警告", "无数据，请先加载或分析数据")
            return
        if self.ai_worker and self.ai_worker.isRunning():
            QMessageBox.information(self, "提示", "AI 审核已在后台运行，请稍后")
            return
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("AI 审核中...")
        self.ai_worker = AIAuditWorker(self.audit_data, self.rule_engine, self.ai_client)
        self.ai_worker.progress.connect(self._on_ai_progress)
        self.ai_worker.finished.connect(self._on_ai_finished)
        self.ai_worker.error.connect(self._on_ai_error)
        self.ai_worker.start()

    def _on_ai_progress(self, processed, total):
        percent = int(processed / total * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.statusBar().showMessage(f"AI 审核中: {processed}/{total}")

    def _on_ai_finished(self, updated_df):
        self._set_audit_data(updated_df)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("AI 审核完成")
        QMessageBox.information(self, "完成", "AI 审核已完成，表格已更新")

    def _on_ai_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("AI 审核失败")
        QMessageBox.critical(self, "错误", f"AI 审核失败: {error_msg}")

    # ---------- 规则配置 ----------
    def _open_rule_config(self):
        """打开可视化规则配置对话框"""
        from pathlib import Path
        rules_path = Path(__file__).parent.parent / "config" / "system" / "rules.json"
        def on_rules_changed():
            # 重新加载规则引擎并刷新表格
            self.rule_engine.load_rules()
            if self.audit_data is not None:
                # 重新设置数据触发整行颜色重算
                self._set_audit_data(self.audit_data)
        dialog = RuleConfigDialog(self, str(rules_path), on_rules_changed)
        dialog.exec()

    def _show_about(self):
        QMessageBox.about(self, "关于 ZPP011",
                          "ZPP011 生产偏差分析器\n版本 v42.0 (PySide6 迁移版)\n\n"
                          "基于 PySide6 重写\n功能：分析、AI审核、表格筛选、编辑等")

    def get_current_audit_data(self):
        """供 DashboardDialog 获取当前审核数据"""
        return self.audit_data

    def _open_dashboard(self):
        """打开管理看板对话框"""
        if self.audit_data is None or self.audit_data.empty:
            QMessageBox.warning(self, "提示", "请先加载审核数据")
            return
        material_df = getattr(self, 'material_df', None)
        dialog = DashboardDialog(self.audit_data, material_df, self)
        dialog.drill_down_signal.connect(self._on_drill_down)
        dialog.exec()

    def _on_drill_down(self, dim_type, dim_value):
        """看板下钻：按维度筛选表格"""
        if self.audit_data is None:
            return
        # dim_type 直接是中文列名（"车间" / "物料大类"）
        if dim_type in self.audit_data.columns:
            self.audit_data = self.audit_data[self.audit_data[dim_type] == dim_value]
            self._set_audit_data(self.audit_data)
            self.statusBar().showMessage(f"下钻筛选: {dim_type}={dim_value}")
        else:
            self.statusBar().showMessage(f"未找到列: {dim_type}", 3000)

    def _show_history_compare(self):
        """打开历史对比对话框"""
        from gui_pyside6.dialogs.history_compare_dialog import HistoryCompareDialog
        dialog = HistoryCompareDialog(self, None)
        dialog.exec()

    # ---------- 模板导入向导 ----------
    def _open_import_wizard(self):
        """打开模板导入向导"""
        from pathlib import Path
        rules_path = Path(__file__).parent.parent / "config" / "system" / "rules.json"

        def on_alt_changed():
            pass  # 替代料变更后刷新（暂不需要额外操作）

        def on_rules_changed():
            self.rule_engine.load_rules()
            if self.audit_data is not None:
                self._set_audit_data(self.audit_data)

        dialog = ImportWizard(
            self,
            alt_pairs=self.alt_pairs,
            rules_path=str(rules_path),
            on_alt_changed=on_alt_changed,
            on_rules_changed=on_rules_changed
        )
        dialog.exec()

    # ---------- 关闭事件 ----------
    def closeEvent(self, event):
        if (self.analysis_worker and self.analysis_worker.isRunning()) or \
           (self.ai_worker and self.ai_worker.isRunning()):
            reply = QMessageBox.question(self, "确认退出",
                                         "后台任务正在运行，退出将取消任务。确定要退出吗？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                if self.analysis_worker:
                    self.analysis_worker.cancel()
                if self.ai_worker:
                    self.ai_worker.cancel()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
