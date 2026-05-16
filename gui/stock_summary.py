"""
S01 模块：云南达利收发存汇总（独立单文件版）
无外部依赖，内置 SQLite 和 Excel 解析
直接运行即可
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import re
from datetime import datetime
import pandas as pd

# ========== 配色方案 ==========
COLORS = {
    'surface': '#f5f5f5',
    'surface2': '#ffffff',
    'text': '#1f2328',
    'text_secondary': '#6e7781',
    'accent': '#1a365d',
}

# ========== 数据库操作类（内置） ==========
class StockDatabase:
    DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "stock_summary.db")

    def __init__(self):
        self.conn = None
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(self.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zmm062_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_month DATE NOT NULL,
                company_code TEXT,
                plant_code TEXT,
                plant_name TEXT,
                group_warehouse_category TEXT NOT NULL,
                storage_location TEXT,
                storage_desc TEXT,
                material_group TEXT,
                material_code TEXT,
                material_desc TEXT,
                spec_desc TEXT,
                unit TEXT,
                opening_qty REAL,
                opening_amount REAL,
                inbound_qty REAL,
                inbound_amount REAL,
                outbound_qty REAL,
                outbound_amount REAL,
                closing_qty REAL,
                closing_amount REAL,
                unit_price REAL,
                turnover_days INTEGER,
                turnover_rate REAL,
                flags TEXT,
                remark TEXT,
                created_by TEXT,
                modified_by TEXT,
                imported_at TIMESTAMP,
                UNIQUE(report_month, plant_code, group_warehouse_category, material_code)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_plant_period_cat_mat ON zmm062_summary(plant_code, report_month, group_warehouse_category, material_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_material_group ON zmm062_summary(material_group)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_category ON zmm062_summary(group_warehouse_category)')
        self.conn.commit()

    def get_distinct_categories(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT group_warehouse_category FROM zmm062_summary ORDER BY group_warehouse_category")
        return [row[0] for row in cursor.fetchall()]

    def get_distinct_material_groups(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT material_group FROM zmm062_summary ORDER BY material_group")
        return [row[0] for row in cursor.fetchall()]

    def get_latest_month(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(report_month) FROM zmm062_summary")
        row = cursor.fetchone()
        return row[0] if row and row[0] else None

    def query_summary(self, plant_code=None, group_category=None, material_group=None,
                      start_month=None, end_month=None, search_text=None):
        query = """
            SELECT 
                group_warehouse_category,
                material_code,
                material_desc,
                unit,
                closing_qty,
                closing_amount,
                outbound_amount,
                turnover_days,
                flags
            FROM zmm062_summary
            WHERE 1=1
        """
        params = []
        if plant_code:
            query += " AND plant_code = ?"
            params.append(plant_code)
        if group_category:
            query += " AND group_warehouse_category = ?"
            params.append(group_category)
        if material_group:
            query += " AND material_group = ?"
            params.append(material_group)
        if start_month:
            query += " AND report_month >= ?"
            params.append(start_month)
        if end_month:
            query += " AND report_month <= ?"
            params.append(end_month)
        if search_text:
            query += " AND (material_code LIKE ? OR material_desc LIKE ?)"
            params.append(f"%{search_text}%")
            params.append(f"%{search_text}%")
        query += " ORDER BY group_warehouse_category, material_code"
        return pd.read_sql_query(query, self.conn, params=params)

    def insert_summary(self, df):
        cursor = self.conn.cursor()
        success_count = 0
        for _, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO zmm062_summary (
                        report_month, company_code, plant_code, plant_name,
                        group_warehouse_category, storage_location, storage_desc,
                        material_group, material_code, material_desc, spec_desc, unit,
                        opening_qty, opening_amount, inbound_qty, inbound_amount,
                        outbound_qty, outbound_amount, closing_qty, closing_amount,
                        unit_price, turnover_days, turnover_rate, flags, remark,
                        created_by, imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['report_month'], row.get('company_code'), row.get('plant_code'), row.get('plant_name'),
                    row['group_warehouse_category'], row.get('storage_location'), row.get('storage_desc'),
                    row.get('material_group'), row['material_code'], row.get('material_desc'), row.get('spec_desc'), row.get('unit'),
                    row.get('opening_qty', 0), row.get('opening_amount', 0),
                    row.get('inbound_qty', 0), row.get('inbound_amount', 0),
                    row.get('outbound_qty', 0), row.get('outbound_amount', 0),
                    row.get('closing_qty', 0), row.get('closing_amount', 0),
                    row.get('unit_price', 0), row.get('turnover_days', 0), row.get('turnover_rate', 0),
                    '', '', 'system', datetime.now().isoformat()
                ))
                success_count += 1
            except Exception as e:
                print(f"插入失败: {e}")
        self.conn.commit()
        return success_count

    def close(self):
        if self.conn:
            self.conn.close()

# ========== Excel 解析函数（内置） ==========
def parse_zmm062_excel(file_path):
    """解析 ZMM062 Excel 文件，返回标准化 DataFrame"""
    try:
        food_df = pd.read_excel(file_path, sheet_name='食品', header=0)
        drink_df = pd.read_excel(file_path, sheet_name='饮料', header=0)
        df = pd.concat([food_df, drink_df], ignore_index=True)
    except Exception as e:
        raise ValueError(f"读取 Excel 失败：{e}")

    column_mapping = {
        '公司代码': 'company_code',
        '工厂': 'plant_code',
        '工厂描述': 'plant_name',
        '库存地点': 'storage_location',
        '库存地点描述': 'storage_desc',
        '物料组描述': 'material_group',
        '物料号': 'material_code',
        '物料描述': 'material_desc',
        '规格描述': 'spec_desc',
        '单位': 'unit',
        '开始数量': 'opening_qty',
        '开始单价(含税)': 'unit_price',
        '开始金额(含税)': 'opening_amount',
        '入库总数量': 'inbound_qty',
        '入库总金额(含税)': 'inbound_amount',
        '出库总数量': 'outbound_qty',
        '出库总金额(含税)': 'outbound_amount',
        '结束数量': 'closing_qty',
        '结束金额(含税)': 'closing_amount',
        '周转天': 'turnover_days',
        '周转率': 'turnover_rate',
        '集团仓库分类': 'group_warehouse_category'
    }
    existing_cols = [c for c in column_mapping.keys() if c in df.columns]
    df = df[existing_cols].rename(columns=column_mapping)

    # 提取报表月份
    match = re.search(r'(\d{6})', file_path)
    if match:
        yymm = match.group(1)
        report_month = f"20{yymm[:2]}-{yymm[2:4]}"
    else:
        report_month = datetime.now().strftime("%Y-%m")
    df['report_month'] = report_month

    # 清洗数值列
    numeric_cols = ['opening_qty', 'opening_amount', 'inbound_qty', 'inbound_amount',
                    'outbound_qty', 'outbound_amount', 'closing_qty', 'closing_amount',
                    'unit_price', 'turnover_days', 'turnover_rate']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 集团仓库分类
    if 'group_warehouse_category' in df.columns:
        df['group_warehouse_category'] = df['group_warehouse_category'].fillna('未知分类').astype(str)
    else:
        df['group_warehouse_category'] = '未知分类'

    # 确保出库为负数
    if 'outbound_qty' in df.columns:
        df['outbound_qty'] = df['outbound_qty'].apply(lambda x: -abs(x) if x > 0 else x)
    if 'outbound_amount' in df.columns:
        df['outbound_amount'] = df['outbound_amount'].apply(lambda x: -abs(x) if x > 0 else x)

    return df

# ========== 主窗口类 ==========
class StockSummaryWindow:
    def __init__(self, parent=None):
        self.parent = parent
        self.db = StockDatabase()
        self.current_data = None

        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("云南达利收发存汇总 - S01")
        self.window.geometry("1400x800")
        self.window.configure(bg=COLORS['surface'])
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()
        self._load_latest_month()

    def _build_ui(self):
        main_frame = tk.Frame(self.window, bg=COLORS['surface'])
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 导入按钮行
        import_frame = tk.Frame(main_frame, bg=COLORS['surface'])
        import_frame.pack(fill="x", pady=(0, 5))
        tk.Button(import_frame, text="📂 导入 ZMM062 报表", command=self._import_excel,
                  bg=COLORS['accent'], fg="white", font=("Microsoft YaHei", 10, "bold"),
                  relief="flat", padx=10, pady=5).pack(side="left")

        self._build_filter_bar(main_frame)
        self._build_stats_cards(main_frame)
        self._build_table(main_frame)
        self._build_status_bar(main_frame)

    def _build_filter_bar(self, parent):
        filter_frame = tk.LabelFrame(parent, text="筛选条件", bg=COLORS['surface'], fg=COLORS['text'], font=("Microsoft YaHei", 10, "bold"))
        filter_frame.pack(fill="x", pady=(0, 10))

        row = 0
        tk.Label(filter_frame, text="工厂：", bg=COLORS['surface'], fg=COLORS['text']).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        self.plant_var = tk.StringVar(value="全部")
        plant_combo = ttk.Combobox(filter_frame, textvariable=self.plant_var, values=["全部", "1101", "1102"], state="readonly", width=15)
        plant_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        plant_combo.bind("<<ComboboxSelected>>", lambda e: self._on_filter_changed())

        tk.Label(filter_frame, text="集团仓库分类：", bg=COLORS['surface'], fg=COLORS['text']).grid(row=row, column=2, padx=5, pady=5, sticky="e")
        self.category_var = tk.StringVar(value="全部")
        self.category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, state="readonly", width=20)
        self.category_combo.grid(row=row, column=3, padx=5, pady=5, sticky="w")
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self._on_filter_changed())
        self._load_category_options()

        tk.Label(filter_frame, text="物料组：", bg=COLORS['surface'], fg=COLORS['text']).grid(row=row, column=4, padx=5, pady=5, sticky="e")
        self.mat_group_var = tk.StringVar(value="全部")
        self.mat_group_combo = ttk.Combobox(filter_frame, textvariable=self.mat_group_var, state="readonly", width=25)
        self.mat_group_combo.grid(row=row, column=5, padx=5, pady=5, sticky="w")
        self.mat_group_combo.bind("<<ComboboxSelected>>", lambda e: self._on_filter_changed())
        self._load_material_group_options()

        row += 1
        tk.Label(filter_frame, text="起始月份：", bg=COLORS['surface'], fg=COLORS['text']).grid(row=row, column=0, padx=5, pady=5, sticky="e")
        self.start_month_var = tk.StringVar()
        start_entry = ttk.Entry(filter_frame, textvariable=self.start_month_var, width=12)
        start_entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        start_entry.bind("<KeyRelease>", lambda e: self._on_filter_changed())

        tk.Label(filter_frame, text="结束月份：", bg=COLORS['surface'], fg=COLORS['text']).grid(row=row, column=2, padx=5, pady=5, sticky="e")
        self.end_month_var = tk.StringVar()
        end_entry = ttk.Entry(filter_frame, textvariable=self.end_month_var, width=12)
        end_entry.grid(row=row, column=3, padx=5, pady=5, sticky="w")
        end_entry.bind("<KeyRelease>", lambda e: self._on_filter_changed())

        tk.Label(filter_frame, text="搜索：", bg=COLORS['surface'], fg=COLORS['text']).grid(row=row, column=4, padx=5, pady=5, sticky="e")
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(filter_frame, textvariable=self.search_var, font=("Microsoft YaHei", 9), bg=COLORS['surface2'], fg=COLORS['text'])
        search_entry.grid(row=row, column=5, padx=5, pady=5, sticky="we")
        search_entry.bind("<KeyRelease>", lambda e: self._on_filter_changed())

        btn_frame = tk.Frame(filter_frame, bg=COLORS['surface'])
        btn_frame.grid(row=row, column=6, padx=10, pady=5, sticky="e")
        tk.Button(btn_frame, text="查询", command=self._on_filter_changed, bg=COLORS['accent'], fg="white", width=8).pack(side="left", padx=2)
        tk.Button(btn_frame, text="重置", command=self._reset_filters, bg=COLORS['surface2'], fg=COLORS['text'], width=8).pack(side="left", padx=2)

        filter_frame.columnconfigure(5, weight=1)

    def _build_stats_cards(self, parent):
        card_frame = tk.Frame(parent, bg=COLORS['surface'])
        card_frame.pack(fill="x", pady=(0, 10))
        self.total_amount_card = self._create_card(card_frame, "期末总库存金额", "¥0.00", 0)
        self.total_amount_card.pack(side="left", expand=True, fill="x", padx=5)
        self.total_materials_card = self._create_card(card_frame, "总物料种类", "0", 1)
        self.total_materials_card.pack(side="left", expand=True, fill="x", padx=5)
        self.turnover_days_card = self._create_card(card_frame, "整体周转天数", "0天", 2)
        self.turnover_days_card.pack(side="left", expand=True, fill="x", padx=5)
        self.abnormal_card = self._create_card(card_frame, "异常物料数", "0", 3, alert=True)
        self.abnormal_card.pack(side="left", expand=True, fill="x", padx=5)

    def _create_card(self, parent, title, value, column, alert=False):
        frame = tk.Frame(parent, bg=COLORS['surface2'], relief="ridge", bd=1)
        frame.columnconfigure(0, weight=1)
        tk.Label(frame, text=title, font=("Microsoft YaHei", 9), bg=COLORS['surface2'], fg=COLORS['text_secondary']).grid(row=0, column=0, pady=(8, 0))
        value_label = tk.Label(frame, text=value, font=("Microsoft YaHei", 18, "bold"), bg=COLORS['surface2'], fg=COLORS['text'])
        value_label.grid(row=1, column=0, pady=(5, 8))
        if alert:
            alert_dot = tk.Label(frame, text="●", fg="red", bg=COLORS['surface2'], font=("Arial", 10))
            alert_dot.place(x=5, y=5)
            alert_dot.place_forget()
            frame.alert_dot = alert_dot
        frame.value_label = value_label
        return frame

    def _build_table(self, parent):
        table_frame = tk.Frame(parent, bg=COLORS['surface'])
        table_frame.pack(fill="both", expand=True)
        columns = ("group_warehouse_category", "material_code", "material_desc", "unit",
                   "closing_qty", "closing_amount", "outbound_amount", "turnover_days", "flags")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)
        col_config = {
            "group_warehouse_category": ("集团仓库分类", 150, "w"),
            "material_code": ("物料号", 120, "w"),
            "material_desc": ("物料描述", 250, "w"),
            "unit": ("单位", 60, "center"),
            "closing_qty": ("期末数量", 100, "e"),
            "closing_amount": ("期末金额(¥)", 120, "e"),
            "outbound_amount": ("本月出库金额(¥)", 120, "e"),
            "turnover_days": ("周转天数", 80, "e"),
            "flags": ("异常标记", 150, "w")
        }
        for col, config in col_config.items():
            self.tree.heading(col, text=config[0], command=lambda c=col: self._sort_by_column(c, False))
            anchor = config[2] if len(config) > 2 else "center"
            self.tree.column(col, width=config[1], anchor=anchor)
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Double-1>", self._on_row_double_click)

    def _build_status_bar(self, parent):
        status_frame = tk.Frame(parent, bg=COLORS['surface'], height=25)
        status_frame.pack(fill="x", side="bottom")
        self.status_label = tk.Label(status_frame, text="就绪", anchor="w", bg=COLORS['surface'], fg=COLORS['text_secondary'])
        self.status_label.pack(side="left", padx=5)
        self.row_count_label = tk.Label(status_frame, text="0 条记录", anchor="e", bg=COLORS['surface'], fg=COLORS['text_secondary'])
        self.row_count_label.pack(side="right", padx=5)

    def _load_category_options(self):
        categories = self.db.get_distinct_categories()
        values = ["全部"] + sorted(categories)
        self.category_combo['values'] = values
        if values:
            self.category_var.set("全部")

    def _load_material_group_options(self):
        groups = self.db.get_distinct_material_groups()
        values = ["全部"] + sorted(groups)
        self.mat_group_combo['values'] = values
        if values:
            self.mat_group_var.set("全部")

    def _load_latest_month(self):
        latest_month = self.db.get_latest_month()
        if latest_month:
            self.start_month_var.set(latest_month)
            self.end_month_var.set(latest_month)
            self._on_filter_changed()
        else:
            self.status_label.config(text="未找到任何数据，请先导入ZMM062报表")

    def _import_excel(self):
        file_path = filedialog.askopenfilename(
            title="请选择 ZMM062 收发存报表",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
        progress_win = tk.Toplevel(self.window)
        progress_win.title("导入中")
        progress_win.geometry("300x100")
        tk.Label(progress_win, text="正在解析 Excel，请稍候...", bg=COLORS['surface']).pack(pady=20)
        progress_win.update()
        try:
            df = parse_zmm062_excel(file_path)
            if df is None or df.empty:
                messagebox.showerror("导入失败", "Excel 文件解析后无有效数据")
                progress_win.destroy()
                return
            success_count = self.db.insert_summary(df)
            progress_win.destroy()
            messagebox.showinfo("导入成功", f"成功导入 {success_count} 条记录")
            self._load_category_options()
            self._load_material_group_options()
            self._load_latest_month()
        except Exception as e:
            progress_win.destroy()
            messagebox.showerror("导入失败", f"解析或导入时出错：\n{e}")

    def _on_filter_changed(self):
        plant = self.plant_var.get() if self.plant_var.get() != "全部" else None
        category = self.category_var.get() if self.category_var.get() != "全部" else None
        mat_group = self.mat_group_var.get() if self.mat_group_var.get() != "全部" else None
        start_month = self.start_month_var.get().strip() or None
        end_month = self.end_month_var.get().strip() or None
        search_text = self.search_var.get().strip() or None

        try:
            df = self.db.query_summary(
                plant_code=plant,
                group_category=category,
                material_group=mat_group,
                start_month=start_month,
                end_month=end_month,
                search_text=search_text
            )
            self.current_data = df
            self._refresh_table(df)
            self._update_stats_cards(df)
            self.status_label.config(text=f"查询完成，共 {len(df)} 条记录")
        except Exception as e:
            messagebox.showerror("查询错误", f"查询数据失败：{e}")

    def _refresh_table(self, df):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if df is None or df.empty:
            self.row_count_label.config(text="0 条记录")
            return
        for _, row in df.iterrows():
            closing_amount = f"¥{row['closing_amount']:,.2f}" if pd.notna(row['closing_amount']) else ""
            outbound_amount = f"¥{abs(row['outbound_amount']):,.2f}" if pd.notna(row['outbound_amount']) else ""
            turnover_days = f"{row['turnover_days']:.1f}" if pd.notna(row['turnover_days']) else ""
            values = (
                row['group_warehouse_category'],
                row['material_code'],
                row['material_desc'],
                row['unit'],
                f"{row['closing_qty']:.2f}" if pd.notna(row['closing_qty']) else "",
                closing_amount,
                outbound_amount,
                turnover_days,
                row.get('flags', '') or ""
            )
            self.tree.insert("", "end", values=values)
        self.row_count_label.config(text=f"{len(df)} 条记录")

    def _update_stats_cards(self, df):
        if df is None or df.empty:
            self.total_amount_card.value_label.config(text="¥0.00")
            self.total_materials_card.value_label.config(text="0")
            self.turnover_days_card.value_label.config(text="0天")
            self.abnormal_card.value_label.config(text="0")
            if hasattr(self.abnormal_card, 'alert_dot'):
                self.abnormal_card.alert_dot.place_forget()
            return
        total_amount = df['closing_amount'].sum()
        self.total_amount_card.value_label.config(text=f"¥{total_amount:,.2f}")
        total_materials = df['material_code'].nunique()
        self.total_materials_card.value_label.config(text=f"{total_materials}")
        total_outbound = df['outbound_amount'].abs().sum()
        if total_outbound > 0:
            turnover_days = (total_amount / total_outbound) * 30
            self.turnover_days_card.value_label.config(text=f"{turnover_days:.1f}天")
        else:
            self.turnover_days_card.value_label.config(text="N/A")
        abnormal_count = df['flags'].astype(str).str.strip().ne('').sum() if 'flags' in df.columns else 0
        self.abnormal_card.value_label.config(text=str(abnormal_count))
        if abnormal_count > 0 and hasattr(self.abnormal_card, 'alert_dot'):
            self.abnormal_card.alert_dot.place(x=5, y=5)
        elif hasattr(self.abnormal_card, 'alert_dot'):
            self.abnormal_card.alert_dot.place_forget()

    def _sort_by_column(self, col, reverse):
        if self.current_data is None or self.current_data.empty:
            return
        col_map = {
            "group_warehouse_category": "group_warehouse_category",
            "material_code": "material_code",
            "material_desc": "material_desc",
            "unit": "unit",
            "closing_qty": "closing_qty",
            "closing_amount": "closing_amount",
            "outbound_amount": "outbound_amount",
            "turnover_days": "turnover_days",
            "flags": "flags"
        }
        df_col = col_map.get(col)
        if df_col is None:
            return
        self.current_data = self.current_data.sort_values(by=df_col, ascending=not reverse)
        self._refresh_table(self.current_data)

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        menu = tk.Menu(self.window, tearoff=0)
        menu.add_command(label="导出选中行", command=self._export_selected_rows)
        menu.add_command(label="复制物料号", command=self._copy_material_code)
        menu.add_separator()
        menu.add_command(label="刷新", command=self._on_filter_changed)
        menu.post(event.x_root, event.y_root)

    def _export_selected_rows(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选中要导出的行")
            return
        selected_data = [self.tree.item(item, 'values') for item in selected]
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel文件", "*.xlsx")])
        if file_path:
            columns = [self.tree.heading(c)['text'] for c in self.tree['columns']]
            df_export = pd.DataFrame(selected_data, columns=columns)
            df_export.to_excel(file_path, index=False)
            messagebox.showinfo("导出成功", f"已导出 {len(selected)} 条记录到 {file_path}")

    def _copy_material_code(self):
        selected = self.tree.selection()
        if not selected:
            return
        codes = []
        for item in selected:
            values = self.tree.item(item, 'values')
            if len(values) > 1:
                codes.append(values[1])
        if codes:
            self.window.clipboard_clear()
            self.window.clipboard_append("\n".join(codes))
            self.status_label.config(text=f"已复制 {len(codes)} 个物料号到剪贴板")

    def _on_row_double_click(self, event):
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            values = self.tree.item(item, 'values')
            material_code = values[1] if len(values) > 1 else None
            if material_code:
                self.status_label.config(text=f"双击物料 {material_code}，联动功能待实现")

    def _reset_filters(self):
        self.plant_var.set("全部")
        self.category_var.set("全部")
        self.mat_group_var.set("全部")
        self.start_month_var.set("")
        self.end_month_var.set("")
        self.search_var.set("")
        self._on_filter_changed()

    def on_close(self):
        self.db.close()
        self.window.destroy()

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = StockSummaryWindow()
    app.show()
    tk.mainloop()