# -*- coding: utf-8 -*-
# Fix _show_attribution_standalone method in app.py

content = open(r'E:\zpp011_dev\模块化脚本\gui\app.py', 'r', encoding='utf-8').read()

# Read the correct new method from user's patch
new_method = '''    def _show_attribution_standalone(self):
        """独立 AI 归因分析入口（Task 013）"""
        from core.attribution import generate_report_text, get_latest_history_analysis
        from tkinter import filedialog, messagebox
        import traceback

        df = self.get_current_audit_data()
        if df is None or df.empty:
            messagebox.showinfo("提示", "当前无分析数据，请先完成分析")
            return

        try:
            history_df = get_latest_history_analysis()
            report = generate_report_text(df, history_df)
            if not report or report.strip() == "":
                report = "（未生成有效报告，请检查数据完整性或联系管理员）"
        except Exception as e:
            report = f"归因分析失败：{str(e)}\n{traceback.format_exc()}"

        # 弹出报告窗口
        win = tk.Toplevel(self.root)
        win.title("AI 归因分析报告")
        win.geometry("600x400")
        text = tk.Text(win, wrap=tk.WORD, font=("微软雅黑", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, report)
        text.config(state=tk.DISABLED)

        def save_report():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt", filetypes=[("Text files", "*.txt")]
            )
            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(report)
                messagebox.showinfo("保存成功", f"报告已保存至 {file_path}")

        tk.Button(win, text="保存报告", command=save_report).pack(side=tk.LEFT, padx=10, pady=5)
        tk.Button(win, text="关闭", command=win.destroy).pack(side=tk.RIGHT, padx=10, pady=5)
'''

# Find the old method
import re
pattern = r'    def _show_attribution_standalone\(self\):\r\n.*?        tk\.Button\(win, text="关闭", command=win\.destroy\)\.pack\(side=tk\.RIGHT, padx=10, pady=5\)\r\n'
match = re.search(pattern, content, re.DOTALL)
if match:
    old_method = match.group(0)
    print(f'Found old method: {len(old_method)} chars')
    content = content.replace(old_method, new_method)
    open(r'E:\zpp011_dev\模块化脚本\gui\app.py', 'w', encoding='utf-8').write(content)
    print('Replacement done')
else:
    print('Pattern not found, trying without \\r')
    pattern2 = r'    def _show_attribution_standalone\(self\):\n.*?        tk\.Button\(win, text="关闭", command=win\.destroy\)\.pack\(side=tk\.RIGHT, padx=10, pady=5\)\n'
    match2 = re.search(pattern2, content, re.DOTALL)
    if match2:
        old_method = match2.group(0)
        print(f'Found without \\r: {len(old_method)} chars')
        content = content.replace(old_method, new_method)
        open(r'E:\zpp011_dev\模块化脚本\gui\app.py', 'w', encoding='utf-8').write(content)
        print('Replacement done (no \\r)')
    else:
        print('Still not found')
        # Try to find just the method start
        idx = content.find('    def _show_attribution_standalone(self):')
        if idx >= 0:
            print(f'Method starts at position {idx}')
            print(repr(content[idx:idx+200]))