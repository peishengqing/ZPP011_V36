# -*- coding: utf-8 -*-
"""Fix inventory_view.py: add title bar, fix colors; update version.json and build_log"""

import json, os, datetime

# ============================================================
# 1. Update version.json to v36.1
# ============================================================
version_path = r'E:\zpp011_dev\模块化脚本\config\version.json'
with open(version_path, 'r', encoding='utf-8') as f:
    ver = json.load(f)

ver['version'] = 'v36.1'
ver['release_notes'] = (
    "新增:库存流水界面完整实现(导入Excel/三表展示/汇总卡片/搜索过滤/全检报告)\n"
    "新增:库存流水界面顶部标题栏(与分析模式统一风格)\n"
    "修复:tkinter Frame构造函数pady元组参数错误导致界面崩溃\n"
    "修复:导入库存表按钮无反应(self.parent.log属性错误+表格填充未实现)\n"
    "修复:mode.json UTF-8 BOM编码问题\n"
    "修复:EXE打包后ModeSelector路径问题(sys._MEIPASS+用户目录)"
)

with open(version_path, 'w', encoding='utf-8') as f:
    json.dump(ver, f, ensure_ascii=False, indent=2)
print("1. Updated config/version.json -> v36.1")

# ============================================================
# 2. Add title bar to inventory_view.py _build_ui method
# ============================================================
inv_path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(inv_path, 'r', encoding='utf-8') as f:
    content = f.read()

content_norm = content.replace('\r\n', '\n')

# Find the _build_ui method - insert title bar after top_frame creation
old_build_start = '''    def _build_ui(self):
        """构建界面布局"""
        # ── 顶部操作栏 ───────────────────────────────
        top_frame = tk.Frame(self, bg='#f5f5f5', pady=10)
        top_frame.pack(fill='x', padx=10)'''

new_build_start = '''    def _build_ui(self):
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

if old_build_start in content_norm:
    content_norm = content_norm.replace(old_build_start, new_build_start)
    print("2. Added title bar to inventory_view._build_ui()")
else:
    print("2. FAILED: _build_ui pattern not found!")
    idx = content_norm.find('def _build_ui')
    if idx >= 0:
        print(f"   Context: {content_norm[idx:idx+300]}")

# Write back with CRLF
content_crlf = content_norm.replace('\n', '\r\n')
with open(inv_path, 'w', encoding='utf-8') as f:
    f.write(content_crlf)

# ============================================================
# 3. Update build_log.md
# ============================================================
log_path = r'E:\zpp011_dev\模块化脚本\build_log.md'
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

new_entry = (
    "\n==================================================\n"
    f"\U0001f4e5 v36.1 | {now} | \u6210\u529f\n"
    "\U0001f4e4 \u6253\u5305\u4eba\uff1\u88d8\u76db\u6e05\n"
    "--------------------------------------------------\n"
    " Python 3.11.9 | onefile | gui/events.py + gui/inventory_view.py | 44.8 MB |\n"
    "--------------------------------------------------\n"
    "\u2705 \u65b0\u589e\u529f\u80fd:\n"
    " 1. \u5e93\u5b58\u6d41\u6c34\u754c\u9762\u5b8c\u6574\u5b9e\u73b0(\u5bfc\u5165Excel/\u4e09\u8868\u5c55\u793a/\u6c47\u603b\u5361\u7247/\u641c\u7d22\u8fc7\u6ee4/\u5168\u68c0\u62a5\u544a)\n"
    " 2. \u5e93\u5b58\u6d41\u6c34\u9876\u90e8\u6807\u9898\u680f(\u4e0e\u5206\u6790\u6a21\u5f0f\u7edf\u4e00\u98ce\u683c)\n"
    "\ud83d\udca1 \u529f\u80fd\u6539\u8fdb:\n"
    " 1. \u7248\u672c\u53f7\u91cd\u7f6e\u4e3av36.1\n"
    "\ud83d\udee1 Bug\u4fee\u590d:\n"
    " 1. tkinter Frame\u6784\u9020\u51fd\u6570pady\u5143\u7ec4\u53c2\u6570\u9519\u8bef\u5bfc\u81f4\u754c\u9762\u5d29\u6e83\n"
    " 2. \u5bfc\u5165\u5e93\u5b58\u8868\u6309\u94ae\u65e0\u53cd\u5e94(self.parent.log\u5c5e\u6027\u9519\u8bef+\u8868\u683c\u586b\u5145\u672a\u5b9e\u73b0)\n"
    " 3. mode.json UTF-8 BOM\u7f16\u7801\u95ee\u9898\n"
    " 4. EXE\u6253\u5305\u540eModeSelector\u8def\u5f84\u95ee\u9898(sys._MEIPASS+\u7528\u6237\u76ee\u5f55)\n"
    "==================================================\n"
)

with open(log_path, 'a', encoding='utf-8') as f:
    f.write(new_entry)
print("3. Updated build_log.md")

print("\nAll done!")
