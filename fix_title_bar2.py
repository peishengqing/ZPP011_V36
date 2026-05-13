# -*- coding: utf-8 -*-
"""Add title bar - handle \r\r\n line endings"""

inv_path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(inv_path, 'rb') as f:
    raw = f.read()

# Normalize line endings first: \r\r\n -> \n
content = raw.replace(b'\r\r\n', b'\n').decode('utf-8')

old_text = '''    def _build_ui(self):
        """构建界面布局"""
        # ── 顶部操作栏 ───────────────────────────────
        top_frame = tk.Frame(self, bg='#f5f5f5', pady=10)
        top_frame.pack(fill='x', padx=10)'''

new_text = '''    def _build_ui(self):
        """构建界面布局"""
        # ── 顶部标题栏 ───────────────────────────────
        header = tk.Frame(self, bg='#1a365d', height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="📦", font=("Segoe UI Emoji", 22),
                 bg='#1a365d').pack(side="left", padx=(16, 8))
        title_frame = tk.Frame(header, bg='#1a365d')
        title_frame.pack(side="left")
        tk.Label(title_frame, text="云南达利ZPP011 库存流水管理",
                 font=("Microsoft YaHei", 13, "bold"), fg='#ffffff',
                 bg='#1a365d').pack(anchor="w")
        tk.Label(title_frame, text="制作人：裴盛清  |  v36.1",
                 font=("Microsoft YaHei", 8), fg='#cae8ff',
                 bg='#1a365d').pack(anchor="w")

        # ── 顶部操作栏 ───────────────────────────────
        top_frame = tk.Frame(self, bg='#f5f5f5')
        top_frame.pack(fill='x', padx=10, pady=(8, 0))'''

if old_text in content:
    content = content.replace(old_text, new_text)
    print("SUCCESS: Title bar added!")
else:
    print("FAILED after normalization")
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    idx = content.find('def _build_ui')
    print(content[idx:idx+300])

# Write back with normal CRLF
with open(inv_path, 'w', encoding='utf-8') as f:
    f.write(content)
