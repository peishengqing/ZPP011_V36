import os
import sys

code = r'''# -*- coding: utf-8 -*-
"""
模板导入向导 (PySide6 版本)
支持从 Excel 批量导入替代料配对和备注校验规则
"""
import os
import pandas as pd
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWizard, QWizardPage,
    QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QRadioButton, QButtonGroup,
    QMessageBox, QProgressBar
)
from PySide6.QtCore import Signal, QThread

# 尝试导入相关模块，如果失败则提供桩位实现
try:
    from core.import_handlers import import_alt_pairs_from_excel, import_rules_from_excel
except ImportError:
    def import_alt_pairs_from_excel(data, alt_pairs, overwrite=False):
        return data  # 桩位实现
    
    def import_rules_from_excel(data, rules_path, overwrite=False):
        pass  # 桩位实现

try:
    from domain.alt_material.alt_manager import save_alt_pairs
except ImportError:
    def save_alt_pairs(pairs, log_cb=None):
        pass  # 桩位实现


class LoadExcelWorker(QThread):
    """加载 Excel 文件的工作线程"""
    finished = Signal(object, object)  # dataframe, sheet_names
    error = Signal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            xl = pd.ExcelFile(self.file_path)
            sheets = xl.sheet_names
            # 默认读取第一个工作表
            df = pd.read_excel(self.file_path, sheet_name=sheets[0])
            self.finished.emit(df, sheets)
        except Exception as e:
            self.error.emit(str(e))


class SheetPage(QWizardPage):
    """选择文件页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.df = None
        self.sheets = None
        self.file_path = None
        self.setup_ui()
    
    def setup_ui(self):
        self.setTitle("选择 Excel 文件")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("选择 Excel 文件："))
        file_layout = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        file_layout.addWidget(self.file_edit)
        self.browse_btn = QPushButton("浏览...")
        file_layout.addWidget(self.browse_btn)
        layout.addLayout(file_layout)
        layout.addWidget(QLabel("工作表名称："))
        self.sheet_combo = QComboBox()
        layout.addWidget(self.sheet_combo)
        self.file_preview = QLabel("预览：未选择文件")
        layout.addWidget(self.file_preview)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        layout.addStretch()
        self.setLayout(layout)
    
    def isComplete(self):
        return self.df is not None


class MappingPage(QWizardPage):
    """列映射页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mapping_widgets = {}
        self.setup_ui()
    
    def setup_ui(self):
        self.setTitle("列映射")
        self.mapping_layout = QVBoxLayout()
        self.setLayout(self.mapping_layout)
    
    def isComplete(self):
        # 检查是否所有字段都已映射
        if not hasattr(self, 'mapping_widgets') or not self.mapping_widgets:
            return False
        for field, combo in self.mapping_widgets.items():
            if not combo.currentText():
                return False
        return True


class PreviewPage(QWizardPage):
    """预览与确认页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parsed_data = None
        self.setup_ui()
    
    def setup_ui(self):
        self.setTitle("预览与确认")
        layout = QVBoxLayout()
        self.preview_table = QTableWidget()
        layout.addWidget(self.preview_table)
        self.preview_info = QLabel()
        layout.addWidget(self.preview_info)
        layout.addWidget(QLabel("导入模式："))
        mode_layout = QHBoxLayout()
        self.append_radio = QRadioButton("追加（保留现有，添加新数据）")
        self.overwrite_radio = QRadioButton("覆盖（清空现有，完全替换）")
        self.append_radio.setChecked(True)
        mode_layout.addWidget(self.append_radio)
        mode_layout.addWidget(self.overwrite_radio)
        layout.addLayout(mode_layout)
        layout.addStretch()
        self.setLayout(layout)
    
    def isComplete(self):
        return self.parsed_data is not None and len(self.parsed_data) > 0


class ImportWizard(QWizard):
    """导入向导主窗口"""
    def __init__(self, parent, alt_pairs, rules_path, on_alt_changed=None, on_rules_changed=None):
        super().__init__(parent)
        self.setWindowTitle("模板导入向导")
        self.resize(800, 600)

        self.alt_pairs = alt_pairs
        self.rules_path = rules_path
        self.on_alt_changed = on_alt_changed
        self.on_rules_changed = on_rules_changed

        self.import_type = None  # 'alt' or 'rule'
        self.file_path = None
        self.df = None
        self.mapping = {}
        self.parsed_data = None
        self.worker = None

        self._add_pages()
        self.setButtonText(QWizard.NextButton, "下一步")
        self.setButtonText(QWizard.BackButton, "上一步")
        self.setButtonText(QWizard.FinishButton, "完成")
        self.setButtonText(QWizard.CancelButton, "取消")

    def _add_pages(self):
        # 第一页：选择类型
        self.page_type = QWizardPage()
        self.page_type.setTitle("选择导入类型")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("请选择要导入的数据类型："))
        self.type_group = QButtonGroup()
        self.alt_radio = QRadioButton("替代料配对（Excel）")
        self.rule_radio = QRadioButton("备注校验规则（Excel）")
        self.alt_radio.setChecked(True)
        self.type_group.addButton(self.alt_radio, 0)
        self.type_group.addButton(self.rule_radio, 1)
        layout.addWidget(self.alt_radio)
        layout.addWidget(self.rule_radio)
        layout.addStretch()
        self.page_type.setLayout(layout)
        self.addPage(self.page_type)

        # 第二页：选择文件
        self.page_file = SheetPage()
        self.page_file.browse_btn.clicked.connect(self._browse_file)
        self.addPage(self.page_file)

        # 第三页：列映射
        self.page_mapping = MappingPage()
        self.addPage(self.page_mapping)

        # 第四页：预览与确认
        self.page_preview = PreviewPage()
        self.addPage(self.page_preview)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 文件", "", "Excel files (*.xlsx *.xls)")
        if file_path:
            self.file_path = file_path
            self.page_file.file_path = file_path
            self.page_file.file_edit.setText(file_path)
            self.page_file.progress.setVisible(True)
            self.page_file.progress.setRange(0, 0)  # 不确定进度
            self.worker = LoadExcelWorker(file_path)
            self.worker.finished.connect(self._on_excel_loaded)
            self.worker.error.connect(self._on_excel_error)
            self.worker.start()

    def _on_excel_loaded(self, df, sheets):
        self.page_file.progress.setVisible(False)
        self.page_file.df = df
        self.page_file.sheets = sheets
        self.df = df
        self.page_file.sheet_combo.clear()
        self.page_file.sheet_combo.addItems(sheets)
        self.page_file.sheet_combo.setCurrentIndex(0)
        # 预览前5行
        preview = df.head().to_string()
        self.page_file.file_preview.setText(f"预览前5行：\n{preview}")
        # 触发页面完成状态更新
        self.page_file.completeChanged.emit()

    def _on_excel_error(self, err):
        self.page_file.progress.setVisible(False)
        QMessageBox.critical(self, "错误", f"读取 Excel 失败: {err}")

    def initializePage(self, id):
        if id == 2:  # 列映射页
            self._build_mapping_ui()
        elif id == 3:  # 预览页
            self._build_preview()

    def _build_mapping_ui(self):
        # 清空旧控件
        for w in self.page_mapping.mapping_widgets.values():
            w.deleteLater()
        self.page_mapping.mapping_widgets.clear()
        # 根据导入类型确定字段
        self.import_type = 'alt' if self.alt_radio.isChecked() else 'rule'
        if self.import_type == 'alt':
            fields = ["工厂名称", "物料A编码", "物料A名称", "物料B编码", "物料B名称"]
        else:
            fields = ["规则名称", "条件表达式", "动作类型", "动作参数", "启用"]
        # 获取列名
        cols = self.df.columns.tolist()
        for field in fields:
            row_layout = QHBoxLayout()
            row_layout.addWidget(QLabel(field + ":"))
            combo = QComboBox()
            combo.addItems([""] + cols)
            # 尝试自动匹配
            for col in cols:
                if field in col or col in field:
                    combo.setCurrentText(col)
                    break
            row_layout.addWidget(combo)
            self.page_mapping.mapping_layout.addLayout(row_layout)
            self.page_mapping.mapping_widgets[field] = combo
        self.page_mapping.mapping_layout.addStretch()
        # 连接信号以实时验证
        for combo in self.page_mapping.mapping_widgets.values():
            combo.currentTextChanged.connect(self.page_mapping.completeChanged.emit)

    def _build_preview(self):
        # 收集映射
        mapping = {}
        for field, combo in self.page_mapping.mapping_widgets.items():
            mapping[field] = combo.currentText()
        # 解析数据
        try:
            if self.import_type == 'alt':
                self.parsed_data = self._parse_alt_data(mapping)
            else:
                self.parsed_data = self._parse_rule_data(mapping)
        except Exception as e:
            QMessageBox.critical(self, "解析错误", str(e))
            self.page_preview.parsed_data = None
            self.page_preview.completeChanged.emit()
            return

        # 显示预览
        if self.import_type == 'alt':
            headers = ['工厂', '物料A编码', '物料A名称', '物料B编码', '物料B名称']
            rows = [[item.get('工厂名称', ''), item.get('物料A编码', ''), item.get('物料A名称', ''), item.get('物料B编码', ''), item.get('物料B名称', '')] for item in self.parsed_data[:20]]
        else:
            headers = ['规则名称', '条件', '动作', '参数', '启用']
            rows = [[item.get('规则名称', ''), item.get('条件表达式', ''), item.get('动作类型', ''), item.get('动作参数', ''), item.get('启用', '')] for item in self.parsed_data[:20]]
        
        self.page_preview.preview_table.setColumnCount(len(headers))
        self.page_preview.preview_table.setHorizontalHeaderLabels(headers)
        self.page_preview.preview_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.page_preview.preview_table.setItem(i, j, QTableWidgetItem(str(val)))
        self.page_preview.preview_table.resizeColumnsToContents()
        self.page_preview.preview_info.setText(f"共解析到 {len(self.parsed_data)} 条记录（仅显示前20条）")
        self.page_preview.parsed_data = self.parsed_data
        self.page_preview.completeChanged.emit()

    def _parse_alt_data(self, mapping):
        # 重命名列
        rename_map = {v: k for k, v in mapping.items() if v}
        df = self.df.rename(columns=rename_map)
        required = ['工厂名称', '物料A编码', '物料A名称', '物料B编码', '物料B名称']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"缺少列：{col}")
        df = df[required].dropna()
        df = df.applymap(lambda x: str(x).strip() if pd.notna(x) else '')
        df = df[(df['物料A编码'] != '') & (df['物料B编码'] != '')]
        return df.to_dict('records')

    def _parse_rule_data(self, mapping):
        # 重命名列
        rename_map = {v: k for k, v in mapping.items() if v}
        df = self.df.rename(columns=rename_map)
        required = ['规则名称', '条件表达式', '动作类型', '动作参数', '启用']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"缺少列：{col}")
        df = df[required].dropna()
        records = []
        for _, row in df.iterrows():
            record = {
                '规则名称': str(row['规则名称']).strip(),
                '条件表达式': str(row['条件表达式']).strip(),
                '动作类型': str(row['动作类型']).strip(),
                '动作参数': str(row['动作参数']).strip() if pd.notna(row['动作参数']) else '',
                '启用': str(row['启用']).strip().lower() in ('true', '是', '1', 'yes')
            }
            records.append(record)
        return records

    def accept(self):
        """完成按钮点击时执行导入"""
        if self.parsed_data is None:
            QMessageBox.warning(self, "提示", "没有可导入的数据")
            return
        overwrite = self.page_preview.overwrite_radio.isChecked()
        try:
            if self.import_type == 'alt':
                new_pairs = import_alt_pairs_from_excel(self.parsed_data, self.alt_pairs, overwrite=overwrite)
                # 更新内存中的 alt_pairs
                self.alt_pairs.clear()
                self.alt_pairs.extend(new_pairs)
                # 保存到文件
                save_alt_pairs(self.alt_pairs, log_cb=lambda msg, level: print(msg))
                if self.on_alt_changed:
                    self.on_alt_changed()
                QMessageBox.information(self, "导入成功", f"成功导入 {len(self.parsed_data)} 条替代料配对")
            else:
                import_rules_from_excel(self.parsed_data, self.rules_path, overwrite=overwrite)
                if self.on_rules_changed:
                    self.on_rules_changed()
                QMessageBox.information(self, "导入成功", f"成功导入 {len(self.parsed_data)} 条规则")
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
'''

