# 生成报告.py
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

# 确保能导入同目录下的 ppt_generator 模块
sys.path.append(os.path.dirname(__file__))
from ppt_generator import run_ppt_generation

def main():
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    excel_path = filedialog.askopenfilename(
        title="请选择偏差数据 Excel 文件",
        filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")]
    )
    if not excel_path:
        return
    
    # 生成输出路径：在原文件名后加 _专业报告
    base, ext = os.path.splitext(excel_path)
    output_path = f"{base}_专业报告.pptx"
    success = run_ppt_generation(excel_path, output_path)
    
    if success:
        messagebox.showinfo("成功", f"报告已生成：\n{output_path}\n\n是否打开所在文件夹？")
        # 打开文件夹并选中文件
        os.startfile(os.path.dirname(output_path))
    else:
        messagebox.showerror("失败", "报告生成失败，请查看控制台错误信息。")
    
    input("按回车键退出...")

if __name__ == "__main__":
    main()