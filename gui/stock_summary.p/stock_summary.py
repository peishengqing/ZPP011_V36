"""
S01 模块：云南达利收发存汇总
Phase 1 - 基础查询界面
功能：数据导入后，多维度查询收发存数据，展示明细表格和统计卡片
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import Toplevel
import pandas as pd
from datetime import datetime
import os
import sys

# 添加项目根目录到路径（以便导入storage模块）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.stock_db import StockDatabase
from config.themes import C  # 统一配色方案


class StockSummaryWindow:
    """收发存汇总主窗口"""

    def __init__(self, parent=None):
        self.parent = parent
        self.db = StockDatabase()
        self.current_data = None  # 当前显示的DataFrame
        self.current_month = None  # 当前选中的月份

        # 创建独立顶级窗口
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("云南达利收发存汇总 - S01")
        self.window.geometry("1400x800")
        self.window.configure(bg=C["surface"])

        # 设置窗口图标（如果有）
        # self.window.iconbitmap('assets/icon.ico')

        # 绑定关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        # 初始化UI
        self._build_ui()

        # 加载最新月份数据
        self._load_latest_month()

    def _build_ui(self):
        """构建主界面"""
        # 主框架
        main_frame = tk.Frame(self.window, bg=C["surface"])
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. 筛选栏
        self._build_filter_bar(main_frame)

        # 2. 统计卡片区
        self._build_stats_cards(main_frame)

        # 3. 明细表格
        self._build_table(main_frame)

        # 4. 状态栏
        self._build_status_bar(main_frame)

    def _build_filter_bar(self, parent):
        """构建筛选栏"""
        filter_frame = tk.LabelFrame(
            parent,
            text="筛选条件",
            bg=C["surface"],
            fg=C["text"],
            font=("Microsoft YaHei", 10, "bold"),
        )
        filter_frame.pack(fill="x", pady=(0, 10))

        # 使用Grid布局，多行多列
        row = 0

        # 工厂
        tk.Label(filter_frame, text="工厂：", bg=C["surface"], fg=C["text"]).grid(
            row=row, column=0, padx=5, pady=5, sticky="e"
        )
        self.plant_var = tk.StringVar(value="全部")
        plant_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.plant_var,
            values=["全部", "1101", "1102"],
            state="readonly",
            width=15,
        )
        plant_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        plant_combo.bind("<<ComboboxSelected>>", lambda e: self._on_filter_changed())

        # 集团仓库分类（多选，暂时用下拉单选，后续可升级为Listbox多选）
        tk.Label(
            filter_frame, text="集团仓库分类：", bg=C["surface"], fg=C["text"]
        ).grid(row=row, column=2, padx=5, pady=5, sticky="e")
        self.category_var = tk.StringVar(value="全部")
        self.category_combo = ttk.Combobox(
            filter_frame, textvariable=self.category_var, state="readonly", width=20
        )
        self.category_combo.grid(row=row, column=3, padx=5, pady=5, sticky="w")
        self.category_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._on_filter_changed()
        )
        self._load_category_options()

        # 物料组
        tk.Label(filter_frame, text="物料组：", bg=C["surface"], fg=C["text"]).grid(
            row=row, column=4, padx=5, pady=5, sticky="e"
        )
        self.mat_group_var = tk.StringVar(value="全部")
        self.mat_group_combo = ttk.Combobox(
            filter_frame, textvariable=self.mat_group_var, state="readonly", width=25
        )
        self.mat_group_combo.grid(row=row, column=5, padx=5, pady=5, sticky="w")
        self.mat_group_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._on_filter_changed()
        )
        self._load_material_group_options()

        row += 1

        # 月份范围
        tk.Label(filter_frame, text="起始月份：", bg=C["surface"], fg=C["text"]).grid(
            row=row, column=0, padx=5, pady=5, sticky="e"
        )
        self.start_month_var = tk.StringVar()
        start_entry = ttk.Entry(
            filter_frame, textvariable=self.start_month_var, width=12
        )
        start_entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        start_entry.bind("<KeyRelease>", lambda e: self._on_filter_changed())

        tk.Label(filter_frame, text="结束月份：", bg=C["surface"], fg=C["text"]).grid(
            row=row, column=2, padx=5, pady=5, sticky="e"
        )
        self.end_month_var = tk.StringVar()
        end_entry = ttk.Entry(filter_frame, textvariable=self.end_month_var, width=12)
        end_entry.grid(row=row, column=3, padx=5, pady=5, sticky="w")
        end_entry.bind("<KeyRelease>", lambda e: self._on_filter_changed())

        # 搜索框（物料号/描述）
        tk.Label(filter_frame, text="搜索：", bg=C["surface"], fg=C["text"]).grid(
            row=row, column=4, padx=5, pady=5, sticky="e"
        )
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(
            filter_frame,
            textvariable=self.search_var,
            font=("Microsoft YaHei", 9),
            bg=C["surface2"],
            fg=C["text"],
        )
        search_entry.grid(row=row, column=5, padx=5, pady=5, sticky="we")
        search_entry.bind("<KeyRelease>", lambda e: self._on_filter_changed())

        # 查询按钮和重置按钮
        btn_frame = tk.Frame(filter_frame, bg=C["surface"])
        btn_frame.grid(row=row, column=6, padx=10, pady=5, sticky="e")
        tk.Button(
            btn_frame,
            text="查询",
            command=self._on_filter_changed,
            bg=C["accent"],
            fg="white",
            width=8,
        ).pack(side="left", padx=2)
        tk.Button(
            btn_frame,
            text="重置",
            command=self._reset_filters,
            bg=C["surface2"],
            fg=C["text"],
            width=8,
        ).pack(side="left", padx=2)

        # 配置网格权重
        filter_frame.columnconfigure(5, weight=1)

    def _build_stats_cards(self, parent):
        """构建统计卡片区"""
        card_frame = tk.Frame(parent, bg=C["surface"])
        card_frame.pack(fill="x", pady=(0, 10))

        # 期末总库存金额卡片
        self.total_amount_card = self._create_card(
            card_frame, "期末总库存金额", "¥0.00", 0
        )
        self.total_amount_card.pack(side="left", expand=True, fill="x", padx=5)

        # 总物料种类卡片
        self.total_materials_card = self._create_card(card_frame, "总物料种类", "0", 1)
        self.total_materials_card.pack(side="left", expand=True, fill="x", padx=5)

        # 整体周转天数卡片
        self.turnover_days_card = self._create_card(
            card_frame, "整体周转天数", "0天", 2
        )
        self.turnover_days_card.pack(side="left", expand=True, fill="x", padx=5)

        # 异常计数卡片（红点标识）
        self.abnormal_card = self._create_card(
            card_frame, "异常物料数", "0", 3, alert=True
        )
        self.abnormal_card.pack(side="left", expand=True, fill="x", padx=5)

    def _create_card(self, parent, title, value, column, alert=False):
        """创建单个统计卡片"""
        frame = tk.Frame(parent, bg=C["surface2"], relief="ridge", bd=1)
        frame.columnconfigure(0, weight=1)

        title_label = tk.Label(
            frame,
            text=title,
            font=("Microsoft YaHei", 9),
            bg=C["surface2"],
            fg=C["text_secondary"],
        )
        title_label.grid(row=0, column=0, pady=(8, 0))

        value_label = tk.Label(
            frame,
            text=value,
            font=("Microsoft YaHei", 18, "bold"),
            bg=C["surface2"],
            fg=C["text"],
        )
        value_label.grid(row=1, column=0, pady=(5, 8))

        if alert:
            # 红点指示器（初始隐藏）
            alert_dot = tk.Label(
                frame, text="●", fg="red", bg=C["surface2"], font=("Arial", 10)
            )
            alert_dot.place(x=5, y=5)
            alert_dot.place_forget()
            frame.alert_dot = alert_dot

        frame.title = title
        frame.value_label = value_label
        return frame

    def _build_table(self, parent):
        """构建明细表格"""
        table_frame = tk.Frame(parent, bg=C["surface"])
        table_frame.pack(fill="both", expand=True)

        # 创建Treeview和滚动条
        columns = (
            "group_warehouse_category",
            "material_code",
            "material_desc",
            "unit",
            "closing_qty",
            "closing_amount",
            "outbound_amount",
            "turnover_days",
            "flags",
        )
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=20
        )

        # 定义列标题和宽度
        col_config = {
            "group_warehouse_category": ("集团仓库分类", 150),
            "material_code": ("物料号", 120),
            "material_desc": ("物料描述", 250),
            "unit": ("单位", 60),
            "closing_qty": ("期末数量", 100, "right"),
            "closing_amount": ("期末金额(¥)", 120, "right"),
            "outbound_amount": ("本月出库金额(¥)", 120, "right"),
            "turnover_days": ("周转天数", 80, "right"),
            "flags": ("异常标记", 150),
        }

        for col, config in col_config.items():
            self.tree.heading(
                col,
                text=config[0],
                command=lambda c=col: self._sort_by_column(c, False),
            )
            self.tree.column(
                col, width=config[1], anchor=config[2] if len(config) > 2 else "center"
            )

        # 滚动条
        v_scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
        h_scrollbar = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 绑定右键菜单
        self.tree.bind("<Button-3>", self._show_context_menu)

        # 双击事件（预留联动）
        self.tree.bind("<Double-1>", self._on_row_double_click)

    def _build_status_bar(self, parent):
        """构建底部状态栏"""
        status_frame = tk.Frame(parent, bg=C["surface"], height=25)
        status_frame.pack(fill="x", side="bottom")
        self.status_label = tk.Label(
            status_frame,
            text="就绪",
            anchor="w",
            bg=C["surface"],
            fg=C["text_secondary"],
        )
        self.status_label.pack(side="left", padx=5)

        self.row_count_label = tk.Label(
            status_frame,
            text="0 条记录",
            anchor="e",
            bg=C["surface"],
            fg=C["text_secondary"],
        )
        self.row_count_label.pack(side="right", padx=5)

    def _load_category_options(self):
        """加载集团仓库分类下拉选项"""
        categories = self.db.get_distinct_categories()
        values = ["全部"] + sorted(categories)
        self.category_combo["values"] = values
        if values:
            self.category_var.set("全部")

    def _load_material_group_options(self):
        """加载物料组下拉选项"""
        groups = self.db.get_distinct_material_groups()
        values = ["全部"] + sorted(groups)
        self.mat_group_combo["values"] = values
        if values:
            self.mat_group_var.set("全部")

    def _load_latest_month(self):
        """加载最新月份数据并刷新表格"""
        latest_month = self.db.get_latest_month()
        if latest_month:
            # 设置月份范围默认值为最新月份
            self.start_month_var.set(latest_month)
            self.end_month_var.set(latest_month)
            self._on_filter_changed()
        else:
            self.status_label.config(text="未找到任何数据，请先导入ZMM062报表")
            self.row_count_label.config(text="0 条记录")

    def _on_filter_changed(self):
        """筛选条件变化时刷新数据"""
        # 获取筛选条件
        plant = self.plant_var.get()
        if plant == "全部":
            plant = None
        category = self.category_var.get()
        if category == "全部":
            category = None
        mat_group = self.mat_group_var.get()
        if mat_group == "全部":
            mat_group = None
        start_month = self.start_month_var.get().strip()
        end_month = self.end_month_var.get().strip()
        search_text = self.search_var.get().strip()

        # 查询数据
        try:
            df = self.db.query_summary(
                plant_code=plant,
                group_category=category,
                material_group=mat_group,
                start_month=start_month if start_month else None,
                end_month=end_month if end_month else None,
                search_text=search_text if search_text else None,
            )
            self.current_data = df
            self._refresh_table(df)
            self._update_stats_cards(df)
            self.status_label.config(text=f"查询完成，共 {len(df)} 条记录")
        except Exception as e:
            messagebox.showerror("查询错误", f"查询数据失败：{e}")
            self.status_label.config(text="查询失败")

    def _refresh_table(self, df):
        """刷新表格内容"""
        # 清空现有数据
        for item in self.tree.get_children():
            self.tree.delete(item)

        if df is None or df.empty:
            self.row_count_label.config(text="0 条记录")
            return

        # 插入数据
        for _, row in df.iterrows():
            # 格式化金额
            closing_amount = (
                f"¥{row['closing_amount']:,.2f}"
                if pd.notna(row["closing_amount"])
                else ""
            )
            outbound_amount = (
                f"¥{abs(row['outbound_amount']):,.2f}"
                if pd.notna(row["outbound_amount"])
                else ""
            )
            turnover_days = (
                f"{row['turnover_days']:.1f}" if pd.notna(row["turnover_days"]) else ""
            )

            values = (
                row["group_warehouse_category"],
                row["material_code"],
                row["material_desc"],
                row["unit"],
                f"{row['closing_qty']:.2f}" if pd.notna(row["closing_qty"]) else "",
                closing_amount,
                outbound_amount,
                turnover_days,
                row.get("flags", "") or "",
            )
            self.tree.insert("", "end", values=values)

        self.row_count_label.config(text=f"{len(df)} 条记录")

    def _update_stats_cards(self, df):
        """更新统计卡片"""
        if df is None or df.empty:
            self.total_amount_card.value_label.config(text="¥0.00")
            self.total_materials_card.value_label.config(text="0")
            self.turnover_days_card.value_label.config(text="0天")
            self.abnormal_card.value_label.config(text="0")
            if hasattr(self.abnormal_card, "alert_dot"):
                self.abnormal_card.alert_dot.place_forget()
            return

        # 期末总金额
        total_amount = (
            df["closing_amount"].sum() if "closing_amount" in df.columns else 0
        )
        self.total_amount_card.value_label.config(text=f"¥{total_amount:,.2f}")

        # 总物料种类
        total_materials = (
            df["material_code"].nunique() if "material_code" in df.columns else 0
        )
        self.total_materials_card.value_label.config(text=f"{total_materials}")

        # 整体周转天数 = 期末总金额 / 出库总金额 * 30
        total_outbound = (
            df["outbound_amount"].abs().sum() if "outbound_amount" in df.columns else 0
        )
        if total_outbound > 0:
            turnover_days = (total_amount / total_outbound) * 30
            self.turnover_days_card.value_label.config(text=f"{turnover_days:.1f}天")
        else:
            self.turnover_days_card.value_label.config(text="N/A")

        # 异常计数（flags字段非空且非空字符串）
        if "flags" in df.columns:
            abnormal_count = df["flags"].astype(str).str.strip().ne("").sum()
        else:
            abnormal_count = 0
        self.abnormal_card.value_label.config(text=str(abnormal_count))
        if abnormal_count > 0 and hasattr(self.abnormal_card, "alert_dot"):
            self.abnormal_card.alert_dot.place(x=5, y=5)
        elif hasattr(self.abnormal_card, "alert_dot"):
            self.abnormal_card.alert_dot.place_forget()

    def _sort_by_column(self, col, reverse):
        """表格列排序"""
        if self.current_data is None or self.current_data.empty:
            return
        # 获取当前列对应的DataFrame列名
        col_map = {
            "group_warehouse_category": "group_warehouse_category",
            "material_code": "material_code",
            "material_desc": "material_desc",
            "unit": "unit",
            "closing_qty": "closing_qty",
            "closing_amount": "closing_amount",
            "outbound_amount": "outbound_amount",
            "turnover_days": "turnover_days",
            "flags": "flags",
        }
        df_col = col_map.get(col)
        if df_col is None:
            return
        # 排序
        self.current_data = self.current_data.sort_values(
            by=df_col, ascending=not reverse
        )
        self._refresh_table(self.current_data)
        # 更新列标题箭头（简单实现，可后续优化）
        for c in self.tree["columns"]:
            self.tree.heading(c, text=col_config.get(c, (c,))[0])
        self.tree.heading(col, text=col_config[col][0] + (" ↑" if reverse else " ↓"))

    def _show_context_menu(self, event):
        """显示右键菜单"""
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
        """导出选中行到Excel"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选中要导出的行")
            return
        # 获取选中的数据
        selected_data = []
        for item in selected:
            values = self.tree.item(item, "values")
            # 需要将values映射回原始DataFrame，但为简化，直接构建列表
            # 实际应关联self.current_data，这里简化处理
            selected_data.append(values)
        # 导出
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel文件", "*.xlsx")]
        )
        if file_path:
            df_export = pd.DataFrame(
                selected_data,
                columns=[self.tree.heading(c)["text"] for c in self.tree["columns"]],
            )
            df_export.to_excel(file_path, index=False)
            messagebox.showinfo(
                "导出成功", f"已导出 {len(selected)} 条记录到 {file_path}"
            )

    def _copy_material_code(self):
        """复制物料号到剪贴板"""
        selected = self.tree.selection()
        if not selected:
            return
        codes = []
        for item in selected:
            values = self.tree.item(item, "values")
            # 物料号在第2列（索引1）
            if len(values) > 1:
                codes.append(values[1])
        if codes:
            self.window.clipboard_clear()
            self.window.clipboard_append("\n".join(codes))
            self.status_label.config(text=f"已复制 {len(codes)} 个物料号到剪贴板")

    def _on_row_double_click(self, event):
        """双击行事件（预留联动）"""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            values = self.tree.item(item, "values")
            material_code = values[1] if len(values) > 1 else None
            if material_code:
                # TODO: 调用偏差分析模块查看该物料历史偏差
                self.status_label.config(
                    text=f"双击物料 {material_code}，联动功能待实现"
                )

    def _reset_filters(self):
        """重置所有筛选条件"""
        self.plant_var.set("全部")
        self.category_var.set("全部")
        self.mat_group_var.set("全部")
        self.start_month_var.set("")
        self.end_month_var.set("")
        self.search_var.set("")
        self._on_filter_changed()

    def on_close(self):
        """关闭窗口时的清理"""
        self.db.close()
        self.window.destroy()

    def show(self):
        """显示窗口"""
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()


# 独立运行测试
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    app = StockSummaryWindow()
    app.show()
     tk.mainloop()
