#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
添加 _show_about 方法到 gui/app.py
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

root = r'E:\zpp011_dev\模块化脚本'
app_path = os.path.join(root, 'gui/app.py')

with open(app_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到插入位置（在 _show_shortcuts_help 方法后面）
insert_marker = '''    def _show_shortcuts_help(self):
        """显示快捷键帮助"""'''

if insert_marker in content:
    # 找到插入位置
    insert_idx = content.find(insert_marker)
    
    # 新方法
    new_method = '''    def _show_about(self):
        """显示关于对话框"""
        import tkinter.messagebox as messagebox
        from utils.version_history import APP_NAME
        
        # 获取当前版本
        try:
            from utils.version_history import get_current_version
            version = get_current_version()
        except:
            version = 'v39.4'
        
        info = f"""{APP_NAME}
版本：{version}

制作人：裴盛清
架构师：元宝

© 2026 云南达利食品有限公司

本软件受版权保护，未经许可不得复制或分发。"""
        
        messagebox.showinfo('关于本软件', info)

    '''
    
    # 插入新方法
    content = content[:insert_idx] + new_method + content[insert_idx:]
    
    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✓ 已添加 _show_about 方法')
    print(f'  插入位置：Line {content[:insert_idx].count(chr(10)) + 1}')
else:
    print('✗ 未找到插入位置')
