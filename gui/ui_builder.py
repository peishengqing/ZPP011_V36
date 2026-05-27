import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
from widgets import C, STEPS, card, btn, label, entry
from tkcalendar import DateEntry
from domain.alt_material import alt_manager
import os
import json
import sys
import pandas as pd

# 默认列宽配置
DEFAULT_COL_WIDTHS = {
    'idx': 35, 'excel_row': 60, 'code': 70, 'name': 100, 'factory': 70,
    'order_date': 70, 'admin': 70, 'quota': 50, 'actual': 50, 'dev_rate': 55,
    'is_alt': 50, 'status': 55, 'remark': 80, 'batch_remark': 90,
    'audit_result': 80, 'AI建议': 120, 'audit_status': 60, 'audit_source': 70,
    'deviation_amount': 90, 'order_no': 100
}
# 列宽配置文件路径
COLUMN_WIDTHS_FILE = os.path.join(os.path.expanduser('~'), '.zpp011_audit', 'column_widths.json')


def build_ui(app_instance):
    """构建完整 GUI 界面（v36 抽取）"""
    _build_ui(app_instance)


def _build_ui(self):
        # 顶部标题栏
        header = tk.Frame(self.root, bg=C['header_bg'], height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Frame(header, bg=C['accent'], width=4).pack(side="left", fill="y", padx=(0, 16))
        tk.Label(header, text="🏭", font=("Segoe UI Emoji", 26),
                 bg=C['header_bg']).pack(side="left", padx=(16, 8))
        title_frame = tk.Frame(header, bg=C['header_bg'])
        title_frame.pack(side="left")
        # 从 utils.version_history 动态读取版本号（统一来源）
        from utils.version_history import get_version_display, get_current_version
        _ver = get_current_version()
        tk.Label(title_frame, text=f"云南达利ZPP011生产偏差分析器 {_ver}",
                 font=("Microsoft YaHei", 14, "bold"), fg='#ffffff',
                 bg=C['header_bg']).pack(anchor="w")
        tk.Label(title_frame, text=f"制作人：裴盛清  |  {_ver}",
                 font=("Microsoft YaHei", 9), fg='#cae8ff',
                 bg=C['header_bg']).pack(anchor="w")

        main = tk.Frame(self.root, bg=C['bg'])
        main.pack(fill="both", expand=True, padx=16, pady=(12, 8))

        left = tk.Frame(main, bg=C['bg'], width=360)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        # 文件卡片
        fc = card(left)
        fc.pack(fill="x", pady=(0, 10))
        tk.Frame(fc, bg=C['accent'], height=3).pack(fill="x")
        tk.Label(fc, text="  📁 文件选择", font=("Microsoft YaHei", 10, "bold"),
                 fg=C['text'], bg=C['surface'], anchor="w").pack(fill="x", padx=12, pady=(10, 6))
        fr_in = tk.Frame(fc, bg=C['surface'])
        fr_in.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(fr_in, text="输入文件", font=("Microsoft YaHei", 9),
                 fg=C['text_dim'], bg=C['surface'], width=8, anchor="w").pack(side="left")
        entry(fr_in, self.input_file).pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn(fr_in, "浏览", self._select_input, "#d0d7de", C['text'],
                  ("Microsoft YaHei", 9), width=6).pack(side="right")

        fr_out = tk.Frame(fc, bg=C['surface'])
        fr_out.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(fr_out, text="输出目录", font=("Microsoft YaHei", 9),
                 fg=C['text_dim'], bg=C['surface'], width=8, anchor="w").pack(side="left")
        entry(fr_out, self.output_dir).pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn(fr_out, "浏览", self._select_output, "#d0d7de", C['text'],
                  ("Microsoft YaHei", 9), width=6).pack(side="right")

        # 日期卡片
        date_card = card(left)
        date_card.pack(fill="x", pady=(0, 10))
        tk.Frame(date_card, bg=C['accent'], height=3).pack(fill="x")
        tk.Label(date_card, text="  📅 日期范围（可选）", font=("Microsoft YaHei", 10, "bold"),
                 fg=C['text'], bg=C['surface'], anchor="w").pack(fill="x", padx=12, pady=(10, 6))
        fr_date1 = tk.Frame(date_card, bg=C['surface'])
        fr_date1.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(fr_date1, text="开始", font=("Microsoft YaHei", 9),
                 fg=C['text_dim'], bg=C['surface'], width=6, anchor="w").pack(side="left")
        entry(fr_date1, self.start_date).pack(side="left", fill="x", expand=True)
        tk.Label(fr_date1, text="例：2026-04-01", font=("Microsoft YaHei", 9),
                 fg=C['text_dim'], bg=C['surface']).pack(side="right")
        fr_date2 = tk.Frame(date_card, bg=C['surface'])
        fr_date2.pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(fr_date2, text="结束", font=("Microsoft YaHei", 9),
                 fg=C['text_dim'], bg=C['surface'], width=6, anchor="w").pack(side="left")
        entry(fr_date2, self.end_date).pack(side="left", fill="x", expand=True)
        tk.Label(fr_date2, text="例：2026-04-30", font=("Microsoft YaHei", 9),
                 fg=C['text_dim'], bg=C['surface']).pack(side="right")

        # 物料搜索卡片
        search_card = card(left)
        search_card.pack(fill="x", pady=(0, 10))
        tk.Frame(search_card, bg=C['accent'], height=3).pack(fill="x")
        tk.Label(search_card, text="  🔍 物料搜索（可选）", font=("Microsoft YaHei", 10, "bold"),
                 fg=C['text'], bg=C['surface'], anchor="w").pack(fill="x", padx=12, pady=(10, 6))
        fr_search = tk.Frame(search_card, bg=C['surface'])
        fr_search.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(fr_search, text="编码/名称", font=("Microsoft YaHei", 9),
                 fg=C['text_dim'], bg=C['surface'], width=8, anchor="w").pack(side="left")
        entry(fr_search, self.material_search).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(fr_search, text="留空分析全部", font=("Microsoft YaHei", 9),
                 fg=C['text_dim'], bg=C['surface']).pack(side="right")

        # 数据预览
        self.preview_card = card(left)
        self.preview_card.pack(fill="x", pady=(0, 10))
        tk.Frame(self.preview_card, bg=C['accent'], height=3).pack(fill="x")
        tk.Label(self.preview_card, text="  📊 数据预览", font=("Microsoft YaHei", 10, "bold"),
                 fg=C['text'], bg=C['surface'], anchor="w").pack(fill="x", padx=12, pady=(10, 6))
        self.preview_lbl = tk.Label(self.preview_card, text="未选择文件", font=("Microsoft YaHei", 9),
                                    fg=C['text_dim'], bg=C['surface'], anchor="w", justify="left")
        self.preview_lbl.pack(fill="x", padx=12, pady=(0, 10))# 替代料配置卡片
        cfg = card(left)
        cfg.pack(fill="x")
        tk.Frame(cfg, bg=C['accent'], height=3).pack(fill="x")
        tk.Label(cfg, text="  🔧 替代料配对", font=("Microsoft YaHei", 10, "bold"),
                 fg=C['text'], bg=C['surface'], anchor="w").pack(fill="x", padx=12, pady=(10, 6))
        self.alt_list_frame = tk.Frame(cfg, bg=C['surface2'], height=90)
        self.alt_list_frame.pack(fill="x", padx=12)
        self.alt_list_frame.pack_propagate(False)
        alt_canvas = tk.Canvas(self.alt_list_frame, bg=C['surface2'], highlightthickness=0, height=90)
        alt_scroll = ttk.Scrollbar(self.alt_list_frame, command=alt_canvas.yview)
        alt_inner = tk.Frame(alt_canvas, bg=C['surface2'])
        self._alt_inner = alt_inner
        alt_canvas.configure(yscrollcommand=alt_scroll.set)
        alt_scroll.pack(side="right", fill="y")
        alt_canvas.pack(side="left", fill="both", expand=True)
        alt_canvas.create_window((0, 0), window=alt_inner, anchor="nw")
        alt_inner.bind("<Configure>", lambda e: alt_canvas.configure(scrollregion=alt_canvas.bbox("all")))
        self._refresh_alt_view(alt_inner)
        alt_canvas.bind("<MouseWheel>", lambda e: alt_canvas.yview_scroll(int(-e.delta/120), "units"))
        btn_row = tk.Frame(cfg, bg=C['surface'])
        btn_row.pack(fill="x", padx=12, pady=(6, 10))
        btn(btn_row, "➕ 添加", self._add_alt, "#d0d7de", C['text'], ("Microsoft YaHei", 9)).pack(side="left", padx=(0, 4))
        btn(btn_row, "🗑 删除", self._del_alt, "#d0d7de", C['danger'], ("Microsoft YaHei", 9)).pack(side="left", padx=(0, 4))
        btn(btn_row, "🔄 重置", self._reset_alt, "#d0d7de", C['text_dim'], ("Microsoft YaHei", 9)).pack(side="left", padx=(0, 4))
        btn(btn_row, "📸 JSON快照", self._show_alt_snapshot, "#d0d7de", C['text'], ("Microsoft YaHei", 9)).pack(side="left")

        # 右侧区域（进度、操作、审核、日志）
        right = tk.Frame(main, bg=C['bg'])
        right.pack(side="left", fill="both", expand=True)
        right_canvas = tk.Canvas(right, bg=C['bg'], highlightthickness=0)
        right_scrollbar = ttk.Scrollbar(right, orient="vertical", command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_scrollbar.set)
        right_scrollbar.pack(side="right", fill="y")
        right_canvas.pack(side="left", fill="both", expand=True)
        right_inner = tk.Frame(right_canvas, bg=C['bg'])
        right_inner_id = right_canvas.create_window((0, 0), window=right_inner, anchor="nw")
        def _configure_right_scroll(event=None):
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))
        right_inner.bind("<Configure>", _configure_right_scroll)
        def _resize_right_canvas(event=None):
            right_canvas.itemconfig(right_inner_id, width=event.width)
        right_canvas.bind("<Configure>", _resize_right_canvas)
        right_canvas.bind("<MouseWheel>", lambda e: right_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # 进度卡片
        pc = card(right_inner)
        pc.pack(fill="x", pady=(0, 14))
        tk.Frame(pc, bg=C['accent'], height=3).pack(fill="x")
        tk.Label(pc, text="  ⚡ 分析进度", font=("Microsoft YaHei", 10, "bold"),
         fg=C['text'], bg=C['surface'], anchor="w").pack(fill="x", padx=12, pady=(12, 10))
        self.step_frames = {}
        step_row = tk.Frame(pc, bg=C['surface'])
        step_row.pack(fill="x", padx=12, pady=(0, 10))
        for i, (name, icon) in enumerate(STEPS):
            fr = tk.Frame(step_row, bg=C['surface2'], relief="flat")
            fr.pack(side="left", padx=2)
            self.step_frames[i] = {'frame': fr, 'done': False}
            lbl = tk.Label(fr, text=icon, font=("Segoe UI Emoji", 11),
                           bg=C['surface2'], fg=C['text_dim'], width=2)
            lbl.pack(padx=4, pady=3)
            fr.bind("<Button-1>", lambda e, idx=i: self._show_step_log(idx))
        prog_row = tk.Frame(pc, bg=C['surface'])
        prog_row.pack(fill="x", padx=12, pady=(0, 10))
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(prog_row, variable=self.progress_var, maximum=100,
                                    length=100, style="TProgressbar")
        self.progress_bar.pack(fill="x", expand=True)
        self.progress_lbl = tk.Label(prog_row, text="就绪", font=("Microsoft YaHei", 9),
                             fg=C['text_dim'], bg=C['surface'])
        self.progress_lbl.pack(pady=(4, 0))

# 操作按钮卡片
        act = card(right_inner)
        act.pack(fill="x", pady=(0, 14))
        tk.Frame(act, bg=C['border'], height=1).pack(fill="x")
        btn_row = tk.Frame(act, bg=C['surface'])
        btn_row.pack(fill="x", padx=12, pady=10)
        self.run_btn = btn(btn_row, "▶  开始分析", self.start_analysis, bg=C['accent'], width=14)
        self.run_btn.pack(side="left", padx=(0, 8))
        self.cancel_btn = btn(btn_row, "⏹ 取消", self.request_cancel, bg="#d29922", width=10, state="disabled")
        self.cancel_btn.pack(side="left", padx=(0, 8))
        self.open_btn = btn(btn_row, "📂 打开目录", self.open_output, bg="#d0d7de", width=12, state="disabled")
        self.open_btn.pack(side="left", padx=(0, 8))
        self.ppt_btn = btn(btn_row, "📊 生成PPT", self.generate_ppt, bg="#6f42c1", fg="#ffffff", width=12, state="normal")
        self.ppt_btn.pack(side="left", padx=(0, 8))
        self.excel_btn = btn(btn_row, "📋 生成表格", self.generate_excel_direct, bg="#2a9d8f", fg="#ffffff", width=12, state="normal")
        self.excel_btn.pack(side="left", padx=(0, 8))
        self.timer_lbl = tk.Label(btn_row, text="⏱ 00:00", font=("Consolas", 11, "bold"),
                          fg=C['text_dim'], bg=C['surface'])
        self.timer_lbl.pack(side="right")# 审核卡片（包含明细、筛选、按钮）
        audit = card(right_inner)
        audit.pack(fill="both", expand=False, pady=(0, 14))
        tk.Frame(audit, bg="#1a365d", height=3).pack(fill="x")
        tk.Label(audit, text="  🤖 偏差明细与审核", font=("Microsoft YaHei", 10, "bold"),
         fg=C['text'], bg=C['surface'], anchor="w").pack(fill="x", padx=12, pady=(12, 8))

# 统计小卡片
        stat_row = tk.Frame(audit, bg=C['surface'])
        stat_row.pack(fill="x", padx=12, pady=(0, 8))
        self.audit_stat_labels = {}
        self.audit_stat_cards = {}
        stat_items = [
    ("total", "总记录", "gray", None),
    ("high_dev", "偏差>10%", "#d29922", "high_dev"),
    ("need_note", "需补备注", "#e63946", "need_note"),
    ("ok_note", "已审核", "#2a9d8f", "ok_note"),
        ]
        for key, text, color, filter_type in stat_items:
            fr = tk.Frame(stat_row, bg=C['surface2'], relief="flat", cursor="hand2")
            fr.pack(side="left", expand=True, fill="both", padx=(0, 6))
            lbl = tk.Label(fr, text="0", font=("Microsoft YaHei", 18, "bold"),
                          fg=color, bg=C['surface2'], anchor="center")
            lbl.pack(pady=(8, 0))
            tk.Label(fr, text=text, font=("Microsoft YaHei", 9),
                    fg=C['text_dim'], bg=C['surface2'], anchor="center").pack()
            self.audit_stat_labels[key] = lbl
            self.audit_stat_cards[key] = fr
            if filter_type:
                fr.bind("<Button-1>", lambda e, ft=filter_type: self._filter_audit_tree(ft))
                lbl.bind("<Button-1>", lambda e, ft=filter_type: self._filter_audit_tree(ft))
            else:
                fr.bind("<Button-1>", lambda e: self._filter_audit_tree(None))
                lbl.bind("<Button-1>", lambda e: self._filter_audit_tree(None))

        # 筛选栏
        # ── P1：万能搜索框 ──
        search_frame = tk.Frame(audit, bg=C['surface'])
        search_frame.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(search_frame, text="🔍", font=("Microsoft YaHei", 10),
        bg=C['surface']).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var,
        font=("Microsoft YaHei", 10), bg=C['surface2'],
        fg=C['text'], insertbackground=C['accent'],
        relief="flat")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.search_entry.insert(0, "输入任意关键词，实时过滤全部列...")
        self.search_entry.bind("<FocusIn>", lambda e: self.search_entry.delete(0, "end") if self.search_entry.get() == "输入任意关键词，实时过滤全部列..." else None)
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_filter_changed("search"))
        # 注册到 filter_widgets，方便重置
        self.filter_widgets['search'] = self.search_entry

        filter_bar = tk.Frame(audit, bg=C['surface'])
        filter_bar.pack(fill="x", padx=12, pady=(0, 5))

        filter_cols = [
            ('order_date', '订单日期'),
            ('remark', '备注'),
            ('ai_result', 'AI审核'),
            ('_color', '颜色'),
            ('audit_source', '审核来源'),
            ('remark_check_status', '校验提示'),
        ]
        # ── P1#12：筛选栏宽度映射 ──
        filter_width = {
            '订单日期': 16, '备注': 10, 'AI审核': 8, '颜色': 7,
            '审核来源': 10, '校验提示': 10,
        }

        self.filter_widgets = {}
        # P1#14：趋势显示标签容器
        self.trend_labels = {"早期": {}, "中期": {}, "近期": {}}
        for c in range(6):  # P1#12: 改为6列，容纳分隔线
            filter_bar.columnconfigure(c, weight=1)
        row_idx = 0
        col_idx = 0
        for col_key, col_label in filter_cols:
            col_frame = tk.Frame(filter_bar, bg=C['surface'])
            col_frame.grid(row=row_idx, column=col_idx, padx=2, pady=2, sticky="ew")
            filter_bar.columnconfigure(col_idx, weight=1)

            tk.Label(col_frame, text=col_label, font=("Microsoft YaHei", 9),
                     bg=C['surface'], fg=C['text_dim']).pack()

            if col_key == 'name':
                name_entry = tk.Entry(col_frame, font=("Microsoft YaHei", 9), width=10)
                name_entry.pack(fill="x")
                name_entry.bind("<KeyRelease>", lambda e, k=col_key: self._on_filter_changed(k))
                self.filter_widgets[col_key] = name_entry
                self.filter_vars[col_key] = name_entry
            elif col_key == 'order_date':
                # ── tkcalendar DateEntry 日期选择 ──
                date_row = tk.Frame(col_frame, bg=C['surface'])
                date_row.pack(fill="x")
                self.date_start_de = DateEntry(date_row, width=12,
                                               background='#4a90d9', foreground='white',
                                               borderwidth=1, font=("Microsoft YaHei", 9),
                                               locale='zh_CN', date_pattern='yyyy-mm-dd')
                self.date_start_de.pack(side="left", padx=(0, 2))
                tk.Label(date_row, text="~", font=("Microsoft YaHei", 9, 'bold'),
                         bg=C['surface'], fg=C['text_dim']).pack(side="left")
                self.date_end_de = DateEntry(date_row, width=12,
                                             background='#4a90d9', foreground='white',
                                             borderwidth=1, font=("Microsoft YaHei", 9),
                                             locale='zh_CN', date_pattern='yyyy-mm-dd')
                self.date_end_de.pack(side="left", padx=(2, 4))
                date_btn = tk.Button(date_row, text="筛选", font=("Microsoft YaHei", 9),
                                     bg='#4a90d9', fg='white', cursor='hand2',
                                     command=lambda: self._on_filter_changed('order_date'),
                                     relief='flat', padx=6)
                date_btn.pack(side="left")
                self.filter_widgets[col_key] = (self.date_start_de, self.date_end_de)
            else:
                col_width = filter_width.get(col_label, 10)
                # ── P1#13：颜色筛选下拉框 ──
                if col_key == '_color':
                    color_options = ["全部", "红", "橙", "黄", "绿"]
                    cb = ttk.Combobox(col_frame, state="readonly", font=("Microsoft YaHei", 9), 
                                  width=col_width, values=color_options)
                    cb.current(0)
                    cb.pack(fill="x")
                    cb.bind("<<ComboboxSelected>>", lambda e, k=col_key: self._on_filter_changed(k))
                    self.filter_vars[col_key] = tk.StringVar(value="全部")
                    self.filter_widgets[col_key] = cb
                else:
                    # 为新增筛选预设选项值
                    preset_options = {
                        'audit_source': ["全部", "AI", "手动", "替代料", "系统"],
                        'remark_check_status': ["全部", "红色", "黄色", "正常"],
                    }
                    cb = ttk.Combobox(
                        col_frame, state="readonly",
                        font=("Microsoft YaHei", 9),
                        width=col_width,
                        values=preset_options.get(col_key, [])
                    )
                    cb.pack(fill="x")
                    if preset_options.get(col_key):
                        cb.current(0)
                    cb.bind("<<ComboboxSelected>>",
                            lambda e, k=col_key: self._on_filter_changed(k))
                    self.filter_widgets[col_key] = cb
                # ── P1#12：常用组 后加分隔线 ──
                if col_key == 'order_date':
                    sep = tk.Frame(filter_bar, bg=C['surface'], width=2, height=20)
                    sep.configure(bg='#cccccc')  # 分隔线颜色
                    sep.grid(row=row_idx, column=col_idx+1, padx=(8, 0), pady=2, sticky='ns')

            col_idx += 1
            if col_idx >= 6:
                col_idx = 0
                row_idx += 1

        # 重置按钮放在第二行末尾
        reset_btn_frame = tk.Frame(filter_bar, bg=C['surface'])
        reset_btn_frame.grid(row=1, column=4, pady=(4,0), sticky="e")
        reset_btn = btn(reset_btn_frame, "重置", self._reset_all_filters,
                              bg="#d0d7de", fg=C['text'], width=6)
        reset_btn.pack(side="left")
        # 列宽锁定按钮
        self.column_locked = self._load_lock_state()
        lock_text = "🔒 已锁定" if self.column_locked else "🔓 可调整"
        self.lock_btn = tk.Button(reset_btn_frame, text=lock_text,
                                  command=self._toggle_column_lock,
                                  font=("Microsoft YaHei", 9),
                                  bg="#f0f0f0" if self.column_locked else "#e8f5e9",
                                  fg="#333333", relief="flat", cursor="hand2",
                                  activebackground="#e0e0e0", width=10)
        self.lock_btn.pack(side="left", padx=(4, 0))
        # 重置列宽按钮
        tk.Button(reset_btn_frame, text="↩重置列宽", command=self._reset_default_widths,
                  font=("Microsoft YaHei", 9), bg="#fff3e0", fg="#333333",
                  relief="flat", cursor="hand2", activebackground="#ffe0b2",
                  width=8).pack(side="left", padx=(4, 0))
        self.filter_status_lbl = tk.Label(audit, text="", font=("Microsoft YaHei", 9),
                                   bg=C['surface'], fg=C['text_dim'], anchor="w")
        self.filter_status_lbl.pack(fill="x", padx=12, pady=(0, 4))# Treeview 表格
        self.table_frame = tk.Frame(audit, bg=C['surface'])
        self.table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        tree_container = tk.Frame(self.table_frame, bg=C['surface'])
        tree_container.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        audit_vscroll = ttk.Scrollbar(tree_container, orient="vertical")
        audit_vscroll.pack(side="right", fill="y")
        audit_hscroll = ttk.Scrollbar(tree_container, orient="horizontal")
        audit_hscroll.pack(side="bottom", fill="x")
        cols = ("idx", "excel_row", "factory", "admin", "order_date", "order_no",
                "code", "name", "quota", "actual", "dev_rate", "is_alt", "status",
                "remark", "batch_remark", "audit_result", "AI建议", "audit_status",
                "audit_source", "deviation_amount",
                "remark_check_status", "remark_check_msg")
        self.audit_tree = ttk.Treeview(tree_container, columns=cols, show="headings",
                               height=15, style="Custom.Treeview",
                               selectmode="extended",
                               yscrollcommand=audit_vscroll.set,
                               xscrollcommand=audit_hscroll.set)
        self.audit_tree.heading("idx", text="序号")
        self.audit_tree.heading("excel_row", text="原表行号")
        self.audit_tree.heading("factory", text="工厂名称")
        self.audit_tree.heading("admin", text="车间")
        self.audit_tree.heading("order_date", text="订单日期")
        self.audit_tree.heading("order_no", text="流程订单")
        self.audit_tree.heading("code", text="物料号")
        self.audit_tree.heading("name", text="物料描述")
        self.audit_tree.heading("quota", text="定额")
        self.audit_tree.heading("actual", text="实际")
        self.audit_tree.heading("dev_rate", text="偏差率%")
        self.audit_tree.heading("is_alt", text="替代料")
        self.audit_tree.heading("status", text="状态")
        self.audit_tree.heading("remark", text="备注")
        self.audit_tree.heading("batch_remark", text="批量备注")
        self.audit_tree.heading("audit_result", text="审核结果")
        self.audit_tree.heading("AI建议", text="AI建议")
        self.audit_tree.heading("audit_status", text="审核状态")
        self.audit_tree.heading("audit_source", text="审核来源")
        self.audit_tree.heading("deviation_amount", text="偏差金额")
        self.audit_tree.heading("remark_check_status", text="")
        self.audit_tree.heading("remark_check_msg", text="校验提示")
        # column() 顺序必须与 heading() 顺序完全一致，否则数据显示错位
        self.audit_tree.column("idx", width=35, anchor="center")
        self.audit_tree.column("excel_row", width=60, anchor="center")
        self.audit_tree.column("factory", width=70, anchor="w")
        self.audit_tree.column("admin", width=70, anchor="w")
        self.audit_tree.column("order_date", width=70, anchor="center")
        self.audit_tree.column("order_no", width=100, anchor="center")
        self.audit_tree.column("code", width=70, anchor="center")
        self.audit_tree.column("name", width=100, anchor="w")
        self.audit_tree.column("quota", width=50, anchor="e")
        self.audit_tree.column("actual", width=50, anchor="e")
        self.audit_tree.column("dev_rate", width=55, anchor="center")
        self.audit_tree.column("is_alt", width=50, anchor="center")
        self.audit_tree.column("status", width=55, anchor="center")
        self.audit_tree.column("remark", width=80, anchor="w")
        self.audit_tree.column("batch_remark", width=90, anchor="w")
        self.audit_tree.column("audit_result", width=80, anchor="center")
        self.audit_tree.column("AI建议", width=120, anchor="w")
        self.audit_tree.column("audit_status", width=60, anchor="center")
        self.audit_tree.column("audit_source", width=70, anchor="center")
        self.audit_tree.column("deviation_amount", width=90, anchor="e")
        self.audit_tree.column("remark_check_status", width=0, stretch=False)
        self.audit_tree.column("remark_check_msg", width=150, anchor="w")
        self.audit_tree.pack(side="left", fill="both", expand=True)
        # 应用初始列宽锁定状态
        self.root.after(100, self._toggle_column_lock)
        audit_vscroll.config(command=self.audit_tree.yview)
        audit_hscroll.config(command=self.audit_tree.xview)
        self.audit_context_menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei", 9))
        self.audit_context_menu.add_command(label="📝 批量改状态", command=self._batch_change_status)
        self.audit_context_menu.add_command(label="📋 批量填备注", command=self._batch_remark)
        self.audit_context_menu.add_command(label="📤 批量导出", command=self._batch_export)
        self.audit_context_menu.add_separator()
        self.audit_context_menu.add_command(label="➕ 添加状态标签", command=self._add_custom_status)
        self.audit_context_menu.add_separator()
        self.audit_context_menu.add_command(label="🔒 移入隔离区", command=self._quarantine_selected)
        self.audit_context_menu.add_separator()
        self.audit_context_menu.add_command(label="📋 复制为微信草稿", command=self._copy_wechat_draft)
        self.audit_tree.bind("<Button-3>", self._show_audit_context_menu)
        self.audit_tree.tag_configure('row_even', background='#f5f7fa', foreground='#24292e')
        self.audit_tree.tag_configure('row_odd',  background='#ffffff',  foreground='#24292e')
        self.audit_tree.tag_configure('need_note', background='#fff0e0', foreground='#b04000')
        self.audit_tree.tag_configure('ok_note',   background='#e8f5e9', foreground='#1a6b1a')
        self.audit_tree.tag_configure('ai_gen',    background='#fce4ec', foreground='#880e4f')
        self.audit_tree.tag_configure('sel', background=C['accent'], foreground='#ffffff')
        self.audit_tree.tag_configure('priority_red', background='#ffe0e0')
        self.audit_tree.tag_configure('priority_yellow', background='#fff8e0')
        self.audit_tree.tag_configure('priority_green', background='#e8f5e9')
        self.audit_tree.tag_configure('mutation_alert', background='#fff3e0')
        self.audit_tree.tag_configure('amt_rank_1', background='#ffcdd2')
        self.audit_tree.tag_configure('amt_rank_2', background='#ffebee')
        self.audit_tree.tag_configure('auto_closed', background='#f0f0f0')
        self.audit_tree.tag_configure('over_amount', background='#ffebee')
        self.audit_tree.tag_configure('under_amount', background='#e8f5e9')
        self.audit_tree.tag_configure('remark_red', background='#ffcccc')
        self.audit_tree.tag_configure('remark_yellow', background='#ffffcc')
        self.audit_tree.bind("<Double-Button-1>", self._on_tree_double_click)
        # B004: removed single-click card popup; only double-click triggers _show_audit_card
        self.audit_data = pd.DataFrame()

