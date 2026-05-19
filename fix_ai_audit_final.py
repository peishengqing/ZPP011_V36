# -*- coding: utf-8 -*-
"""最终修复 _run_ai_audit 和 _refresh_alt_view 方法"""
import sys, re, subprocess

path = r'E:\zpp011_dev\模块化脚本\gui\events.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ========== 1. 修复 _run_ai_audit 方法 ==========
# 找到方法开头和结尾
run_start = content.find('    def _run_ai_audit(self):\n')
if run_start == -1:
    print("[ERROR] _run_ai_audit 方法未找到")
    sys.exit(1)

# 找到方法结尾（下一个 def 或类结束）
run_end = content.find('\n    def ', run_start + 1)
if run_end == -1:
    run_end = content.find('\nclass ', run_start + 1)
if run_end == -1:
    run_end = len(content)

print(f"[INFO] 找到 _run_ai_audit: 位置 {run_start}-{run_end}")

# 新代码（修正语法错误）
new_run_ai_audit = '''    def _run_ai_audit(self):
        """AI审核：只处理未审核且非自动填充/替代料的行"""
        if self.is_auditing:
            messagebox.showwarning("提示", "AI审核正在运行，请等待完成或点击取消")
            return
        if self.audit_data is None or self.audit_data.empty:
            messagebox.showwarning("警告", "没有审核数据，请先加载审核数据")
            return

        # 确保必要列存在
        for col in ['audit_result', 'AI建议', '备注来源']:
            if col not in self.audit_data.columns:
                self.audit_data[col] = ''

        # 构建替代料名称集合（用于自动填充/替代料判断）
        alt_all_descs = set()
        for a, b in getattr(self, 'alt_pairs', []):
            for item in (a, b):
                if item:
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        desc = str(item[2]).strip()
                    elif isinstance(item, (list, tuple)) and len(item) == 2:
                        desc = str(item[1]).strip() if item[1] else str(item[0]).strip()
                    else:
                        desc = str(item).strip()
                    if desc and desc != 'None':
                        alt_all_descs.add(desc)

        # 自动填充条件（透明胶、600开头物料）
        is_auto_fill = (
            self.audit_data['组件物料描述'].astype(str).str.contains('透明胶', na=False) |
            self.audit_data['组件物料号'].astype(str).str.startswith('600')
        )
        is_alt = self.audit_data['组件物料描述'].astype(str).str.strip().isin(alt_all_descs)
        exclude_sources = ['人工填写', '自动填充', '替代料', 'AI审核合格', 'AI审核待改进', 'AI生成']
        is_already_processed = self.audit_data['备注来源'].isin(exclude_sources)

        to_audit_mask = (
            (self.audit_data['audit_result'].isna() | (self.audit_data['audit_result'] == '')) &
            (~is_auto_fill) &
            (~is_alt) &
            (~is_already_processed)
        )

        # ⚠️ 关键：提取需要审核的索引列表
        audit_indices = self.audit_data[to_audit_mask].index.tolist()
        if not audit_indices:
            messagebox.showinfo("提示", "没有需要AI审核的行")
            return

        # 进度条
        self.progress_bar.configure(mode='determinate', maximum=100)
        self.progress_bar['value'] = 0
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)
        self.set_status("AI审核中...")
        self._ai_cancel_flag = threading.Event()
        self.is_auditing = True

        df_to_audit = self.audit_data.loc[audit_indices].copy()
        _my_cancel_flag = self._ai_cancel_flag

        def _worker(progress_callback):
            total = len(audit_indices)
            popup_rows = []
            remark_col = next((c for c in ['备注原因', '备注'] if c in df_to_audit.columns), None)
            name_col = next((c for c in ['组件物料描述', '物料名称'] if c in df_to_audit.columns), None)
            rate_col = next((c for c in ['偏差率(%)', '偏差率'] if c in df_to_audit.columns), None)
            for seq, idx in enumerate(audit_indices):
                if _my_cancel_flag.is_set():
                    raise InterruptedError("用户取消了AI审核")
                row = df_to_audit.loc[idx]
                remark = row[remark_col] if remark_col else ''
                dev_rate_raw = row[rate_col] if rate_col else 0
                try:
                    dev_rate = float(dev_rate_raw or 0)
                except:
                    dev_rate = 0.0
                material_desc = str(row[name_col]) if name_col else ''
                try:
                    result = self.ai_client.audit(remark, dev_rate)
                    audit_result = result.get('result', '需补备注')
                    ai_suggestion = result.get('suggestion', '')
                except Exception as ex:
                    audit_result = '审核失败'
                    ai_suggestion = str(ex)
                popup_rows.append({
                    'idx': idx,
                    '物料': material_desc,
                    '偏差率': f"{dev_rate:.1f}%",
                    '原备注': str(remark) if not pd.isna(remark) else '',
                    'AI建议': ai_suggestion,
                    '审核结果': audit_result,
                    '_audit_result': audit_result,
                    '_ai_suggestion': ai_suggestion,
                })
                if progress_callback:
                    progress_callback(int((seq + 1) / total * 100))
            return popup_rows

        def _on_progress(pct):
            self.root.after(0, lambda p=pct: (
                self.progress_bar.configure(value=p),
                self.set_status(f"AI审核中... {p}%")
            ))

        self.task_manager.run(
            _worker,
            callback=self._on_ai_audit_done,
            error_callback=self._on_ai_audit_error,
            progress_callback=_on_progress,
        )

'''

