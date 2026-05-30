#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
补充 UI 集成代码到 gui/app.py
- 添加 ViewManager 初始化
- 添加管理看板按钮
- 添加视图管理工具栏
- 添加视图管理方法
"""

import re

def patch_app_py():
    with open('gui/app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = content
    
    # 1. 在 __init__ 方法末尾、build_ui 调用后添加 ViewManager 初始化
    # 找到 _init_sort_columns() 后面，添加 view_manager 初始化
    init_patch = '''
        # Task 012: 视图管理器初始化
        from core.view_manager import ViewManager
        self.view_manager = ViewManager()
        self._refresh_view_list()
'''
    # 在 _init_column_width_tracking() 后插入
    if '_init_column_width_tracking()' in modified and 'self.view_manager' not in modified:
        modified = modified.replace(
            '        self._init_column_width_tracking()  # Task 008：列宽变化追踪\n        self._init_sort_columns()  # 初始化多列排序系统',
            '        self._init_column_width_tracking()  # Task 008：列宽变化追踪\n        self._init_sort_columns()  # 初始化多列排序系统' + init_patch
        )
        print("[OK] 已添加 ViewManager 初始化")
    
    # 2. 在 _build_ui 方法中、筛选栏后添加视图管理工具栏
    # 先找到 filter_bar 相关的 pack() 调用
    view_toolbar = '''
        # ---------- 视图管理工具栏 ----------
        view_bar = tk.Frame(self.root, bg=C['surface'])
        view_bar.pack(fill="x", padx=12, pady=(0, 5))
        
        tk.Label(view_bar, text="视图:", font=("Microsoft YaHei", 9),
                 bg=C['surface'], fg=C['text_dim']).pack(side="left")
        
        self.view_combo = ttk.Combobox(view_bar, state="readonly", width=20)
        self.view_combo.pack(side="left", padx=5)
        
        self.save_view_btn = tk.Button(view_bar, text="保存当前视图", command=self._save_current_view,
                                      bg="#28a745", fg="white", relief="flat", font=("Microsoft YaHei", 8))
        self.save_view_btn.pack(side="left", padx=2)
        
        self.del_view_btn = tk.Button(view_bar, text="删除视图", command=self._delete_selected_view,
                                      bg="#dc3545", fg="white", relief="flat", font=("Microsoft YaHei", 8))
        self.del_view_btn.pack(side="left", padx=2)
        
        self.refresh_view_btn = tk.Button(view_bar, text="刷新列表", command=self._refresh_view_list,
                                          bg="#6c757d", fg="white", relief="flat", font=("Microsoft YaHei", 8))
        self.refresh_view_btn.pack(side="left", padx=2)
'''
    
    # 在 table_frame.pack() 之前插入视图工具栏
    if 'self.table_frame' in modified and 'view_bar' not in modified:
        # 找到 table_frame 定义位置，在其前面插入
        modified = modified.replace(
            '        self.table_frame =',
            view_toolbar + '\n        self.table_frame ='
        )
        print("[OK] 已添加视图管理工具栏")
    
    # 3. 添加视图管理方法（在类末尾，before `if __name__` 之前）
    view_methods = '''
    # ---------- Task 012: 视图管理方法 ----------
    def _refresh_view_list(self):
        """刷新视图下拉列表"""
        try:
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
                self.log(f"视图 '{name}' 已保存", "info")
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
                self.log(f"已加载视图 '{name}'", "info")
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
                self.log(f"视图 '{name}' 已删除", "info")
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
        if not hasattr(self, 'audit_data') or self.audit_data.empty:
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
    
    # 在文件末尾（before `if __name__ == '__main__'`）插入方法
    if 'def _apply_sort' not in modified:
        modified = modified.rstrip() + '\n' + view_methods
        print("[OK] 已添加视图管理方法")
    
    # 4. 确保导入 tkinter 对话框
    if 'from tkinter import' in modified and 'simpledialog' not in modified:
        modified = modified.replace(
            'from tkinter import scrolledtext, messagebox, filedialog, ttk',
            'from tkinter import scrolledtext, messagebox, filedialog, ttk, simpledialog'
        )
        print("[OK] 已添加 simpledialog 导入")
    
    # 写回文件
    with open('gui/app.py', 'w', encoding='utf-8') as f:
        f.write(modified)
    
    print("\n✅ gui/app.py 补丁完成")
    print("请检查并测试：")
    print("  1. 视图管理工具栏是否显示")
    print("  2. 管理看板按钮是否可用")
    print("  3. 保存/加载/删除视图功能")

if __name__ == '__main__':
    patch_app_py()
