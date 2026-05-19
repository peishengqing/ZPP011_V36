# -*- coding: utf-8 -*-
"""修复 ui_builder.py: 添加pandas导入，调整audit_data初始化位置"""
import os

fp = r'E:\zpp011_dev\模块化脚本\gui\ui_builder.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复1: 添加 pandas 导入
old_import = '''import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
from widgets import C, STEPS, card, btn, label, entry
from domain.alt_material import alt_manager
import os
import json
import sys'''

new_import = '''import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
from widgets import C, STEPS, card, btn, label, entry
from domain.alt_material import alt_manager
import os
import json
import sys
import pandas as pd'''

if old_import in content:
    content = content.replace(old_import, new_import)
    print('OK: Added pandas import')
else:
    print('SKIP: Import pattern not found')

# 修复2: 移动 audit_data 初始化到 status_lbl 之后
old_init = '''        self.audit_tree.bind("<<TreeviewSelect>>", self._show_audit_card)
        self.audit_data = pd.DataFrame()'''

new_init = '''        self.audit_tree.bind("<<TreeviewSelect>>", self._show_audit_card)
        # audit_data 在 build_ui 完成后初始化（确保 status_lbl 已存在）'''

if old_init in content:
    content = content.replace(old_init, new_init)
    print('OK: Moved audit_data init comment')
else:
    print('SKIP: Init pattern not found')

# 修复3: 在 build_ui 最后添加 audit_data 初始化
old_end = '''        # 初始化替代料配对列表
        self.alt_pairs = []
        self._refresh_alt_view(self._alt_inner)'''

new_end = '''        # 初始化替代料配对列表
        self.alt_pairs = []
        self._refresh_alt_view(self._alt_inner)

        # 初始化 audit_data（确保所有UI组件已创建）
        self.audit_data = pd.DataFrame()'''

if old_end in content:
    content = content.replace(old_end, new_end)
    print('OK: Added audit_data init at end of build_ui')
else:
    print('SKIP: End pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
