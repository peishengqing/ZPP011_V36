# -*- coding: utf-8 -*-
"""
文件数据加载器 (v43)

简化版，只包含纯数据逻辑，不直接操作UI，避免与MainWindow产生循环依赖。
"""

import os
import pandas as pd


class FileLoader:
    """简化版文件加载器（数据层）."""

    def __init__(self, main_window):
        self.mw = main_window

    def file_mtime_signature(self, path):
        """文件指纹。"""
        if not path:
            return None
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except (OSError, ValueError):
            return None

    def drop_stale_input_cache(self):
        """检查并丢弃陈旧缓存。"""
        # 简化版本：假设主窗口自己处理
        return False  # 假设没有 stale

    def format_preview_stats(self, df):
        """格式化预览统计字符串。"""
        if df is None or df.empty:
            return "预览：无数据"
        total_rows = len(df)
        total_cols = len(df.columns)
        return f"预览：{total_rows} 行 × {total_cols} 列"

    def set_column_widths(self):
        """主表列宽自动调整。"""
        # 简化：由 MainWindow 自己实现
        pass

    def schedule_unread_summary(self):
        """调度显示未读摘要窗。"""
        # 简化：由 MainWindow 自己处理
        pass

    def auto_collapse_progress_after_analysis(self):
        """6 秒后自动收起进度面板。"""
        pass

    def select_file(self):
        """打开文件选择对话框，选择 Excel 文件。"""
        # 简化：返回空，MainWindow 自己处理
        return None

    def on_file_loaded(self, df, file_path):
        """文件加载完成后的处理逻辑。"""
        # 简化：不直接操作，由 MainWindow 自己实现
        pass