# 统一操作按钮行
        op_card = card(right_inner)
        op_card.pack(fill="x", pady=(0, 10))
        tk.Frame(op_card, bg=C['accent'], height=3).pack(fill="x")
        tk.Label(op_card, text="  ⚡ 操作", font=("Microsoft YaHei", 10, "bold"),
         fg=C['text'], bg=C['surface'], anchor="w").pack(fill="x", padx=12, pady=(10, 6))
        # 第一行按钮：核心操作
        row1_frame = tk.Frame(op_card, bg=C['surface'])
        row1_frame.pack(fill="x", padx=12, pady=(0, 2))
        self.load_audit_btn = btn(row1_frame, "📂 加载审核数据", self._load_audit_data_from_output_click,
                                  bg="#5c6bc0", fg="white", width=14, state="disabled")
        self.load_audit_btn.pack(side="left", padx=(0, 8))
        self.unified_ai_btn = btn(row1_frame, "🧠 AI审核备注", self._run_ai_audit,
                                bg="#6f42c1", fg="white", width=14, state="disabled")
        self.unified_ai_btn.pack(side="left", padx=(0, 8))
        # 取消AI审核按钮
        self.cancel_audit_btn = tk.Button(row1_frame, text="取消审核", command=self._cancel_ai_audit,
                                bg="#ff9800", fg="white", width=8, state="disabled")
        self.cancel_audit_btn.pack(side="left", padx=(0, 8))
        self.unified_export_btn = btn(row1_frame, "💾 导出Excel", self._export_audit_excel,
                                     bg="#2a9d8f", fg="white", width=14, state="disabled")
        self.unified_export_btn.pack(side="left", padx=(0, 8))
        self.save_audit_btn = btn(row1_frame, "💾 保存审核结果", self._save_audit_back,
                                bg="#e76f51", fg="white", width=14, state="disabled")
        self.save_audit_btn.pack(side="left", padx=(0, 8))

        # Audit log export button (Task 004)
        self.export_audit_log_btn = btn(row1_frame, "📋 导出审计日志", self._export_audit_log,
                                        bg="#6c757d", fg="#ffffff", width=14)
        self.export_audit_log_btn.pack(side="left", padx=(0, 8))
        self.export_db_btn = btn(row1_frame, "📤 导出备份", self._export_audit_backup,
                               bg="#4a90d9", fg="white", width=12, state="normal")
        self.export_db_btn.pack(side="left", padx=(0, 8))
        self.import_db_btn = btn(row1_frame, "📥 导入备份", self._import_audit_backup,
                               bg="#4a90d9", fg="white", width=12, state="normal")
        self.import_db_btn.pack(side="left")
        self.tree_view_btn = btn(row1_frame, "🌲 树形视图", self._show_tree_view,
                               bg="#4a90d9", fg="white", width=12, state="disabled")
        self.tree_view_btn.pack(side="left", padx=(8, 0))

        # 第二行按钮：辅助操作
        row2_frame = tk.Frame(op_card, bg=C['surface'])
        row2_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.resume_btn = btn(row2_frame, "📌 恢复进度", self._do_resume_state,
                              bg="#fff3cd", fg="#856404", width=12, state="disabled")
        self.resume_btn.pack(side="left", padx=(0, 8))
        self.quarantine_btn = btn(row2_frame, "📦 隔离区", self._open_quarantine,
                                  bg="#f59e0b", fg="white", width=12, state="normal")
        self.quarantine_btn.pack(side="left", padx=(0, 8))
        self.auto_close_btn = btn(row2_frame, "✅ 自动结案", self._auto_close,
                                   bg="#2a9d8f", fg="white", width=16, state="disabled")
        self.auto_close_btn.pack(side="left", padx=(0, 8))
        self.cancel_auto_close_btn = btn(row2_frame, "⛔ 取消结案", self._cancel_auto_close,
                                   bg="#ef4444", fg="white", width=10, state="disabled")
        self.cancel_auto_close_btn.pack(side="left", padx=(0, 8))
        self.unified_result_lbl = tk.Label(row2_frame, text="",
                                    font=("Microsoft YaHei", 9),
                                    fg=C['text_dim'], bg=C['surface'])
        self.unified_result_lbl.pack(side="right")
        self.status_filter_label = tk.Label(row2_frame, text="",
                                    font=("Microsoft YaHei", 9),
                                    fg=C['text_dim'], bg=C['surface'])
        self.status_filter_label.pack(side="left", padx=(0, 8))

