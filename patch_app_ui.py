#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接修改 gui/app.py，添加管理看板按钮和视图管理工具栏
使用绝对路径，避免工作目录问题
"""

import os
import sys

# 设置正确的工作目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

print(f"工作目录: {os.getcwd()}")
print(f"gui/app.py 存在: {os.path.exists('gui/app.py')}")

def patch_app_py():
    app_py_path = os.path.join(SCRIPT_DIR, 'gui', 'app.py')
    
    if not os.path.exists(app_py_path):
        print(f"错误: 找不到 {app_py_path}")
        return False
    
    with open(app_py_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    content = ''.join(lines)
    modified = False
    
    # ============================================
    # 1. 添加导入语句（在文件开头的导入区域）
    # ============================================
    if 'from core.view_manager import ViewManager' not in content:
        # 在 "from core.audit_logger import AuditLogger" 后面添加
        old_import = 'from core.audit_logger import AuditLogger'
        new_import = '''from core.audit_logger import AuditLogger
from core.view_manager import ViewManager  # Task 012: 视图管理'''
        
        if old_import in content:
            content = content.replace(old_import, new_import)
            print("[OK] 已添加 ViewManager 导入")
            modified = True
    
    # ============================================
    # 2. 在 __init__ 中添加 ViewManager 初始化
    # ============================================
    if 'self.view_manager = None' not in content and 'self.view_manager' not in content:
        # 在 _init_column_width_tracking() 后面添加
        old_init = '        self._init_column_width_tracking()  # Task 008：列宽变化追踪'
        new_init = old_init + '''
        
        # Task 012: 视图管理器初始化
        self.view_manager = ViewManager()
        self._refresh_view_list()
'''
        
        if old_init in content:
            content = content.replace(old_init, new_init)
            print("[OK] 已添加 ViewManager 初始化")
            modified = True
    
    # ============================================
    # 3. 添加视图管理工具栏（在 build_ui 中，table_frame 之前）
    # ============================================
    if 'view_bar' not in content:
        # 找到 table_frame 的定义位置
        table_frame_idx = content.find('        self.table_frame =')
        
        if table_frame_idx > 0:
            # 在 table_frame 定义前插入视图工具栏
            view_toolbar = '''
        # ---------- 视图管理工具栏 ----------
        view_bar = tk.Frame(self.root, bg=C['surface'])
        view_bar.pack(fill="x", padx=12, pady=(0, 5))
        
        tk.Label(view_bar, text="视图:", font=("Microsoft YaHei", 9),
                 bg=C['surface'], fg=C['text_dim']).pack(side="left")
        
        self.view_combo = ttk.Combobox(view_bar, state="readonly", width=20, font=("Microsoft YaHei", 9))
        self.view_combo.pack(side="left", padx=5)
        self.view_combo.bind("<<ComboboxSelected>>", lambda e: self._load_selected_view())
        
        self.save_view_btn = tk.Button(view_bar, text="💾 保存当前视图", command=self._save_current_view,
                                      bg="#28a745", fg="white", relief="flat", font=("Microsoft YaHei", 8))
        self.save_view_btn.pack(side="left", padx=2)
        
        self.del_view_btn = tk.Button(view_bar, text="🗑️ 删除视图", command=self._delete_selected_view,
                                      bg="#dc3545", fg="white", relief="flat", font=("Microsoft YaHei", 8))
        self.del_view_btn.pack(side="left", padx=2)
        
        self.refresh_view_btn = tk.Button(view_bar, text="🔄 刷新列表", command=self._refresh_view_list,
                                          bg="#6c757d", fg="white", relief="flat", font=("Microsoft YaHei", 8))
        self.refresh_view_btn.pack(side="left", padx=2)
'''
            
            # 插入到 table_frame 之前
            content = content[:table_frame_idx] + view_toolbar + '\n' + content[table_frame_idx:]
            print("[OK] 已添加视图管理工具栏")
            modified = True
    
    # ============================================
    # 4. 在菜单栏添加管理看板按钮（如果还没有）
    # ============================================
    if '管理看板' not in content or 'DashboardWindow' not in content:
        # 在 history_menu 中添加管理看板菜单项
        old_menu = "        history_menu.add_command(label='历史对比', command=self._show_history_compare)"
        new_menu = old_menu + '''
        history_menu.add_separator()
        history_menu.add_command(label='📊 管理看板', command=self._show_management_dashboard)'''
        
        if old_menu in content:
            content = content.replace(old_menu, new_menu)
            print("[OK] 已添加管理看板菜单项")
            modified = True
    
    # ============================================
    # 5. 添加视图管理方法（在类末尾）
    # ============================================
    if '_save_current_view' not in content:
        # 在类末尾（before `if __name__`）添加方法
        view_methods = '''
    
    # ---------- Task 012: 视图管理方法 ----------
    def _show_management_dashboard(self):
        """打开管理看板窗口"""
        try:
            from gui.management_dashboard import DashboardWindow
            DashboardWindow(self)
        except Exception as e:
            self.log(f"打开管理看板失败: {e}", "error")
    
    def _refresh_view_list(self):
        """刷新视图下拉列表"""
        try:
            if hasattr(self, 'view_manager') and self.view_manager:
                views = self.view_manager.list_views()
                self.view_combo['values'] = views
                current = self.view_combo.get()
                if views:
                    if current not in views:
                        self.view_combo.set(views[0])
                else:
                    self.view_combo.set('')
        except Exception as e:
            self.log(f"刷新视图列表失败: {e}", "error")
    
    def _save_current_view(self):
        """保存当前视图状态"""
        from tkinter import simpledialog
        name = simpledialog.askstring("保存视图", "请输入视图名称:")
        if name and name.strip():
            try:
                state = self._get_current_view_state()
                self.view_manager.save_view(name.strip(), state)
                self._refresh_view_list()
                self.log(f"✅ 视图 '{name}' 已保存", "info")
            except Exception as e:
                self.log(f"保存视图失败: {e}", "error")
    
    def _load_selected_view(self):
        """加载选中的视图"""
        name = self.view_combo.get()
        if not name:
            return
        try:
            state = self.view_manager.load_view(name)
            if state:
                self._apply_view_state(state)
                self.log(f"✅ 已加载视图 '{name}'", "info")
        except Exception as e:
            self.log(f"加载视图失败: {e}", "error")
    
    def _delete_selected_view(self):
        """删除选中的视图"""
        from tkinter import messagebox
        name = self.view_combo.get()
        if not name:
            return
        if messagebox.askyesno("确认删除", f"确定要删除视图 '{name}' 吗？"):
            try:
                self.view_manager.delete_view(name)
                self._refresh_view_list()
                self.log(f"✅ 视图 '{name}' 已删除", "info")
            except Exception as e:
                self.log(f"删除视图失败: {e}", "error")
    
    def _get_current_view_state(self):
        """收集当前界面状态（筛选、排序、列顺序、列宽）"""
        state = {
            'filters': {},
            'sort_column': getattr(self, '_current_sort_column', None),
            'sort_order': getattr(self, '_current_sort_order', 'asc'),
            'column_order': list(self.audit_tree['displaycolumns']) if self.audit_tree['displaycolumns'] else list(self.audit_tree['columns']),
            'column_widths': {col: self.audit_tree.column(col, 'width') for col in self.audit_tree['columns']}
        }
        # 收集筛选条件
        if hasattr(self, 'filter_widgets'):
            for key, widget in self.filter_widgets.items():
                if key == 'order_date':
                    start, end = widget
                    try:
                        state['filters'][key] = (start.get_date().isoformat(), end.get_date().isoformat())
                    except:
                        pass
                else:
                    val = widget.get() if hasattr(widget, 'get') else None
                    if val and val != "全部":
                        state['filters'][key] = val
        return state
    
    def _apply_view_state(self, state):
        """应用视图状态"""
        try:
            # 恢复筛选条件
            if hasattr(self, 'filter_widgets'):
                for key, value in state.get('filters', {}).items():
                    widget = self.filter_widgets.get(key)
                    if widget:
                        if key == 'order_date' and isinstance(value, (list, tuple)):
                            start_w, end_w = widget
                            from datetime import date
                            start_date = date.fromisoformat(value[0])
                            end_date = date.fromisoformat(value[1])
                            start_w.set_date(start_date)
                            end_w.set_date(end_date)
                            self._on_filter_changed(key)
                        else:
                            widget.set(value)
                            self._on_filter_changed(key)
            
            # 恢复排序
            sort_col = state.get('sort_column')
            sort_order = state.get('sort_order', 'asc')
            if sort_col:
                self._apply_sort(sort_col, sort_order)
            
            # 恢复列顺序
            col_order = state.get('column_order')
            if col_order:
                self._reorder_columns(col_order)
            
            # 恢复列宽
            for col, width in state.get('column_widths', {}).items():
                if col in self.audit_tree['columns']:
                    self.audit_tree.column(col, width=width)
            
            # 重置分页和缓存
            self._reset_pagination()
            self._row_tag_cache.clear()
            self._refresh_audit_tree(reset_pagination=False)
        except Exception as e:
            self.log(f"应用视图状态失败: {e}", "error")
    
    def _apply_sort(self, column, order='asc'):
        """对 audit_data 排序并刷新"""
        if not hasattr(self, 'audit_data') or self.audit_data is None or self.audit_data.empty:
            return
        try:
            if column in self.audit_data.columns:
                self.audit_data.sort_values(by=column, ascending=(order == 'asc'), inplace=True)
            self._reset_pagination()
            self._row_tag_cache.clear()
            self._refresh_audit_tree(reset_pagination=False)
        except Exception as e:
            self.log(f"排序失败: {e}", "error")
'''
        
        # 在文件末尾（before `if __name__ == '__main__'`）插入
        main_idx = content.find("\n\nif __name__ == '__main__':")
        if main_idx > 0:
            content = content[:main_idx] + view_methods + '\n' + content[main_idx:]
            print("[OK] 已添加视图管理方法")
            modified = True
    
    # ============================================
    # 写回文件
    # ============================================
    if modified:
        backup_path = app_py_path + '.bak'
        import shutil
        shutil.copy2(app_py_path, backup_path)
        print(f"[INFO] 已备份原文件到: {backup_path}")
        
        with open(app_py_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("\n✅ gui/app.py 补丁完成")
        print("修改内容:")
        print("  1. 添加了 ViewManager 导入和初始化")
        print("  2. 添加了视图管理工具栏（下拉框 + 保存/删除/刷新按钮）")
        print("  3. 在菜单栏添加了"管理看板"选项")
        print("  4. 添加了视图管理的所有方法")
        print("\n请测试:")
        print("  - 视图工具栏是否显示")
        print("  - 能否保存/加载/删除视图")
        print("  - 管理看板能否打开")
        return True
    else:
        print("\n⚠️ 没有检测到需要修改的内容，或者已经修改过了")
        return False

if __name__ == '__main__':
    print("="*60)
    print("开始修补 gui/app.py...")
    print("="*60)
    try:
        success = patch_app_py()
        if success:
            print("\n✅ 补丁成功！请重启程序测试。")
        else:
            print("\n⚠️ 补丁未应用，请检查。")
    except Exception as e:
        print(f"\n❌ 补丁失败: {e}")
        import traceback
        traceback.print_exc()
