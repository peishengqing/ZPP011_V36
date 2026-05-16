# -*- coding: utf-8 -*-
"""
库存流水管理界面
包含：库存快照、入库流水、过期预警三大区域
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys

# 导入数据处理模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from inventory_loader import load_inventory_snapshot, merge_inventory_records, calc_expiry_warning
import storage


class InventoryView(tk.Frame):
    """库存流水管理主界面"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.configure(bg='#f5f5f5')

        # 数据存储
        self.inventory_df = None  # 库存快照
        self.inflow_df = None     # 入库流水
        self.warning_df = None    # 过期预警
        
        # 保存三个表格的引用
        self.inventory_tree = None
        self.inflow_tree = None
        self.warning_tree = None

        # 汇总卡片数值标签引用
        self.summary_total_lbl = None
        self.summary_expired_lbl = None
        self.summary_soon_lbl = None
        self.summary_inflow_lbl = None

        self._build_ui()
        
        # 为三个表格设置排序功能
        self._setup_inventory_sorting()

    def _build_ui(self):
        """构建界面布局（含全局滚动条）"""
        # ── 顶部标题栏（固定不滚） ───────────────────
        header = tk.Frame(self, bg='#1a365d', height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="📦", font=("Segoe UI Emoji", 22),
                 bg='#1a365d').pack(side="left", padx=(16, 8))
        title_frame = tk.Frame(header, bg='#1a365d')
        title_frame.pack(side="left")
        tk.Label(title_frame, text="云南路居基地库存流水管理系统",
                 font=("Microsoft YaHei", 13, "bold"), fg='#ffffff',
                 bg='#1a365d').pack(anchor="w")
        tk.Label(title_frame, text="制作人：裴盛清|v1.0",
                 font=("Microsoft YaHei", 8), fg='#cae8ff',
                 bg='#1a365d').pack(anchor="w")

        # ── 全局滚动区域（Canvas + Scrollbar） ──────
        canvas_container = tk.Frame(self, bg='#f5f5f5')
        canvas_container.pack(fill='both', expand=True)

        self._global_canvas = tk.Canvas(canvas_container, bg='#f5f5f5',
                                         highlightthickness=0)
        global_vsb = ttk.Scrollbar(canvas_container, orient="vertical",
                                   command=self._global_canvas.yview)
        self._global_canvas.configure(yscrollcommand=global_vsb.set)

        global_vsb.pack(side='right', fill='y')
        self._global_canvas.pack(side='left', fill='both', expand=True)

        # 内部可滚动容器
        scroll_frame = tk.Frame(self._global_canvas, bg='#f5f5f5')
        self._canvas_window = self._global_canvas.create_window(
            (0, 0), window=scroll_frame, anchor='nw')

        def _configure_scroll_region(event):
            self._global_canvas.configure(scrollregion=self._global_canvas.bbox('all'))
            # 让内部框架宽度跟随 Canvas 宽度
            self._global_canvas.itemconfig(self._canvas_window, width=event.width)

        self._global_canvas.bind('<Configure>', _configure_scroll_region)
        scroll_frame.bind('<Configure>', lambda e: self._global_canvas.configure(
            scrollregion=self._global_canvas.bbox('all')))

        # 鼠标滚轮绑定到全局 Canvas
        def _on_mousewheel(event):
            self._global_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._global_canvas.bind_all('<MouseWheel>', _on_mousewheel)

        # ── 以下控件全部放入 scroll_frame ────────────

        # ── 顶部操作栏 ───────────────────────────────
        top_frame = tk.Frame(scroll_frame, bg='#f5f5f5')
        top_frame.pack(fill='x', padx=10, pady=(8, 0))

        tk.Button(top_frame, text="📥 导入库存表", command=self._import_inventory,
                  bg='#3498db', fg='white', font=('Microsoft YaHei', 10),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(top_frame, text="🔄 刷新数据", command=self._refresh_data,
                  bg='#2ecc71', fg='white', font=('Microsoft YaHei', 10),
                  padx=15, pady=5).pack(side='left', padx=5)

        ttk.Separator(top_frame, orient='vertical').pack(side='left', padx=8, fill='y')

        self.check_all_btn = tk.Button(top_frame, text="🔍 库存全检", command=self._on_check_all,
                  bg='#e67e22', fg='white', font=('Microsoft YaHei', 10),
                  padx=15, pady=5)
        self.check_all_btn.pack(side='left', padx=5)

        # ── 汇总卡片区域 ───────────────────────────────
        self.summary_frame = tk.Frame(scroll_frame, bg='#f5f5f5')
        self.summary_frame.pack(fill='x', padx=10, pady=(0, 5))

        # 四个卡片配置: (标题, 背景色, 数字颜色, 单位)
        cards = [
            ('📦 总品种数', '#ffffff', '#333333', '种'),
            ('🔴 已过期', '#ffe0e0', '#cc0000', '项'),
            ('🟡 即将过期', '#fff0d0', '#cc6600', '项'),
            ('📥 本月入库批次', '#e0e8ff', '#3366cc', '批'),
        ]

        lbl_refs = [None, None, None, None]
        for i, (title, bg, fg, unit) in enumerate(cards):
            card = tk.Frame(self.summary_frame, bg=bg, relief='solid', bd=1)
            card.grid(row=0, column=i, sticky='nsew', padx=5)
            tk.Label(card, text=title, font=('Microsoft YaHei', 8),
                     bg=bg, fg='#888888').pack(pady=(6, 0))
            val_lbl = tk.Label(card, text='--', font=('Microsoft YaHei', 18, 'bold'),
                               bg=bg, fg=fg)
            val_lbl.pack()
            tk.Label(card, text=unit, font=('Microsoft YaHei', 8),
                     bg=bg, fg='#888888').pack(pady=(0, 6))
            lbl_refs[i] = val_lbl

        self.summary_total_lbl = lbl_refs[0]
        self.summary_expired_lbl = lbl_refs[1]
        self.summary_soon_lbl = lbl_refs[2]
        self.summary_inflow_lbl = lbl_refs[3]

        # 设置 grid 列权重（4列均匀分配）
        for i in range(4):
            self.summary_frame.columnconfigure(i, weight=1)

        # ── 库存快照区域（含搜索栏） ──────────────────
        self.inventory_tree = self._create_section(
            scroll_frame, "📦 库存快照", self._build_inventory_table,
            before_tree=self._build_search_bar)

        # ── 入库流水区域 ───────────────────────────────
        self.inflow_tree = self._create_section(scroll_frame, "📋 入库流水", self._build_inflow_table)

        # ── 过期预警区域 ───────────────────────────────
        self.warning_tree = self._create_section(scroll_frame, "⚠️ 过期预警", self._build_warning_table)

        # ── 全局快捷键 ───────────────────────────────
        self.bind_all('<Control-f>', lambda e: self.search_entry.focus_set())

    def _create_section(self, parent, title, build_func, before_tree=None):
        """创建通用区域框架"""
        frame = tk.LabelFrame(parent, text=title, font=('Microsoft YaHei', 11, 'bold'),
                             bg='#f5f5f5', padx=10, pady=5)
        frame.pack(fill='both', expand=True, padx=10, pady=5)

        # 在Tree之前插入自定义控件（如搜索栏）
        if before_tree:
            before_tree(frame)

        # 创建 Treeview
        tree = ttk.Treeview(frame, show='headings')

        # 垂直滚动条
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        # 用 pack：tree 先填充剩余空间，滚动条贴右侧
        vsb.pack(side='right', fill='y')
        tree.pack(side='left', fill='both', expand=True)

        # 调用特定区域的构建函数
        build_func(tree)

        return tree

    def _build_search_bar(self, parent_frame):
        """构建搜索栏（插入到库存快照区域的Tree上方）"""
        search_row = tk.Frame(parent_frame, bg='#f5f5f5')
        search_row.pack(side='top', fill='x', pady=(0, 5))

        placeholder = '🔍 搜索物料编码或名称...'
        self._search_var = tk.StringVar(value=placeholder)
        self.search_entry = tk.Entry(
            search_row, textvariable=self._search_var,
            font=('Microsoft YaHei', 9), width=22,
            fg='#999999', relief='solid', bd=1)
        self.search_entry.pack(side='left')

        # 占位文字：FocusIn 清空 / FocusOut 恢复
        def _focus_in(event):
            if self.search_entry.get() == placeholder:
                self.search_entry.delete(0, 'end')
                self.search_entry.configure(fg='#333333')

        def _focus_out(event):
            if not self.search_entry.get().strip():
                self.search_entry.insert(0, placeholder)
                self.search_entry.configure(fg='#999999')

        self.search_entry.bind('<FocusIn>', _focus_in)
        self.search_entry.bind('<FocusOut>', _focus_out)

        # 搜索图标按钮（暂不绑定命令）
        tk.Button(search_row, text='🔎', font=('', 10),
                  relief='flat', bg='#f5f5f5', command=lambda: None
                  ).pack(side='left', padx=(5, 0))

        # 键盘释放事件绑定
        self.search_entry.bind('<KeyRelease>', self._on_search_key)

    def _on_search_key(self, event):
        """搜索框键盘事件回调 - 实时过滤库存快照表格"""
        keyword = self.search_entry.get().strip()
        placeholder = '🔍 搜索物料编码或名称...'
        if keyword == placeholder:
            keyword = ''

        tree = self.inventory_tree
        children = tree.get_children()

        # 输入为空 → 恢复全部行
        if not keyword:
            for item in children:
                tree.reattach(item, '', 'end')
            return

        # 非空 → 逐行过滤
        keyword_lower = keyword.lower()
        matched_any = False
        for item in children:
            code = str(tree.set(item, '物料编码') or '').strip()
            name = str(tree.set(item, '物料名称') or '').strip()
            if keyword_lower in code.lower() or keyword_lower in name.lower():
                tree.reattach(item, '', 'end')
                matched_any = True
            else:
                tree.detach(item)

        # 无匹配结果提示
        if not matched_any:
            tree.delete(*tree.get_children())
            tree.insert('', 'end', values=('', '未找到匹配的物料', '', '', ''),
                        tags=('no_result',))

    def _build_inventory_table(self, tree):
        """构建库存快照表格"""
        columns = ['物料编码', '物料名称', '现存量', '生产日期', '保质期']
        tree['columns'] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor='center')

    def _build_inflow_table(self, tree):
        """构建入库流水表格"""
        columns = ['入库日期', '物料编码', '物料名称', '入库类型', '数量', '单位', '金额']
        tree['columns'] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor='center')

    def _build_warning_table(self, tree):
        """构建过期预警表格"""
        columns = ['物料编码', '物料名称', '剩余天数', '过期状态', '保质期']
        tree['columns'] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor='center')

    def _import_inventory(self):
        """导入库存表"""
        filepath = filedialog.askopenfilename(
            title="选择库存表",
            filetypes=[("Excel文件", "*.xlsx *.xls"), ("所有文件", "*.*")]
        )
        if not filepath:
            return

        try:
            # 读取库存快照
            self.inventory_df = load_inventory_snapshot(filepath)

            # 读取入库流水
            self.inflow_df = merge_inventory_records(filepath)

            # 计算过期预警
            self.warning_df = calc_expiry_warning(self.inventory_df.copy())

            # 刷新表格显示
            self._refresh_data()
            self._update_summary()

            messagebox.showinfo("导入成功", f"库存数据导入完成！\n库存记录: {len(self.inventory_df)} 条\n入库记录: {len(self.inflow_df)} 条")

        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def _refresh_data(self):
        """刷新表格显示"""
        # 刷新库存快照表格
        if self.inventory_df is not None and self.inventory_tree is not None:
            self.inventory_tree.delete(*self.inventory_tree.get_children())
            for _, row in self.inventory_df.iterrows():
                values = []
                for col in ['物料编码', '物料名称', '现存量', '生产日期', '保质期']:
                    val = row.get(col, '')
                    values.append(str(val) if val is not None else '')
                self.inventory_tree.insert('', 'end', values=values)

        # 刷新入库流水表格
        if self.inflow_df is not None and self.inflow_tree is not None:
            self.inflow_tree.delete(*self.inflow_tree.get_children())
            for _, row in self.inflow_df.iterrows():
                values = []
                for col in ['入库日期', '物料编码', '物料名称', '入库类型', '数量', '单位', '金额']:
                    val = row.get(col, '')
                    values.append(str(val) if val is not None else '')
                self.inflow_tree.insert('', 'end', values=values)

        # 刷新过期预警表格
        if self.warning_df is not None and self.warning_tree is not None:
            self.warning_tree.delete(*self.warning_tree.get_children())
            for _, row in self.warning_df.iterrows():
                values = []
                for col in ['物料编码', '物料名称', '剩余天数', '过期状态', '保质期']:
                    val = row.get(col, '')
                    values.append(str(val) if val is not None else '')
                self.warning_tree.insert('', 'end', values=values)

    def _update_summary(self):
        """更新汇总卡片数据"""
        # 数据为空时恢复默认值
        if self.inventory_df is None or self.inventory_df.empty:
            self.summary_total_lbl.configure(text='--')
            self.summary_expired_lbl.configure(text='--')
            self.summary_soon_lbl.configure(text='--')
            self.summary_inflow_lbl.configure(text='--')
            return

        # 总品种数
        total = len(self.inventory_df)
        self.summary_total_lbl.configure(text=str(total))

        # 已过期 / 即将过期
        from inventory_loader import calc_expiry_warning
        warning_df = calc_expiry_warning(self.inventory_df.copy())
        expired_count = int(warning_df[warning_df['过期状态'] == '已过期'].shape[0])
        soon_count = int(warning_df[warning_df['过期状态'] == '即将过期(30天内)'].shape[0])
        self.summary_expired_lbl.configure(text=str(expired_count))
        self.summary_soon_lbl.configure(text=str(soon_count))

        # 本月入库批次
        if self.inflow_df is not None and not self.inflow_df.empty:
            try:
                import pandas as pd
                date_col = '入库日期'
                # 尝试推断日期列
                for col in self.inflow_df.columns:
                    if any(k in str(col) for k in ['日期', 'date', 'Date', '时间']):
                        date_col = col
                        break
                self.inflow_df['_date_tmp'] = pd.to_datetime(self.inflow_df[date_col], errors='coerce')
                now_year, now_month = pd.Timestamp.now().year, pd.Timestamp.now().month
                monthly_count = int(self.inflow_df[
                    (self.inflow_df['_date_tmp'].dt.year == now_year) &
                    (self.inflow_df['_date_tmp'].dt.month == now_month)
                ].shape[0])
                self.inflow_df.drop(columns=['_date_tmp'], inplace=True)
                self.summary_inflow_lbl.configure(text=str(monthly_count))
            except Exception:
                self.summary_inflow_lbl.configure(text='--')
        else:
            self.summary_inflow_lbl.configure(text='--')

        # 入库流水和过期预警表格由 _refresh_data() 统一处理

    def _setup_inventory_sorting(self):
        """
        为库存表格设置多列排序功能。
        普通点击：切换该列升降序
        Ctrl+点击：追加/移除该列的排序条件
        """
        from gui.tree_utils import bind_multi_sort

        # 初始化排序状态存储
        self._sort_states = {}

        # 库存快照
        inv_cols = ["物料编码", "物料名称", "现存量", "生产日期", "保质期"]
        inv_key = "inventory"
        self._sort_states[inv_key] = {}
        bind_multi_sort(self.inventory_tree, lambda: self._sort_states[inv_key], inv_cols)

        # 入库流水
        inflow_cols = ["入库日期", "物料编码", "物料名称", "入库类型", "数量", "单位", "金额"]
        inflow_key = "inflow"
        self._sort_states[inflow_key] = {}
        bind_multi_sort(self.inflow_tree, lambda: self._sort_states[inflow_key], inflow_cols)

        # 过期预警
        warn_cols = ["物料编码", "物料名称", "剩余天数", "过期状态", "保质期"]
        warn_key = "warning"
        self._sort_states[warn_key] = {}
        bind_multi_sort(self.warning_tree, lambda: self._sort_states[warn_key], warn_cols)

    def _on_check_all(self):
        """库存全检 - 弹出健康度报告窗口"""
        # 检查数据源
        if self.inventory_df is None or self.inventory_df.empty:
            messagebox.showwarning("⚠️ 提示", "请先导入库存表")
            return

        # 计算预警数据
        warning_df = calc_expiry_warning(self.inventory_df.copy())

        # 筛选各类数据
        expired_df = warning_df[warning_df['过期状态'] == '已过期'].copy()
        expiring_df = warning_df[warning_df['过期状态'] == '即将过期(30天内)'].copy()

        # 筛选低库存物资：现存量 <= 5
        low_stock_df = self.inventory_df[self.inventory_df['现存量'] <= 5].copy()

        # 创建弹窗
        win = tk.Toplevel(self)
        win.title("📋 库存健康度全检报告")
        win.geometry("550x420")
        win.resizable(True, True)
        win.transient(self)
        win.grab_set()

        # 居中显示
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        ww, wh = 550, 420
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        # 主容器
        main_frame = tk.Frame(win, bg='#f8f9fa', padx=15, pady=10)
        main_frame.pack(fill='both', expand=True)

        # 标题 - 显示数据完整性
        total_count = len(self.inventory_df)
        title_label = tk.Label(main_frame, text=f"✅ 数据完整性：共加载 {total_count} 条物资",
                               font=('Microsoft YaHei', 12, 'bold'), bg='#f8f9fa',
                               fg='#2c3e50')
        title_label.pack(anchor='w', pady=(5, 10))

        # 三个预警区域
        expired_frame = ttk.LabelFrame(main_frame, text=f"🔴 已过期 ({len(expired_df)}项)")
        expired_frame.pack(fill='both', expand=True, padx=5, pady=5)
        expired_text = tk.Text(expired_frame, height=4, font=('Consolas', 9),
                               bg='#fff5f5', relief='flat', state='disabled')
        expired_text.pack(fill='both', expand=True, padx=8, pady=5)

        expiring_frame = ttk.LabelFrame(main_frame, text=f"🟡 即将过期-30天内 ({len(expiring_df)}项)")
        expiring_frame.pack(fill='both', expand=True, padx=5, pady=5)
        expiring_text = tk.Text(expiring_frame, height=4, font=('Consolas', 9),
                                 bg='#fffef0', relief='flat', state='disabled')
        expiring_text.pack(fill='both', expand=True, padx=8, pady=5)

        low_stock_frame = ttk.LabelFrame(main_frame, text=f"⚠️ 低库存预警 ({len(low_stock_df)}项)")
        low_stock_frame.pack(fill='both', expand=True, padx=5, pady=5)
        low_stock_text = tk.Text(low_stock_frame, height=4, font=('Consolas', 9),
                                  bg='#f0f8ff', relief='flat', state='disabled')
        low_stock_text.pack(fill='both', expand=True, padx=8, pady=5)

        # 底部按钮栏
        btn_frame = tk.Frame(main_frame, bg='#f8f9fa')
        btn_frame.pack(fill='x', pady=(10, 0))

        tk.Button(btn_frame, text="导出异常清单", font=('Microsoft YaHei', 10),
                  bg='#3498db', fg='white', relief='flat', padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(btn_frame, text="关闭", font=('Microsoft YaHei', 10),
                  bg='#95a5a6', fg='white', relief='flat', padx=15, pady=5,
                  command=win.destroy).pack(side='right', padx=5)

        # ── 填充数据 ─────────────────────────────────────────
        def _make_fold_handler(text_widget, all_rows, get_line_func):
            """创建折叠/展开处理器"""
            expanded = [False]

            def _on_click(event):
                index = text_widget.index(f"@{event.x},{event.y}")
                if not index:
                    return
                tags = text_widget.tag_names(index)
                if 'fold' in tags:
                    expanded[0] = not expanded[0]
                    text_widget.configure(state='normal')
                    text_widget.delete('1.0', 'end')
                    _fill_text(text_widget, all_rows, not expanded[0], get_line_func)
                    text_widget.configure(state='disabled')

            return _on_click

        def _fill_text(text_widget, rows, collapsed=False, get_line_func=None):
            """填充Text控件，支持折叠"""
            text_widget.delete('1.0', 'end')
            if rows.empty:
                text_widget.insert('end', '（暂无数据）')
                return

            display_rows = rows.head(3).to_dict('records')
            total = len(rows)

            for i, row in enumerate(display_rows):
                if get_line_func:
                    line = get_line_func(row)
                else:
                    code = str(row.get('物料编码', ''))
                    name = str(row.get('物料名称', ''))
                    stock = str(row.get('现存量', ''))
                    status = str(row.get('过期状态', ''))
                    days = str(row.get('剩余天数', ''))
                    if status == '已过期':
                        status_disp = f"已过期({days}天)"
                    else:
                        status_disp = f"剩余{days}天"
                    line = f"{code}  {name}  现存量:{stock}  {status_disp}"
                text_widget.insert('end', line + '\n')

            if collapsed and total > 3:
                fold_text = f"▼ 展开更多（共{total}项）"
                text_widget.insert('end', '\n' + fold_text)
                start = text_widget.index('end-1c linestart')
                end = text_widget.index('end-1c')
                text_widget.tag_add('fold', start, end)
                text_widget.tag_config('fold', foreground='#3498db', underline=True)
                text_widget.bind('<Button-1>', _make_fold_handler(text_widget, rows, get_line_func))

        _fill_text(expired_text, expired_df, collapsed=True)
        _fill_text(expiring_text, expiring_df, collapsed=True)

        def _get_low_stock_line(row):
            code = str(row.get('物料编码', ''))
            name = str(row.get('物料名称', ''))
            stock = str(row.get('现存量', ''))
            return f"{code}  {name}  现存量:{stock}  低于安全线"

        _fill_text(low_stock_text, low_stock_df, collapsed=True, get_line_func=_get_low_stock_line)