# 替换
content = content[:run_start] + new_run_ai_audit + content[run_end:]

# ========== 2. 修复 _refresh_alt_view 方法 ==========
alt_start = content.find('    def _refresh_alt_view(self, inner):\n')
if alt_start == -1:
    print("[WARN] _refresh_alt_view 方法未找到，跳过")
else:
    alt_end = content.find('\n    def ', alt_start + 1)
    if alt_end == -1:
        alt_end = len(content)
    
    print(f"[INFO] 找到 _refresh_alt_view: 位置 {alt_start}-{alt_end}")
    
    # 新代码（修正语法错误）
    new_alt_view = '''    def _refresh_alt_view(self, inner):
        for w in inner.winfo_children():
            w.destroy()
        for a, b in self.alt_pairs:
            # 期望 a, b 都是 (factory, code, name) 格式
            if isinstance(a, (list, tuple)) and len(a) >= 3:
                a_factory, a_code, a_name = a[0], a[1], a[2]
            else:
                a_factory, a_code, a_name = '', str(a), ''
            if isinstance(b, (list, tuple)) and len(b) >= 3:
                b_factory, b_code, b_name = b[0], b[1], b[2]
            else:
                b_factory, b_code, b_name = '', str(b), ''
            
            # 显示：编码 + 名称（若名称存在）
            a_disp = f"{a_code} {a_name}" if a_name else a_code
            b_disp = f"{b_code} {b_name}" if b_name else b_code
            
            fr = tk.Frame(inner, bg=C['surface2'])
            fr.pack(fill="x", pady=1)
            tk.Label(fr, text=f"↔ {a_disp}", font=("Consolas", 8), fg=C['text'],
                     bg=C['surface2'], anchor="w").pack(side="left", padx=4)
            tk.Label(fr, text="|", font=("Consolas", 8), fg=C['text_dim'],
                     bg=C['surface2']).pack(side="left")
            tk.Label(fr, text=b_disp, font=("Consolas", 8), fg=C['purple'],
                     bg=C['surface2'], anchor="w").pack(side="left", padx=4)

'''

    # 替换
    content = content[:alt_start] + new_alt_view + content[alt_end:]

# 写回文件
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] 文件已更新")

# 语法检查
r = subprocess.run([sys.executable, '-m', 'py_compile', path], capture_output=True, text=True)
if r.returncode == 0:
    print("[SYNTAX] OK - 语法检查通过")
else:
    print("[SYNTAX ERROR]")
    print(r.stderr[:800])
    sys.exit(1)

print("\n[SUCCESS] 修复完成！")
print("1. _run_ai_audit: audit_indices 已正确定义在方法内")
print("2. _refresh_alt_view: 显示逻辑已修正，不再显示数字2")
print("\n请重新打包 EXE：")
print('  cd "E:\\zpp011_dev\\模块化脚本"')
print('  python build_exe.py')
