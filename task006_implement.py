#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task 006: Implement Treeview Infinite Scroll
直接修改 table_events.py
"""

import re
import shutil

file_path = 'gui/event_handlers/table_events.py'
backup_path = 'gui/event_handlers/table_events.py.backup'

# 备份原文件
shutil.copy2(file_path, backup_path)
print("Backup created successfully")

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# ==================== Step 2: 添加状态属性 ====================
# 在 TableEvents 类中添加状态属性
# 查找 class TableEvents 定义后的第一个方法定义

class_pattern = r'(class TableEvents.*?\n)(\s+def )'
class_match = re.search(class_pattern, content, re.DOTALL)

if class_match:
    # 在第一个方法定义前插入状态属性
    insert_pos = class_match.start(2)
    
    state_attrs = '''    # 分页加载状态（Task 006）
    _display_start = 0
    _display_limit = 500
    _total_rows = 0
    _is_loading = False
    _native_yscroll_set = None
    
'''
    
    content = content[:insert_pos] + state_attrs + content[insert_pos:]
    print("Step 2: State attributes added")
else:
    print("WARNING: Could not find TableEvents class")

# ==================== Step 3: 添加滚动桥接方法 ====================
scroll_methods = '''
    
    # ==================== Task 006: 无限滚动 ====================
    
    def _init_scroll_binding(self):
        """替换 yscrollcommand，桥接原生滚动与自定义加载"""
        # 查找滚动条对象
        scrollbar = getattr(self, 'audit_vscroll', None) or getattr(self, 'vscroll', None)
        if scrollbar:
            self._native_yscroll_set = scrollbar.set
            self.audit_tree.configure(yscrollcommand=self._combined_scroll)
    
    def _combined_scroll(self, *args):
        """组合滚动回调：更新滚动条位置 + 检测触底加载"""
        # 1. 更新滚动条位置
        if self._native_yscroll_set:
            self._native_yscroll_set(*args)
        # 2. 检测触底加载
        if not self._is_loading and len(args) > 1:
            try:
                if float(args[1]) >= 0.99:
                    if self._display_start + self._display_limit < self._total_rows:
                        self._load_more_data()
            except (ValueError, IndexError):
                pass
'''

# 在 _refresh_audit_tree 方法前插入
refresh_pattern = r'(\s+def _refresh_audit_tree\(self)'
refresh_match = re.search(refresh_pattern, content)

if refresh_match:
    insert_pos = refresh_match.start(1)
    content = content[:insert_pos] + scroll_methods + '\n' + content[insert_pos:]
    print("Step 3: Scroll bridging methods added")
else:
    print("WARNING: Could not find _refresh_audit_tree method")

# ==================== Step 4: 添加加载更多和滑动窗口方法 ====================
load_more_methods = '''
    
    def _load_more_data(self):
        """加载更多数据（分页加载）"""
        if self._is_loading:
            return
        self._is_loading = True
        
        new_start = self._display_start + self._display_limit
        if new_start >= self._total_rows:
            self._is_loading = False
            return
        
        self._display_start = new_start
        # 追加数据
        self._append_rows_to_treeview(self._display_start, self._display_limit)
        # 滑动窗口：超过 2000 行时移除前面的行
        self._trim_treeview_if_needed()
        self._is_loading = False
    
    def _trim_treeview_if_needed(self):
        """滑动窗口：保持 Treeview 性能"""
        children = self.audit_tree.get_children()
        if len(children) > 2000:
            to_remove = children[:500]
            for child in to_remove:
                self.audit_tree.detach(child)  # detach 比 delete 快
'''

# 在 _combined_scroll 方法后添加
combined_pattern = r'(\s+def _combined_scroll\(self.*?:.*?)(?=\n\s+def |\nclass |\Z)'
combined_match = re.search(combined_pattern, content, re.DOTALL)

if combined_match:
    insert_pos = combined_match.end(1)
    content = content[:insert_pos] + '\n' + load_more_methods + content[insert_pos:]
    print("Step 4: Load more and sliding window methods added")
else:
    print("WARNING: Could not find _combined_scroll method")

# ==================== Step 5: 修改 _refresh_audit_tree 方法 ====================
# 完全重写 _refresh_audit_tree 方法以支持分页加载

new_refresh_method = '''    
    def _refresh_audit_tree(self, df, skip_auto_sort=False):
        """用给定的 DataFrame 刷新智能审核表格（支持分页加载）"""
        # 重置分页状态
        self._reset_pagination()
        
        # 清空 Treeview
        if hasattr(self, 'audit_tree'):
            self.audit_tree.delete(*self.audit_tree.get_children())
        
        # 设置总行数
        if df is not None and not df.empty:
            self.audit_data = df.copy()
            self._total_rows = len(df)
        else:
            self.audit_data = None
            self._total_rows = 0
        
        # 加载首屏数据
        self._append_rows_to_treeview(0, self._display_limit)
        
        # 初始化滚动绑定（如果还没初始化）
        if self._native_yscroll_set is None:
            self._init_scroll_binding()
        
        # 以下保留原有的调试和优先级标记逻辑
        if hasattr(self, '_log'):
            self._log(f"[DEBUG] _refresh_audit_tree: loaded first {self._display_limit} rows, total {self._total_rows} rows")
'''

# 替换原有的 _refresh_audit_tree 方法
refresh_method_pattern = r'(\s+def _refresh_audit_tree\(self.*?:.*?)(?=\n\s+def |\nclass |\Z)'
refresh_method_match = re.search(refresh_method_pattern, content, re.DOTALL)

if refresh_method_match:
    old_method = refresh_method_match.group(1)
    content = content.replace(old_method, new_refresh_method, 1)
    print("Step 5: _refresh_audit_tree method modified")
else:
    print("WARNING: Could not find _refresh_audit_tree method to replace")

# ==================== Step 6: 添加追加行和重置分页方法 ====================
append_methods = '''    
    def _append_rows_to_treeview(self, start, limit):
        """追加行到 Treeview（分页加载核心）"""
        if not hasattr(self, 'audit_data') or self.audit_data is None:
            return
        
        end = min(start + limit, self._total_rows)
        
        for idx in range(start, end):
            if idx >= len(self.audit_data):
                break
            
            row_data = self.audit_data.iloc[idx]
            
            # 转换为 treeview 可识别的值列表（按列顺序）
            values = [str(row_data.get(col, '')) for col in self.audit_tree['columns']]
            
            # 获取 tag（查找现有的 tag 逻辑）
            tags = self._get_row_tags(idx) if hasattr(self, '_get_row_tags') else ()
            
            self.audit_tree.insert("", "end", values=values, tags=tags)
    
    def _reset_pagination(self):
        """重置分页状态"""
        self.__class__._display_start = 0
        self.__class__._is_loading = False
'''

# 在 _trim_treeview_if_needed 方法后添加
trim_pattern = r'(\s+def _trim_treeview_if_needed\(self.*?:.*?)(?=\n\s+def |\nclass |\Z)'
trim_match = re.search(trim_pattern, content, re.DOTALL)

if trim_match:
    insert_pos = trim_match.end(1)
    content = content[:insert_pos] + '\n' + append_methods + content[insert_pos:]
    print("Step 6: Append rows and reset pagination methods added")
else:
    print("WARNING: Could not find _trim_treeview_if_needed method")

# ==================== Step 7: 修改筛选和排序方法 ====================
# 在 _on_filter_changed 方法开头添加 self._reset_pagination()

# 查找 _on_filter_changed 方法
filter_pattern = r'(\s+def _on_filter_changed\(self.*?:.*?)(?=\n        if self\.audit_data)'
filter_match = re.search(filter_pattern, content, re.DOTALL)

if filter_match:
    old_filter_start = filter_match.group(1)
    new_filter_start = old_filter_start + '        # 重置分页\n        self._reset_pagination()\n\n'
    content = content.replace(old_filter_start, new_filter_start, 1)
    print("Step 7a: _on_filter_changed method modified")
else:
    print("WARNING: Could not find _on_filter_changed method")

# 在 _apply_sort_and_refresh 方法中添加重置分页
sort_pattern = r'(\s+def _apply_sort_and_refresh\(self.*?:.*?)(?=\n        if self\.audit_data)'
sort_match = re.search(sort_pattern, content, re.DOTALL)

if sort_match:
    old_sort_start = sort_match.group(1)
    new_sort_start = old_sort_start + '        # 重置分页\n        self._reset_pagination()\n\n'
    content = content.replace(old_sort_start, new_sort_start, 1)
    print("Step 7b: _apply_sort_and_refresh method modified")
else:
    print("WARNING: Could not find _apply_sort_and_refresh method")

# ==================== 保存修改后的文件 ====================
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n" + "="*60)
print("SUCCESS: File modified successfully")
print("="*60)
print("\nNext steps:")
print("1. Verify syntax: python -m py_compile gui/event_handlers/table_events.py")
print("2. Test the application")
print("3. Commit: git add gui/event_handlers/table_events.py")
print("4. Commit: git commit -m 'feat: Task 006 Treeview 分页加载（无限滚动）'")
print("5. Push: git push origin main")