# ── P1#14：趋势分析显示区域 ──
        trend_row = tk.Frame(right_inner, bg=C['surface'])
        trend_row.pack(fill="x", padx=12, pady=(8, 8))
        # 初始化趋势数据
        self.trend_data = None
        # 三列布局
        for period in ["早期", "中期", "近期"]:
            col_frame = tk.Frame(trend_row, bg=C['surface2'], relief="flat", bd=1)
            col_frame.pack(side="left", fill="both", expand=True, padx=4)
            tk.Label(col_frame, text=period, font=("Microsoft YaHei", 10, "bold"),
                    bg=C['surface2'], fg=C['text']).pack(pady=(6, 2))
            self.trend_labels[period] = {
                "range": tk.Label(col_frame, text="--", font=("Microsoft YaHei", 9),
                                   bg=C['surface2'], fg=C['text_dim']),
                "dev_rate": tk.Label(col_frame, text="--", font=("Microsoft YaHei", 9),
                                     bg=C['surface2'], fg=C['text']),
                "dev_amount": tk.Label(col_frame, text="--", font=("Microsoft YaHei", 9),
                                       bg=C['surface2'], fg=C['text']),
                "pass_rate": tk.Label(col_frame, text="--", font=("Microsoft YaHei", 9),
                                       bg=C['surface2'], fg=C['text']),
            }
            self.trend_labels[period]["range"].pack()
            self.trend_labels[period]["dev_rate"].pack()
            self.trend_labels[period]["dev_amount"].pack()
            self.trend_labels[period]["pass_rate"].pack()

