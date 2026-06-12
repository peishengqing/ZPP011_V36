#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""添加辅助方法 _get_deviation_rate() 和 _is_warning_column()"""

def add_helpers():
    fp = r"E:\zpp011_dev\模块化脚本\gui_pyside6\models\data_frame_model.py"
    
    with open(fp, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"文件行数: {len(lines)}")
    
    # 找到 setData() 方法结束的位置（return False 之后）
    insert_pos = None
    for i, line in enumerate(lines):
        if '        return False\n' in line and i > 180 and i < 220:
            # 检查下一行是否是空行或 def sort(
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.strip() == '' or next_line.startswith('    def '):
                    insert_pos = i + 1  # 在 return False 之后插入
                    print(f"找到插入位置: 行 {insert_pos+1}")
                    break
    
    if insert_pos is None:
        print("错误：未找到插入位置")
        return False
    
    # 辅助方法代码
    helpers = '''    def _get_deviation_rate(self, row):
        """从缓存中获取当前行的偏差率（百分比数值）"""
        # 查找偏差率列索引
        rate_col = None
        for i, col in enumerate(self._display_columns):
            if col in ('偏差率(%)', '偏差率'):
                rate_col = i
                break
        if rate_col is None:
            return 0.0
        val = self._data_cache[row][rate_col]
        if isinstance(val, (int, float)):
            return float(val)
        # 如果缓存中是带%的字符串（兜底）
        if isinstance(val, str) and '%' in val:
            try:
                return float(val.replace('%', '').strip())
            except:
                return 0.0
        return 0.0

    def _is_warning_column(self, col_name):
        """检查列是否为预警列"""
        return col_name in ('偏差率(%)', '偏差率')

'''
    
    # 插入
    new_lines = lines[:insert_pos] + [helpers] + lines[insert_pos:]
    
    # 写入
    with open(fp, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"插入完成: {len(lines)} 行 -> {len(new_lines)} 行")
    return True

if __name__ == '__main__':
    ok = add_helpers()
    print("\n=== 添加完成 ===" if ok else "\n=== 添加失败 ===")
