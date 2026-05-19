# -*- coding: utf-8 -*-
"""淇 PPT 鐢熸垚杩涘害鏉′笉鏇存柊闂"""
import os

fp = r'E:\zpp011_dev\妯″潡鍖栬剼鏈琝gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 淇1: 娣诲姞 _update_ppt_progress 鏂规硶
old_generate_ppt = '''    def generate_ppt(self):
        """閫夋嫨 Excel 鍒嗘瀽缁撴灉锛岀敓鎴?PPT 鎶ュ憡"""
        excel_path = filedialog.askopenfilename(
            title="閫夋嫨 zpp011 鍋忓樊鍒嗘瀽 Excel 鏂囦欢",
            filetypes=[("Excel 鏂囦欢", "*.xlsx *.xls"), ("鎵€鏈夋枃浠?, "*.*")]
        )
        if not excel_path:
            return
        out_dir = self.output_dir.get() or os.path.dirname(excel_path)
        base = os.path.splitext(os.path.basename(excel_path))[0]
        output_path = os.path.join(out_dir, base + ".pptx")
        self.log(f"馃搳 寮€濮嬬敓鎴?PPT锛歿os.path.basename(excel_path)}", "info")
        self.ppt_btn.configure(state="disabled", text="鐢熸垚涓?..")
        self.status_lbl.configure(text="姝ｅ湪鐢熸垚 PPT...", fg=C['purple'])

        def worker():
            try:
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log)
                self.root.after(0, lambda: self._on_ppt_done(output_path))
            except Exception as e:
                self.root.after(0, lambda: self._on_ppt_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()'''

new_generate_ppt = '''    def _update_ppt_progress(self, pct, msg=""):
        """鏇存柊PPT鐢熸垚杩涘害鏉?""
        self.progress_var.set(pct)
        if msg:
            self.status_lbl.configure(text=f"姝ｅ湪鐢熸垚 PPT... {msg}")
        self.root.update_idletasks()

    def generate_ppt(self):
        """閫夋嫨 Excel 鍒嗘瀽缁撴灉锛岀敓鎴?PPT 鎶ュ憡锛堝甫杩涘害鏉★級"""
        excel_path = filedialog.askopenfilename(
            title="閫夋嫨 zpp011 鍋忓樊鍒嗘瀽 Excel 鏂囦欢",
            filetypes=[("Excel 鏂囦欢", "*.xlsx *.xls"), ("鎵€鏈夋枃浠?, "*.*")]
        )
        if not excel_path:
            return
        out_dir = self.output_dir.get() or os.path.dirname(excel_path)
        base = os.path.splitext(os.path.basename(excel_path))[0]
        output_path = os.path.join(out_dir, base + ".pptx")
        
        # 閲嶇疆杩涘害鏉?        self.progress_var.set(0)
        self.progress_bar.pack(fill="x", expand=True, padx=5, pady=2)
        
        self.log(f"馃搳 寮€濮嬬敓鎴?PPT锛歿os.path.basename(excel_path)}", "info")
        self.ppt_btn.configure(state="disabled", text="鐢熸垚涓?..")
        self.status_lbl.configure(text="姝ｅ湪鐢熸垚 PPT...", fg=C['purple'])

        def worker():
            try:
                def progress_cb(current, total, msg=""):
                    pct = int(current / total * 100) if total > 0 else 0
                    self.root.after(0, lambda: self._update_ppt_progress(pct, msg))
                
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log, progress_cb=progress_cb)
                self.root.after(0, lambda: self._on_ppt_done(output_path))
            except Exception as e:
                import traceback
                err_msg = traceback.format_exc()
                self.log(f"[PPT] 鐢熸垚澶辫触: {err_msg}", "error")
                self.root.after(0, lambda: self._on_ppt_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()'''

if old_generate_ppt in content:
    content = content.replace(old_generate_ppt, new_generate_ppt)
    print('OK: Fixed generate_ppt with progress bar')
else:
    print('SKIP: generate_ppt pattern not found')

# 淇2: 鏇存柊 _on_ppt_done 闅愯棌杩涘害鏉?old_done = '''    def _on_ppt_done(self, output_path):
        self.ppt_btn.configure(state="normal", text="馃搳 鐢熸垚PPT")
        self.status_lbl.configure(text=f"PPT 宸茬敓鎴?鈥?{os.path.basename(output_path)}", fg=C['green'])'''

new_done = '''    def _on_ppt_done(self, output_path):
        self.progress_var.set(100)
        self.progress_bar.pack_forget()
        self.ppt_btn.configure(state="normal", text="馃搳 鐢熸垚PPT")
        self.status_lbl.configure(text=f"PPT 宸茬敓鎴?鈥?{os.path.basename(output_path)}", fg=C['green'])'''

if old_done in content:
    content = content.replace(old_done, new_done)
    print('OK: Fixed _on_ppt_done to hide progress bar')
else:
    print('SKIP: _on_ppt_done pattern not found')

# 淇3: 鏇存柊 _on_ppt_error 闅愯棌杩涘害鏉?old_error = '''    def _on_ppt_error(self, msg):
        self.ppt_btn.configure(state="normal", text="馃搳 鐢熸垚PPT")
        self.status_lbl.configure(text="PPT 鐢熸垚鍑洪敊", fg=C['danger'])'''

new_error = '''    def _on_ppt_error(self, msg):
        self.progress_bar.pack_forget()
        self.ppt_btn.configure(state="normal", text="馃搳 鐢熸垚PPT")
        self.status_lbl.configure(text="PPT 鐢熸垚鍑洪敊", fg=C['danger'])'''

if old_error in content:
    content = content.replace(old_error, new_error)
    print('OK: Fixed _on_ppt_error to hide progress bar')
else:
    print('SKIP: _on_ppt_error pattern not found')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')