# 批量操作行
        batch_btn_row = tk.Frame(right_inner, bg=C['surface'])
        batch_btn_row.pack(fill="x", padx=12, pady=(8, 0))
        btn(batch_btn_row, "📝 批量改状态", self._batch_change_status,
          "#3b82f6", "#ffffff", ("Microsoft YaHei", 9), width=10).pack(side="left", padx=(0, 6))
        btn(batch_btn_row, "📋 批量填备注", self._batch_remark,
          "#10b981", "#ffffff", ("Microsoft YaHei", 9), width=10).pack(side="left", padx=(0, 6))
        btn(batch_btn_row, "📤 批量导出", self._batch_export,
          "#f59e0b", "#ffffff", ("Microsoft YaHei", 9), width=10).pack(side="left", padx=(0, 6))
        btn(batch_btn_row, "➕ 添加状态", self._add_custom_status,
          "#6366f1", "#ffffff", ("Microsoft YaHei", 9), width=10).pack(side="left", padx=(0, 6))
        self.bom_btn = btn(batch_btn_row, "📦 BOM导入", self._import_bom,
                           "#4a90d9", "#ffffff", ("Microsoft YaHei", 9), width=10)
        self.bom_btn.pack(side="left", padx=(6, 0))
        self.cleanup_btn = btn(batch_btn_row, "🧹 备注清洗", self._show_cleanup_window,
                                "#795548", "#ffffff", ("Microsoft YaHei", 9), width=10)
        self.cleanup_btn.pack(side="left", padx=(6, 0))

        self.audit_ai_btn = self.unified_ai_btn
        self.audit_export_btn = self.unified_export_btn# 日志卡片
        lc = card(right_inner)
        lc.pack(fill="both", expand=True)
        tk.Frame(lc, bg=C['border'], height=1).pack(fill="x")
        # 标题 + 导出按钮行
        log_title_bar = tk.Frame(lc, bg=C['surface'])
        log_title_bar.pack(fill="x", padx=12, pady=(10, 3))
        tk.Label(log_title_bar, text="  📝 运行日志", font=("Microsoft YaHei", 10, "bold"),
                 fg=C['text'], bg=C['surface'], anchor="w").pack(side="left")
        tk.Button(log_title_bar, text="导出", font=("Microsoft YaHei", 9),
                  command=self._export_log,
                  bg=C['surface2'], fg=C['text'], relief="flat", cursor="hand2",
                  activebackground=C['surface'], activeforeground=C['accent']).pack(side="right", padx=4)
        tk.Button(log_title_bar, text="版本日志", font=("Microsoft YaHei", 9),
                  command=self._export_changelog,
                  bg=C['surface2'], fg=C['text'], relief="flat", cursor="hand2",
                  activebackground=C['surface'], activeforeground=C['accent']).pack(side="right", padx=4)
        tk.Button(log_title_bar, text="📖 故事线", font=("Microsoft YaHei", 9),
                  command=self._show_storyline,
                  bg=C['surface2'], fg=C['text'], relief="flat", cursor="hand2",
                  activebackground=C['surface'], activeforeground=C['accent']).pack(side="right", padx=4)
        log_fr = tk.Frame(lc, bg=C['surface2'])
        log_fr.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(
            log_fr, font=("Consolas", 9), bg='#ffffff', fg='#1f2328',
            insertbackground=C['text'], relief="flat", wrap="word")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("info", foreground=C['info'])
        self.log_text.tag_configure("error", foreground=C['danger'])
        self.log_text.tag_configure("success", foreground=C['green'])
        self.log_text.tag_configure("warn", foreground=C['warn'])
        self.log_text.tag_configure("step", foreground=C['purple'])
        self.log_text.tag_configure("dim", foreground=C['text_dim'])

        # 底部状态栏
        status = tk.Frame(self.root, bg=C['header_bg'], height=28)
        status.pack(fill="x")
        status.pack_propagate(False)
        tk.Frame(status, bg=C['accent'], width=3).pack(side="left", fill="y")
        self.status_lbl = tk.Label(status, text="就绪 — 选择输入文件后点击「开始分析」",
                                   font=("Microsoft YaHei", 9), fg=C['text_dim'],
                                   bg=C['header_bg'], anchor="w")
        self.status_lbl.pack(side="left", padx=12)

