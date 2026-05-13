# -*- coding: utf-8 -*-
"""Fix: add missing 'import storage' to inventory_view.py, and other fixes"""

# ============================================================
# 1. Fix storage import in inventory_view.py
# ============================================================
inv_path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(inv_path, 'r', encoding='utf-8') as f:
    content = f.read()

content_norm = content.replace('\r\n', '\n')

# Check current imports
import_section_start = content_norm.find('import os\nimport sys')
if import_section_start >= 0:
    import_section = content_norm[import_section_start:import_section_start+300]
    print("=== Current imports ===")
    print(import_section)

# Add import storage after the existing imports
old_imports = '''# 导入数据处理模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from inventory_loader import load_inventory_snapshot, merge_inventory_records, calc_expiry_warning'''

new_imports = '''# 导入数据处理模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from inventory_loader import load_inventory_snapshot, merge_inventory_records, calc_expiry_warning
import storage'''

if old_imports in content_norm:
    content_norm = content_norm.replace(old_imports, new_imports)
    print("\n1. Added 'import storage' to inventory_view.py")
else:
    print("\n1. FAILED: import pattern not found, trying alternative...")
    # Try finding just the from line
    if 'from inventory_loader import' in content_norm:
        idx = content_norm.find('from inventory_loader import')
        end_line = content_norm.find('\n', idx)
        insert_pos = end_line + 1
        content_norm = content_norm[:insert_pos] + 'import storage\n' + content_norm[insert_pos:]
        print("   Inserted 'import storage' after inventory_loader import")

# ============================================================
# 2. Add title bar to _build_ui
# ============================================================
old_build = '''    def _build_ui(self):
        """构建界面布局"""
        # ── 顶部操作栏 ───────────────────────────────
        top_frame = tk.Frame(self, bg='#f5f5f5', pady=10)
        top_frame.pack(fill='x', padx=10)'''

new_build = '''    def _build_ui(self):
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

if old_build in content_norm:
    content_norm = content_norm.replace(old_build, new_build)
    print("2. Added title bar to inventory_view._build_ui()")
else:
    # Check if already has title bar
    if '云南达利ZPP011 库存流水管理' in content_norm:
        print("2. Title bar already present, skipping")
    else:
        print("2. WARNING: Could not find _build_ui pattern for title bar")
        idx = content_norm.find('def _build_ui')
        if idx >= 0:
            print(f"   Context: {repr(content_norm[idx:idx+250])}")

# Write back with CRLF
content_crlf = content_norm.replace('\n', '\r\n')
with open(inv_path, 'w', encoding='utf-8') as f:
    f.write(content_crlf)

print("\nDone with inventory_view.py fixes!")
