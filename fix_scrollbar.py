import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'E:\zpp011_dev\模块化脚本\gui\inventory_view.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_tree = """        # 创建 Treeview
        tree = ttk.Treeview(frame, show='headings', height=8)

        # 添加滚动条
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')"""

new_tree = """        # 创建 Treeview
        tree = ttk.Treeview(frame, show='headings', height=10)

        # 添加滚动条（垂直）
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        # 用 grid 布局确保滚动条始终紧贴 Treeview 右侧
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)"""

if old_tree in content:
    content = content.replace(old_tree, new_tree)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('FIXED: Treeview now uses grid layout with proper scrollbar')
else:
    print('Pattern not found!')
    # debug
    idx = content.find('创建 Treeview')
    if idx >= 0:
        print(content[idx:idx+300])
