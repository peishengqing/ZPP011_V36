#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完全重写 main_window.py 中的 _setup_conections 方法"""

import os

file_path = r'E:\zpp011_dev\模块化脚本\gui_pyside6\main_window.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到 _setup_conections 方法的开始和结束
import re

# 匹配整个 _setup_conections 方法
pattern = r'    def _setup_conections\(self\):.*?(?=\n    def |\nclass )'

new_method = '''    def _setup_conections(self):
        self.start_btn.clicked.connect(self._start_analysis)
        self.cancel_btn.clicked.connect(self._cancel_analysis)
        self.open_dir_btn.clicked.connect(self._open_output_dir)
        # 连接导出相关按钮到 ExportController
        self.pt_btn.clicked.connect(lambda: self.export_controller.generate_simple_ppt(
            self.audit_data, self.analysis_output_path, self.output_dir_edit.text().strip(), self, self.log
        ))
        self.excel_btn.clicked.connect(lambda: self.export_controller.export_current_table(self.audit_data, self))
        self.export_full_btn.clicked.connect(lambda: self.export_controller.export_full_excel(
            self.audit_data, self.current_input_file, self._analysis_params, self
        ))
        # 连接双击信号（已读/未读切换）
        self.table_view.doubleClicked.connect(self._on_cell_double_clicked)
'''

# 使用正则表达式替换整个方法
new_content = re.sub(pattern, new_method, content, flags=re.DOTALL)

if new_content != content:
    # 创建备份
    backup_path = file_path + '.backup2'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 写入新内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f'✅ 成功重写 _setup_conections 方法！')
    print(f'   备份文件: {backup_path}')
else:
    print('❌ 未找到 _setup_conections 方法')
    print('   请检查文件内容')
