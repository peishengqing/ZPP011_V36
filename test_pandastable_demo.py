# -*- coding: utf-8 -*-
"""pandastable 技术验证 Demo - 5000行模拟数据，行颜色规则 + 批量备注"""

import tkinter as tk
from tkinter import simpledialog, messagebox
import pandas as pd
import numpy as np
from pandastable import Table, TableModel
from datetime import datetime, timedelta
import random

# ── 模拟数据生成 ──────────────────────────────────────────────
def generate_mock_data(n=5000):
    np.random.seed(42)
    random.seed(42)
    factories = ["1000", "2000", "3000"]
    workshops = ["A01", "A02", "B01", "B02", "C01"]
    units = ["KG", "M", "EA", "L", "M2"]
    sources = ["AI审核合格", "自动填充", "人工填写", ""]
    results = ["通过", "未通过", "待审核"]
    base = datetime(2025, 1, 1)
    rows = []
    for i in range(n):
        order_date = base + timedelta(days=random.randint(0, 180))
        process_order = f"PO{random.randint(100000, 999999)}"
        mat_code = f"MAT{random.randint(10000, 99999)}"
        quota = round(random.uniform(10, 5000), 2)
        actual = round(quota * random.uniform(0.3, 1.7), 2)
        diff = round(actual - quota, 2)
        rate = round((diff / quota) * 100, 2) if quota != 0 else 0
        amt = round(diff * random.uniform(1, 10), 2)
        src = random.choice(sources)
        reason = ""
        if src == "AI审核合格":
            reason = random.choice(["模型校验通过", "历史数据匹配", "规则引擎判定"])
        elif src == "自动填充":
            reason = "系统自动补全"
        elif src == "人工填写":
            reason = random.choice(["工艺调整", "材料替换", "紧急变更"])
        rows.append({
            "订单日期": order_date.strftime("%Y-%m-%d"),
            "流程订单": process_order,
            "工厂": random.choice(factories),
            "车间": random.choice(workshops),
            "物料编码": mat_code,
            "物料名称": f"物料_{mat_code}",
            "组件物料描述": f"组件描述_{i}",
            "单位": random.choice(units),
            "数量-定额": quota,
            "数量-实际": actual,
            "材料偏差": diff,
            "偏差率(%)": rate,
            "备注来源": src,
            "备注原因": reason,
            "审核结果": random.choice(results),
            "偏差金额": amt,
        })
    return pd.DataFrame(rows)

# ── 业务主键工具 ──────────────────────────────────────────────
def make_key(row):
    """提取业务主键: 订单日期+流程订单+物料编码"""
    return (str(row.get("订单日期", "")), str(row.get("流程订单", "")), str(row.get("物料编码", "")))

# ── 颜色规则 ──────────────────────────────────────────────────
def row_color(df, idx):
    """返回 (bg, fg) 颜色元组，优先级从高到低"""
    r = df.iloc[idx]
    rate = r.get("偏差率(%)", 0)
    src = r.get("备注来源", "")
    amt = abs(r.get("偏差金额", 0))
    # 优先级1: 偏差率绝对值>50% 橙色
    if abs(rate) > 50:
        return ("#FFA500", "black")
    # 优先级2: 人工填写且偏差金额>5000 浅黄
    if src == "人工填写" and amt > 5000:
        return ("#FFFF99", "black")
    # 优先级3: AI审核合格 浅绿
    if src == "AI审核合格":
        return ("#C6EFCE", "black")
    # 优先级4: 自动填充 浅灰
    if src == "自动填充":
        return ("#D9D9D9", "black")
    # 优先级5: 正偏差 浅红
    if rate > 1:
        return ("#FFC7CE", "black")
    # 优先级6: 负偏差 浅蓝
    if rate < -1:
        return ("#CCE5FF", "black")
    return ("white", "black")

