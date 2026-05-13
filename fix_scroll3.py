import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = """        # 创建中间容器（隔离 pack/grid 混用）
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

new = """        # 创建 Treeview
        tree = ttk.Treeview(frame, show='headings')

        # 垂直滚动条
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        # 用 pack：tree 先填充剩余空间，滚动条贴右侧
        vsb.pack(side='right', fill='y')
        tree.pack(side='left', fill='both', expand=True)"""

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('FIXED: pure pack layout - scrollbar right, tree fills rest')
else:
    print('Pattern not found!')