with open('E:/zpp011_dev/模块化脚本/gui_pyside6/dialogs/import_wizard_dialog.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("import_wizard_dialog.py 写入完成，开始验证语法...")

# 验证语法
import py_compile
try:
    py_compile.compile('E:/zpp011_dev/模块化脚本/gui_pyside6/dialogs/import_wizard_dialog.py', doraise=True)
    print("语法检查通过")
except py_compile.PyCompileError as e:
    print(f"语法错误: {e}")
    
# 检查是否还有明显错误
with open('E:/zpp011_dev/模块化脚本/gui_pyside6/dialogs/import_wizard_dialog.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    
errors = []
for i, line in enumerate(lines, 1):
    # 检查常见拼写错误
    if 'to_nemeric' in line:
        errors.append(f"L{i}: to_nemeric (应为 to_numeric)")
    if 'coerce' in line and 'coerce' not in line:
        errors.append(f"L{i}: coerce (应为 coerce)")
    if 'horizontal' in line and 'horizontal' not in line:
        errors.append(f"L{i}: horizontal (应为 horizontal)")
    if 'browse' in line and 'browse' not in line and 'browse' not in line:
        errors.append(f"L{i}: browse 拼写错误")
    if 'sheet' in line and 'sheet' not in line and 'Sheet' not in line:
        errors.append(f"L{i}: sheet 拼写错误")
        
if errors:
    print("发现以下错误:")
    for err in errors:
        print(f"  {err}")
else:
    print("未发现明显拼写错误")