# ── 主应用 ────────────────────────────────────────────────────
class PandaTableDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("pandastable 技术验证 Demo (5000行)")
        self.geometry("1400x750")
        self.df = generate_mock_data(5000)
        self._build_key_map()
        self._build_ui()

    def _build_key_map(self):
        """构建 行索引 → 业务主键 映射"""
        self.key_map = {i: make_key(self.df.iloc[i]) for i in range(len(self.df))}
        self.key_to_indices = {}
        for i, k in self.key_map.items():
            self.key_to_indices.setdefault(k, []).append(i)

    def _build_ui(self):
        # 状态栏
        self.status_var = tk.StringVar(value="就绪 | 总行数: 5000")
        status_bar = tk.Label(self, textvariable=self.status_var, anchor="w",
                              relief="sunken", bd=1, font=("Microsoft YaHei", 10))
        status_bar.pack(side="bottom", fill="x")

        # 表格容器
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True)

        self.table = Table(frame, dataframe=self.df.copy(), showtoolbar=False, showstatusbar=False)
        self.table.show()

        # 应用颜色
        self._apply_colors()

        # 绑定选择和右键
        self.table.bind("<ButtonRelease-1>", self._on_select)
        self.table.bind("<Button-3>", self._on_right_click)

        # 自定义右键菜单
        self.popup = tk.Menu(self, tearoff=0)
        self.popup.add_command(label="📝 批量备注（选中行）", command=self._batch_remark)

    def _apply_colors(self):
        """逐行设置颜色"""
        model = self.table.model
        for i in range(len(self.df)):
            bg, fg = row_color(self.df, i)
            self.table.setRowColors(rows=[i], bg=bg, fg=fg, cols=list(range(len(self.df.columns))))
        self.table.redrawVisible()

    def _on_select(self, event=None):
        """更新状态栏"""
        sel = self.table.multirowlist if hasattr(self.table, 'multirowlist') else []
        if not sel:
            # 尝试从 currentrow 获取
            try:
                cr = self.table.currentrow
                sel = [cr] if cr is not None else []
            except:
                sel = []
        count = len(sel)
        if count > 0 and count <= 10:
            keys = [self.key_map.get(s, ("?", "?", "?")) for s in sel if s in self.key_map]
            key_str = "; ".join(f"{k[0]}|{k[1]}|{k[2]}" for k in keys)
            self.status_var.set(f"选中 {count} 行 | 主键: {key_str}")
        elif count > 10:
            self.status_var.set(f"选中 {count} 行 | (主键过多，省略显示)")
        else:
            self.status_var.set(f"就绪 | 总行数: {len(self.df)}")

    def _on_right_click(self, event=None):
        """右键弹出菜单"""
        # pandastable 的选中行
        try:
            row_clicked = self.table.get_row_clicked(event)
            if row_clicked is not None:
                # 确保右键行被选中
                if hasattr(self.table, 'multirowlist') and row_clicked not in self.table.multirowlist:
                    self.table.multirowlist = [row_clicked]
        except:
            pass
        self.popup.tk_popup(event.x_root, event.y_root)

    def _get_selected_rows(self):
        """获取选中行索引列表"""
        if hasattr(self.table, 'multirowlist') and self.table.multirowlist:
            return list(self.table.multirowlist)
        try:
            cr = self.table.currentrow
            return [cr] if cr is not None else []
        except:
            return []

    def _batch_remark(self):
        """批量备注功能"""
        sel_rows = self._get_selected_rows()
        if not sel_rows:
            messagebox.showwarning("提示", "请先选中行再进行批量备注！")
            return

        # 通过行索引→业务主键映射，排序后也不怕错位
        keys = [self.key_map.get(r) for r in sel_rows if r in self.key_map]
        if not keys:
            messagebox.showwarning("提示", "无法获取选中行的业务主键！")
            return

        # 弹出输入框
        remark = simpledialog.askstring("批量备注", f"已选中 {len(keys)} 行\n请输入备注原因：", parent=self)
        if remark is None or remark.strip() == "":
            return

        # 通过业务主键更新内存数据
        updated = 0
        for key in keys:
            for idx in self.key_to_indices.get(key, []):
                self.df.at[idx, "备注来源"] = "人工填写"
                self.df.at[idx, "备注原因"] = remark
                updated += 1

        # 刷新表格数据和颜色
        self.table.model.df = self.df.copy()
        self.table.redraw()
        self._apply_colors()

        messagebox.showinfo("完成", f"已更新 {updated} 行的备注信息")

if __name__ == "__main__":
    app = PandaTableDemo()
    app.mainloop()