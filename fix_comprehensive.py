# -*- coding: utf-8 -*-
"""Comprehensive fix for inventory_view.py"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

inv_path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(inv_path, 'rb') as f:
    raw = f.read()

content = raw.decode('utf-8')
crlf = raw.count(b'\r\n')
lf_only = raw.count(b'\n') - crlf
print(f"File size: {len(raw)} bytes, CRLF={crlf}, LF-only={lf_only}")

# Fix 1: pady=(0, 5) in Frame constructor
old1 = "self.summary_frame = tk.Frame(self, bg='#f5f5f5', pady=(0, 5))\n        self.summary_frame.pack(fill='x', padx=10)"
new1 = "self.summary_frame = tk.Frame(self, bg='#f5f5f5')\n        self.summary_frame.pack(fill='x', padx=10, pady=(0, 5))"
if old1 in content:
    content = content.replace(old1, new1)
    print("Fix 1: pady moved to pack()")
else:
    print("Fix 1: pady pattern not found (may already be fixed)")

# Fix 2: Add title bar
old2 = '    def _build_ui(self):\n        """\u6784\u5efa\u754c\u9762\u5e03\u5c40"""\n        # \u2500\u2500 \u9876\u90e8\u64cd\u4f5c\u680f \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n        top_frame = tk.Frame(self, bg=\'#f5f5f5\', pady=10)\n        top_frame.pack(fill=\'x\', padx=10)'

new2 = '''    def _build_ui(self):
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

if old2 in content:
    content = content.replace(old2, new2)
    print("Fix 2: Title bar added")
else:
    print("Fix 2: title bar pattern not found")

# Fix 3: import storage
if 'import storage' not in content:
    marker = 'from inventory_loader import load_inventory_snapshot'
    if marker in content:
        idx = content.find(marker)
        end_idx = content.find('\n', idx) + 1
        content = content[:end_idx] + 'import storage\n' + content[end_idx:]
        print("Fix 3: Added import storage")
else:
    print("Fix 3: import storage already present")

# Write back
with open(inv_path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

# Verify
print("\nVerifying...")
with open(inv_path, 'r', encoding='utf-8') as f:
    v = f.read()
print(f"  import storage: {'OK' if 'import storage' in v else 'FAIL'}")
has_title = '\u4e91\u5357\u8fbe\u5229ZPP011 \u5e93\u5b58\u6d41\u6c34\u7ba1\u7406' in v
print(f'  title bar: {"OK" if has_title else "FAIL"}')
print(f"  no parent.log: {'OK' if 'self.parent.log' not in v else 'FAIL'}")
pady_ok = "pady=(0, 5))" not in v
print(f'  pady fix: {"OK" if pady_ok else "FAIL (still has tuple in Frame)"}')
