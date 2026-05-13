import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = """        # 创建中间容器（隔离 pack/grid 混用）
        inner = tk.Frame(frame, bg='#f5f5f5')
        inner.pack(fill='both', expand=True)

        # 创建 Treeview
        tree = ttk.Treeview(inner, show='headings', height=10)

        # 添加滚动条（垂直）
        vsb = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        # grid 布局在 inner 容器内，不与 frame 的 pack 冲突
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)"""

new = """        # 创建中间容器（隔离 pack/grid 混用）
        inner = tk.Frame(frame)
        inner.pack(fill='both', expand=True)

        # 创建 Treeview（不设固定 height，让 grid weight 控制大小）
        tree = ttk.Treeview(inner, show='headings')

        # 垂直滚动条 + 水平滚动条
        vsb = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(inner, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # grid 布局：tree 占满，滚动条紧贴右侧和底部
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        inner.grid_rowconfigure(0, weight=1)
        inner.grid_columnconfigure(0, weight=1)"""

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('FIXED: removed fixed height, added horizontal scrollbar too')
else:
    print('Pattern not found!')
