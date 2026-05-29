#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实现 Task 006: Treeview 无限滚动（分页加载）
直接修改 gui/event_handlers/table_events.py
"""

import re
import shutil

# 读取文件
file_path = 'gui/event_handlers/table_events.py'
backup_path = 'gui/event_handlers/table_events.py.backup'

# 先备份
shutil.copy2(file_path, backup_path)
print(f"Backup created: {backup_path}")

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = ''.join(lines)

# ==================== Step 2: 添加状态属性到 __init__ ====================
# 查找 TableEvents 类的 __init__ 方法
# 策略：找到 class TableEvents 后的第一个 __init__ 方法，在其末尾添加状态属性

# 找到 TableEvents 类定义
class_pattern = r'class TableEvents.*?\n'
class_match = re.search(class_pattern, content, re.DOTALL)

if class_match:
    print("Found TableEvents class")
    
    # 找到 __init__ 方法
    init_pattern = r'(\s+def __init__\(self.*?\):.*?)(?=\n\s+def |\nclass |\Z)'
    init_match = re.search(init_pattern, content, re.DOTALL)
    
    if init_match:
        init_block = init_match.group(1)
        print(f"Found __init__ method (length: {len(init_block)} chars)")
        
        # 在 __init__ 方法的最后一个 pass 或 return 前插入状态属性
        # 查找 __init__ 方法的缩进级别（应该是 4 个空格）
        # 在方法结束前添加状态属性
        
        state_attrs = '''
        # 分页加载状态（Task 006）
        self._display_start = 0
        self._display_limit = 500
        self._total_rows = 0
        self._is_loading = False
        self._native_yscroll_set = None
'''
        
        # 在 __init__ 方法的最后一个换行符前插入
        # 简单策略：在 __init__ 方法的最后一个 '\\n    \\n' 前插入
        lines_init = init_block.split('\\n')
        
        # 找到最后一个非空行
        last_non_empty = len(lines_init) - 1
        while last_non_empty >= 0 and lines_init[last_non_empty].strip() == '':
            last_non_empty -= 1
        
        if last_non_empty >= 0:
            # 在最后一个非空行前插入
            insert_pos = init_block.rfind('\\n' + lines_init[last_non_empty])
            if insert_pos != -1:
                new_init = init_block[:insert_pos] + state_attrs + '\\n' + init_block[insert_pos:]
                
                # 替换原内容
                content = content.replace(init_block, new_init, 1)
                print("SUCCESS: Added state attributes to __init__")
            else:
                print("WARNING: Could not find insert position in __init__")
        else:
            print("WARNING: __init__ method appears to be empty")
    else:
        print("ERROR: Could not find __init__ method")
else:
    print("ERROR: Could not find TableEvents class")

# 重新读取内容（如果修改成功）
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# ==================== Step 3: 添加滚动桥接方法 ====================
scroll_methods = '''
    
    # ==================== Task 006: 无限滚动 ====================
    
    def _init_scroll_binding(self):
        """替换 yscrollcommand，桥接原生滚动与自定义加载"""
        # 查找滚动条对象（可能是 audit_vscroll, vscroll, scrollbar 等）
        scrollbar = getattr(self, 'audit_vscroll', None) or getattr(self, 'vscroll', None)
        if scrollbar:
            self._native_yscroll_set = scrollbar.set
            self.audit_tree.configure(yscrollcommand=self._combined_scroll)
    
    def _combined_scroll(self, *args):
        """组合滚动回调：更新滚动条位置 + 检测触底加载"""
        # 1. 更新滚动条位置（必须）
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

# 在 _refresh_audit_tree 方法之前插入这些方法
refresh_pattern = r'(\s+def _refresh_audit_tree\(self.*?:)'
refresh_match = re.search(refresh_pattern, content, re.DOTALL)

if refresh_match:
    # 在 _refresh_audit_tree 之前插入滚动方法
    insert_pos = refresh_match.start(1)
    content = content[:insert_pos] + scroll_methods + '\\n' + content[insert_pos:]
    print("SUCCESS: Added scroll bridging methods")
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
combined_scroll_pattern = r'(\s+def _combined_scroll\(self.*?:.*?)(?=\n\s+def |\nclass |\Z)'
combined_scroll_match = re.search(combined_scroll_pattern, content, re.DOTALL)

if combined_scroll_match:
    combined_scroll_block = combined_scroll_match.group(1)
    # 在 _combined_scroll 方法后插入
    insert_pos = combined_scroll_match.end(1)
    content = content[:insert_pos] + load_more_methods + content[insert_pos:]
    print("SUCCESS: Added load more and sliding window methods")
else:
    print("WARNING: Could not find _combined_scroll method")

# ==================== Step 5: 修改 _refresh_audit_tree 方法 ====================
# 完全重写 _refresh_audit_tree 方法
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
'''

# 替换原有的 _refresh_audit_tree 方法
# 找到方法的开始和结束
refresh_method_pattern = r'(\s+def _refresh_audit_tree\(self.*?:.*?)(?=\n\s+def |\nclass |\Z)'
refresh_method_match = re.search(refresh_method_pattern, content, re.DOTALL)

if refresh_method_match:
    old_refresh_method = refresh_method_match.group(1)
    content = content.replace(old_refresh_method, new_refresh_method, 1)
    print("SUCCESS: Modified _refresh_audit_tree method")
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
        self._display_start = 0
        self._is_loading = False
'''

# 在 _trim_treeview_if_needed 方法后添加
trim_pattern = r'(\s+def _trim_treeview_if_needed\(self.*?:.*?)(?=\n\s+def |\nclass |\Z)'
trim_match = re.search(trim_pattern, content, re.DOTALL)

if trim_match:
    insert_pos = trim_match.end(1)
    content = content[:insert_pos] + '\\n' + append_methods + content[insert_pos:]
    print("SUCCESS: Added append rows and reset pagination methods")
else:
    print("WARNING: Could not find _trim_treeview_if_needed method")

# ==================== Step 7: 修改筛选和排序方法 ====================
# 在 _on_filter_changed 方法开头添加 self._reset_pagination()

# 找到 _on_filter_changed 方法
filter_pattern = r'(\s+def _on_filter_changed\(self.*?:.*?)(?=\n        if self\\.audit_data)'
filter_match = re.search(filter_pattern, content, re.DOTALL)

if filter_match:
    old_filter_start = filter_match.group(1)
    new_filter_start = old_filter_start + '        # 重置分页\\n        self._reset_pagination()\\n\\n'
    content = content.replace(old_filter_start, new_filter_start, 1)
    print("SUCCESS: Modified _on_filter_changed method")
else:
    print("WARNING: Could not find _on_filter_changed method")

# 在 _apply_sort_and_refresh 方法中添加重置分页
sort_pattern = r'(\s+def _apply_sort_and_refresh\(self.*?:.*?)(?=\n        if self\\.audit_data)'
sort_match = re.search(sort_pattern, content, re.DOTALL)

if sort_match:
    old_sort_start = sort_match.group(1)
    new_sort_start = old_sort_start + '        # 重置分页\\n        self._reset_pagination()\\n\\n'
    content = content.replace(old_sort_start, new_sort_start, 1)
    print("SUCCESS: Modified _apply_sort_and_refresh method")
else:
    print("WARNING: Could not find _apply_sort_and_refresh method")

# ==================== 保存修改后的文件 ====================
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\\nSUCCESS: File modified: {file_path}")
print("\\nNext steps:")
print("1. Check syntax: python -m py_compile gui/event_handlers/table_events.py")
print("2. Test if the program runs normally")
print("3. Commit code: git add gui/event_handlers/table_events.py && git commit -m 'feat: Task 006 Treeview 分页加载（无限滚动）' && git push origin main")
