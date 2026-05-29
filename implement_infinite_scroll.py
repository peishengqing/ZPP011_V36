#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实现 Task 006: Treeview 无限滚动（分页加载）
自动修改 gui/event_handlers/table_events.py
"""

import re

# 读取文件
with open('gui/event_handlers/table_events.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ==================== Step 2: 添加状态属性 ====================
# 查找 TableEvents 类的 __init__ 方法
init_pattern = r'(class TableEvents.*?def __init__\(self.*?\):.*?)(?=\n    def |\nclass |\Z)'
init_match = re.search(init_pattern, content, re.DOTALL)

if init_match:
    init_block = init_match.group(1)
    print("找到 __init__ 方法")
    
    # 在 __init__ 方法末尾添加状态属性
    # 查找 __init__ 方法的最后一个 pass 或 return 或方法结束位置
    lines = init_block.split('\n')
    insert_pos = len(init_block)
    
    # 在 __init__ 方法结束前插入
    state_attrs = '''
        # 分页加载状态（Task 006）
        self._display_start = 0
        self._display_limit = 500
        self._total_rows = 0
        self._is_loading = False
        self._native_yscroll_set = None
'''
    
    # 在 __init__ 方法结束前插入（在最后一个缩进块之前）
    # 简单策略：在类定义中的第一个方法定义前插入
    content = re.sub(
        r'(class TableEvents.*?def __init__\(self.*?:.*?)(?=\n    def )',
        r'\1' + state_attrs + '\n    ',
        content,
        count=1,
        flags=re.DOTALL
    )
    print("✓ 已添加状态属性")
else:
    print("✗ 未找到 __init__ 方法")

# 重新读取（如果修改成功）
with open('gui/event_handlers/table_events.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ==================== Step 3: 实现滚动桥接 ====================
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

# 在类中添加这些方法（在 _refresh_audit_tree 方法之前）
content = re.sub(
    r'(    def _refresh_audit_tree\(self.*?:)',
    scroll_methods + r'\1',
    content,
    count=1,
    flags=re.DOTALL
)
print("✓ 已添加滚动桥接方法")

# ==================== Step 4: 实现加载更多和滑动窗口 ====================
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
content = re.sub(
    r'(    def _combined_scroll\(self.*?:.*?)(?=\n    def _|\nclass )',
    r'\1' + load_more_methods,
    content,
    count=1,
    flags=re.DOTALL
)
print("✓ 已添加加载更多和滑动窗口方法")

# ==================== Step 5: 实现重置分页和刷新 ====================
# 修改现有的 _refresh_audit_tree 方法
old_refresh_pattern = r'(def _refresh_audit_tree\(self.*?\):.*?)(?=\n    def |\nclass |\Z)'
refresh_match = re.search(old_refresh_pattern, content, re.DOTALL)

if refresh_match:
    old_refresh = refresh_match.group(1)
    print("找到 _refresh_audit_tree 方法，准备修改...")
    
    # 新实现
    new_refresh = '''def _refresh_audit_tree(self, df, skip_auto_sort=False):
        """用给定的 DataFrame 刷新智能审核表格（支持分页加载）"""
        # 重置分页状态
        self._reset_pagination()
        
        # 清空 Treeview
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
    
    # 替换整个方法
    content = content.replace(old_refresh, new_refresh, 1)
    print("✓ 已修改 _refresh_audit_tree 方法")
else:
    print("✗ 未找到 _refresh_audit_tree 方法")

# ==================== Step 6: 实现追加行方法 ====================
append_method = '''
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
content = re.sub(
    r'(    def _trim_treeview_if_needed\(self.*?:.*?)(?=\n    def _|\nclass )',
    r'\1' + append_method,
    content,
    count=1,
    flags=re.DOTALL
)
print("✓ 已添加追加行和重置分页方法")

# ==================== Step 7: 修改筛选和排序方法 ====================
# 在 _on_filter_changed 方法开头添加 self._reset_pagination()
filter_pattern = r'(def _on_filter_changed\(self.*?:.*?)(?=\n        if self\.audit_data)'
filter_match = re.search(filter_pattern, content, re.DOTALL)

if filter_match:
    old_filter_start = filter_match.group(1)
    new_filter_start = old_filter_start + '        # 重置分页\n        self._reset_pagination()\n\n'
    content = content.replace(old_filter_start, new_filter_start, 1)
    print("✓ 已修改 _on_filter_changed 方法")
else:
    print("✗ 未找到 _on_filter_changed 方法")

# 在 _apply_sort_and_refresh 方法中添加重置分页
sort_pattern = r'(def _apply_sort_and_refresh\(self.*?:.*?)(?=\n        if self\.audit_data)'
sort_match = re.search(sort_pattern, content, re.DOTALL)

if sort_match:
    old_sort_start = sort_match.group(1)
    new_sort_start = old_sort_start + '        # 重置分页\n        self._reset_pagination()\n\n'
    content = content.replace(old_sort_start, new_sort_start, 1)
    print("✓ 已修改 _apply_sort_and_refresh 方法")
else:
    print("✗ 未找到 _apply_sort_and_refresh 方法")

# ==================== 保存修改后的文件 ====================
backup_path = 'gui/event_handlers/table_events.py.backup'
import shutil
shutil.copy2('gui/event_handlers/table_events.py', backup_path)
print(f"\n已备份原文件到: {backup_path}")

with open('gui/event_handlers/table_events.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✓ 已成功修改 gui/event_handlers/table_events.py")
print("\n下一步:")
print("1. 检查语法: python -m py_compile gui/event_handlers/table_events.py")
print("2. 测试程序是否正常运行")
print("3. 提交代码: git add gui/event_handlers/table_events.py && git commit -m 'feat: Task 006 Treeview 分页加载（无限滚动）' && git push origin main")
