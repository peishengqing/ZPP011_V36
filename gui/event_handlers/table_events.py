# -*- coding: utf-8 -*-
"""表格展示、筛选、排序、双击卡片等事件"""

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os, json
from core.rule_engine import RuleEngine
from widgets import C
from domain.alt_material.alt_manager import save_alt_pairs, load_alt_pairs
import traceback


class TableEvents:
    """表格展示、筛选、排序、双击卡片等事件"""

    def _build_audit_values(self, row, i, mat_category, mat_desc, order_no_val,
                              order_type_val, dev_rate, is_alt, status,
                              remark, batch_remark, audit_result_val,
                              audit_status_val, audit_source_val):
        """
        按 self.audit_tree['columns'] 的顺序动态构建 values 元组，
        彻底避免 cols / heading / values 三处顺序不一致导致的列错位。
        """
        cols = self.audit_tree["columns"]
        vals = []
        if i == 1:
            print(f"[DEBUG] _build_audit_values cols={cols}")
        for col in cols:
            if col == "idx":
                vals.append(i)
            elif col == "excel_row":
                v = row.get("原表行号", row.get("excel_row", 0))
                vals.append(int(v)) if pd.notna(v) else vals.append("")
            elif col == "factory":
                vals.append(str(row.get("工厂", row.get("工厂名称", ""))))
            elif col == "admin":
                vals.append(str(row.get("车间", row.get("生产管理员描述", ""))))
            elif col == "order_date":
                v = str(row.get("订单日期", ""))[:10]
                vals.append(v if pd.notna(row.get("订单日期")) else "")
            elif col == "order_type":
                vals.append(str(row.get("订单类型", "")))
            elif col == "order_no":
                vals.append(order_no_val)
            elif col == "material_category":
                vals.append(mat_category)
            elif col == "code":
                vals.append(str(row.get("物料编码", row.get("组件物料号", ""))))
            elif col == "name":
                vals.append(mat_desc[:30])
            elif col == "unit":
                vals.append(str(row.get("组件单位", row.get("单位", ""))))
            elif col == "quota":
                v = row.get("定额", row.get("数量-定额", 0))
                vals.append(f"{v:.3f}")
            elif col == "actual":
                v = row.get("实际", row.get("数量-实际", 0))
                vals.append(f"{v:.3f}")
            elif col == "dev_rate":
                vals.append(f"{dev_rate:.2f}%" if isinstance(dev_rate, (int, float)) else str(dev_rate))
            elif col == "is_alt":
                vals.append(is_alt)
            elif col == "status":
                vals.append(status)
            elif col == "remark":
                vals.append(remark)
            elif col == "batch_remark":
                vals.append(batch_remark[:30])
            elif col == "audit_result":
                vals.append(audit_result_val)
            elif col == "AI建议":
                v = str(row.get("AI建议", ""))[:50]
                vals.append(v)
            elif col == "audit_status":
                vals.append(audit_status_val)
            elif col == "audit_source":
                vals.append(audit_source_val)
            elif col == "deviation_amount":
                v = row.get("偏差金额", row.get("材料偏差", 0))
                vals.append(f"{v:,.2f}" if isinstance(v, (int, float)) else str(v))
            elif col == "remark_check_status":
                vals.append(str(row.get("remark_check_status", "")))
            elif col == "remark_check_msg":
                vals.append(str(row.get("remark_check_msg", "")))
            else:
                vals.append("")
        return tuple(vals)

    def _refresh_audit_tree(self, df, skip_auto_sort=False):
        """用给定的 DataFrame 刷新智能审核表格"""
        print(f"[DEBUG] _refresh_audit_tree 被调用, df={len(df)}行, skip_auto_sort={skip_auto_sort}")

        # 自动设置日期筛选范围为数据的实际日期范围(仅首次加载时)
        if len(df) > 0 and '订单日期' in df.columns:
            date_col = pd.to_datetime(df['订单日期'], errors='coerce')
            valid_dates = date_col.dropna()
            if len(valid_dates) > 0:
                min_date = valid_dates.min().date()
                max_date = valid_dates.max().date()
                try:
                    self.date_start_de.set_date(min_date)
                    self.date_end_de.set_date(max_date)
                except Exception as e:
                    self.log(f"初始化日期范围失败: {e}", "warn")

        # 【调试】打印列定义和第一行数据

        self.log(f"[DEBUG] cols = {self.audit_tree['columns']}")

        if len(df) > 0:
            first = df.iloc[0]

            self.log(
                f"[DEBUG] 第一行数据样例: idx={first.name}, "
                + ", ".join(
                    [
                        f"{c}={first.get(c, '?')}"
                        for c in [
                            "工厂",
                            "车间",
                            "订单日期",
                            "流程订单",
                            "物料编码",
                            "物料名称",
                            "定额",
                            "实际",
                            "偏差率",
                        ]
                        if c in first.index
                    ]
                )
            )

        self.log(f"[DEBUG] _refresh_audit_tree: df={len(df)}行", "info")

        # AI建议列诊断

        if "AI建议" not in df.columns:
            self.log("[WARN] DataFrame中没有'AI建议'列!", "warn")

        else:
            non_empty = df["AI建议"].notna().sum()

            self.log(f"[DEBUG] AI建议列非空: {non_empty}/{len(df)}", "info")

            if non_empty > 0:
                sample = str(df["AI建议"].dropna().iloc[0])[:80]

                self.log(f"[DEBUG] AI建议示例: {sample}", "info")

        # 确保 audit_result 和 AI建议 列存在(在副本上操作,不影响原始数据)

        df = df.copy()

        for col in ("audit_result", "AI建议"):
            if col not in df.columns:
                df[col] = ""

        for row in self.audit_tree.get_children():
            self.audit_tree.delete(row)

        if df is None or len(df) == 0:
            return

        # ── 性能优化:暂停绘制,批量插入后再恢复 ──
        # 原代码 try/pass/except 会吞异常，已移除

        # ── P1:智能优先级标记 ──

        def calc_priority(row):

            if not hasattr(self, "rule_engine"):
                self.rule_engine = RuleEngine()

            dev = abs(float(row.get("偏差率(%)", 0) or 0))

            has_note = (
                pd.notna(row.get("备注原因"))
                and str(row.get("备注原因", "")).strip() != ""
            )

            level = self.rule_engine.get_level_for_deviation_rate(dev)

            # level: info/warning/error -> map to label

            if level == "error":
                label = self.config.get("priority.red_label", "红")

                order = 0 if not has_note else 1

            elif level == "warning":
                label = self.config.get("priority.yellow_label", "黄")

                order = 2 if not has_note else 3

            else:
                label = self.config.get("priority.green_label", "绿")

                order = 4

            return order, label

        df = df.copy()

        df[["_priority_order", "_priority_label"]] = df.apply(
            lambda r: pd.Series(calc_priority(r)), axis=1
        )

        if not skip_auto_sort:
            df = df.sort_values("_priority_order")

        # ── P1:金额排名着色 ──

        amount_col = None

        if "偏差金额" in df.columns:
            amount_col = "偏差金额"

        elif "偏差金额(含税)" in df.columns:
            amount_col = "偏差金额(含税)"

        else:
            amount_col = "_dev_qty_abs"

            df = df.copy()

            df["_dev_qty_abs"] = pd.to_numeric(df["偏差数量"], errors="coerce").abs()

        rank_dict = {}

        if "物料分类" in df.columns and amount_col:
            for cat, grp in df.groupby("物料分类"):
                grp_sorted = grp.sort_values(amount_col, ascending=False, key=abs)

                top3 = grp_sorted.head(3).index.tolist()

                next7 = (
                    grp_sorted.iloc[3:10].index.tolist() if len(grp_sorted) > 3 else []
                )

                for idx in top3:
                    rank_dict[idx] = "amt_rank_1"

                for idx in next7:
                    rank_dict[idx] = "amt_rank_2"

        # 构建替代料名称集合(提取name用于匹配)

        alt_all_descs = set()

        for a, b in getattr(self, "alt_pairs", []):

            def _extract_desc(item):

                if isinstance(item, (list, tuple)):
                    if len(item) >= 3:
                        return str(item[2]).strip() if item[2] else ""

                    if len(item) == 2:
                        return str(item[1]).strip() if item[1] else ""

                    return str(item[0]).strip() if item[0] else ""

                return str(item).strip()

            da, db = _extract_desc(a), _extract_desc(b)

            if da:
                alt_all_descs.add(da)

            if db:
                alt_all_descs.add(db)

        self.log(
            f"[DEBUG] 替代料描述集合({len(alt_all_descs)}): {list(alt_all_descs)[:5]}...",
            "info",
        )

        # ── 填充 Tree(按优先级排序) ──

        # ── 计算物料大类列(插入Tree前先加到DataFrame,确保筛选可用) ──
        def _get_mat_category(code):
            if not code:
                return ""
            prefix = str(code)[:3]
            mat_map = {
                "100": "原辅料", "200": "包材",
                "400": "食品辅料/食品半成品", "410": "饮料辅料/饮料半成品",
                "500": "食品成品", "510": "饮料成品", "600": "促销品",
            }
            return mat_map.get(prefix, prefix)

        code_col = next((c for c in ['物料编码', '组件物料号'] if c in df.columns), None)
        if code_col and 'material_category' not in df.columns:
            df['material_category'] = df[code_col].apply(_get_mat_category)

        # ── 注意:下拉框选项不再这里动态更新,改为在数据加载时一次性设置 ──
        # 原因:如果基于当前 df(可能是筛选后的子集)更新选项,会导致下拉框选项随筛选结果一起变少
        # 正确做法:基于 self.full_audit_data(全量数据)在 _update_filter_options 中设置一次

        for i, (_, row) in enumerate(df.iterrows(), 1):
            # ===== 计算审核来源(核心逻辑)=====

            remark = str(row.get("备注原因", "")).strip()

            code = str(row.get("物料编码", row.get("组件物料号", "")))

            # ===== 物料大类分类 =====
            mat_code_prefix = code[:3] if code else ""
            mat_category_map = {
                "100": "原辅料",
                "200": "包材",
                "400": "食品辅料/食品半成品",
                "410": "饮料辅料/饮料半成品",
                "500": "食品成品",
                "510": "饮料成品",
                "600": "促销品",
            }
            mat_category = mat_category_map.get(mat_code_prefix, mat_code_prefix)

            name = str(row.get("组件物料描述", row.get("物料名称", ""))).strip()

            stored_source = str(row.get("备注来源", ""))

            if remark:
                if stored_source in (
                    "人工填写",
                    "自动填充",
                    "替代料",
                    "AI审核合格",
                    "AI审核待改进",
                    "AI生成",
                ):
                    audit_source = stored_source

                else:
                    audit_source = "人工填写"

            else:
                if "透明胶" in name:
                    audit_source = "自动填充"

                elif str(code).startswith("600"):
                    audit_source = "自动填充"

                elif name in alt_all_descs:
                    audit_source = "替代料"

                else:
                    audit_source = "AI审核"

            if stored_source and stored_source != audit_source:
                audit_source = stored_source

            dev_rate = row.get("偏差率(%)", 0) or 0

            # 原备注

            orig_remark = (
                str(row.get("备注原因", "")) if pd.notna(row.get("备注原因")) else ""
            )

            if orig_remark in ("nan", "NaN", "None"):
                orig_remark = ""

            # 批量备注

            batch_remark = (
                str(row.get("批量备注原因", ""))
                if pd.notna(row.get("批量备注原因"))
                else ""
            )

            if batch_remark in ("nan", "NaN", "None"):
                batch_remark = ""

            # 备注来源

            note_src = str(row.get("备注来源", ""))

            if note_src in ("nan", "NaN", "None"):
                note_src = ""

            has_note = orig_remark.strip() != "" or batch_remark.strip() != ""

            # 状态(简单状态,不含审核结论)

            if note_src == "AI生成":
                dev_dir = float(dev_rate or 0)

                status = f"AI生成{'↑' if dev_dir > 0 else '↓'}"

            elif note_src in ("人工填写", "系统无定额(广宣)", "自动填充", "替代料"):
                status = "已备注"

            else:
                # 包括AI审核合格/待改进/建议等,统一按备注内容显示状态

                status = "已备注" if has_note else "需补备注"

            remark = orig_remark[:30]

            mat_desc = str(row.get("组件物料描述", row.get("物料名称", ""))).strip()

            is_alt = "是" if mat_desc and mat_desc in alt_all_descs else ""

            # audit_status, audit_source, order_no

            audit_result_val = str(row.get("audit_result", ""))

            audit_status_val = (
                "已审核"
                if audit_result_val and audit_result_val.strip() not in ("", "nan")
                else "未审核"
            )

            audit_source_val = audit_source

            if audit_source_val in ("nan", "NaN", "None", ""):
                # 尝试从备注来源推断

                note_source = str(row.get("备注来源", ""))

                if note_source in ("AI审核合格", "AI审核待改进", "AI生成"):
                    audit_source_val = "AI审核"

                elif note_source == "人工填写":
                    audit_source_val = "手动"

                elif note_source == "替代料":
                    audit_source_val = "替代料"

                else:
                    audit_source_val = ""  # 未经过审核的行,来源应为空

            order_no_val = ""

            for _col in ["流程订单", "订单号", "订单编号"]:
                if _col in row.index and pd.notna(row.get(_col)):
                    order_no_val = str(row.get(_col))

                    break

            # 获取订单类型
            order_type_val = ""
            if "订单类型" in row.index:
                order_type_val = str(row.get("订单类型", ""))

            # 用 _build_audit_values 动态构建 values，避免列错位
            try:
                values = self._build_audit_values(
                    row, i, mat_category, mat_desc, order_no_val,
                    order_type_val, dev_rate, is_alt, status,
                    remark, batch_remark, audit_result_val,
                    audit_status_val, audit_source_val
                )
            except Exception as _be:
                print(f"[ERROR] _build_audit_values 第{i}行失败: {_be}")
                import traceback
                traceback.print_exc()
                continue
            try:
                item = self.audit_tree.insert("", "end", values=values)
            except Exception as _ie:
                print(f"[ERROR] insert 第{i}行失败: {_ie}, values数={len(values)}, cols数={len(self.audit_tree['columns'])}")
                import traceback
                traceback.print_exc()
                continue
            if i <= 3:
                print(f"[DEBUG] insert 第{i}行成功, item={item}")

            # Apply remark_check_status tag
            remark_status = row.get("remark_check_status", "")
            if remark_status == "red":
                self.audit_tree.item(
                    item, tags=list(self.audit_tree.item(item, "tags")) + ["remark_red"]
                )
            elif remark_status == "yellow":
                self.audit_tree.item(
                    item,
                    tags=list(self.audit_tree.item(item, "tags")) + ["remark_yellow"],
                )

            # RuleEngine 偏差率颜色

            color_hex = None

            try:
                if hasattr(self, "rule_engine"):
                    color_hex = self.rule_engine.get_color_for_deviation_rate(dev_rate)

                    if color_hex not in self.audit_tree.tag_names():
                        self.audit_tree.tag_configure(color_hex, background=color_hex)

                else:
                    color_hex = None

            except Exception:
                color_hex = None

            # 颜色标签

            if note_src == "自动结案":
                tag = ("auto_closed",)

            elif note_src == "AI生成":
                tag = ("ai_gen",)

            elif note_src in (
                "AI审核合格",
                "人工填写",
                "系统无定额(广宣)",
                "自动填充",
                "替代料",
            ):
                tag = ("ok_note",)

            elif note_src == "AI审核待改进":
                tag = ("need_note",)

            elif not has_note:
                tag = ("need_note",)

            else:
                tag = ("ok_note",)

            mat_code = str(row.get("组件物料号", ""))

            if (
                hasattr(self, "mutation_materials")
                and mat_code in self.mutation_materials
            ):
                tag = ("mutation_alert",) + (tag if isinstance(tag, tuple) else (tag,))

            rank_tag = rank_dict.get(_, None)  # _ 是当前行的原始索引

            if rank_tag:
                tag = (rank_tag,) + (tag if isinstance(tag, tuple) else (tag,))

            # 金额颜色区分:正偏差红色,负偏差绿色

            if dev_rate > 0:
                tag = tag + ("over_amount",)

            elif dev_rate < 0:
                tag = tag + ("under_amount",)

            final_tag = (
                (color_hex,) + tag if color_hex and isinstance(color_hex, str) else tag
            )

            self.audit_tree.item(item, tags=final_tag)

        inserted = len(self.audit_tree.get_children())
        print(f"[DEBUG] _refresh_audit_tree 插入完成, Tree中共有 {inserted} 行")

        # ── 恢复绘制 ──

        try:
            self.audit_tree.configure(
                displaycolumns=[c for c in self.audit_tree["columns"]]
            )

            self.root.update_idletasks()

        except Exception as e:
            self.log(f"恢复表格显示失败: {e}", "error")
            import traceback; self.log(traceback.format_exc(), "error")

        # 确保按钮可用

        if len(df) > 0:
            self._enable_audit_buttons()

        # 绑定右键事件:使用原有 audit_context_menu,追加"复制物料编码"(仅初始化一次)
        if not hasattr(self, "_copy_item_added") and hasattr(
            self, "audit_context_menu"
        ):
            self.audit_context_menu.add_separator()
            self.audit_context_menu.add_command(
                label="📋 复制物料编码", command=self._copy_material_code
            )
            self._copy_item_added = True

    def _show_copy_menu(self, event):
        """显示右键菜单,并选中当前行"""
        item = self.audit_tree.identify_row(event.y)
        if not item:
            return
        # 选中右键点击的行
        self.audit_tree.selection_set(item)
        self.audit_tree.focus(item)
        # 懒初始化菜单
        if not hasattr(self, "copy_menu"):
            self.copy_menu = tk.Menu(self.root, tearoff=0)
            self.copy_menu.add_command(
                label="复制物料编码", command=self._copy_material_code
            )
        self.copy_menu.post(event.x_root, event.y_root)

    def _copy_material_code(self):
        """复制当前选中行的物料编码到剪贴板(通过 audit_data 反查)"""
        selected = self.audit_tree.selection()
        if not selected:
            return
        item = selected[0]

        # 获取原表行号(excel_row)
        values = self.audit_tree.item(item, "values")
        columns = list(self.audit_tree["columns"])

        if "excel_row" not in columns:
            self.log("表格中缺少 excel_row 列,无法复制物料编码", "error")
            return

        excel_row_idx = columns.index("excel_row")
        try:
            excel_row = int(values[excel_row_idx])  # 确保整数
        except (ValueError, TypeError):
            self.log(f"无效的 excel_row 值: {values[excel_row_idx]}", "error")
            return

        # 检查 audit_data 是否包含 excel_row 列
        if self.audit_data is None or "excel_row" not in self.audit_data.columns:
            self.log("数据模型中缺少 excel_row 列,无法复制物料编码", "error")
            return

        # 在 audit_data 中定位行
        row = self.audit_data[self.audit_data["excel_row"] == excel_row]
        if row.empty:
            self.log(f"未找到 excel_row={excel_row} 对应的数据行", "error")
            return

        # 提取物料编码(支持多种列名)
        mat_code = None

        for col in ["物料编码", "组件物料号", "物料号", "code"]:
            if col in row.columns:
                mat_code = row.iloc[0].get(col, "")
                if mat_code:
                    break

        if not mat_code:
            self.log("无法从数据中提取物料编码", "error")
            return

        # 复制到剪贴板
        self.root.clipboard_clear()
        self.root.clipboard_append(str(mat_code))
        self.log(f"已复制物料编码: {mat_code}", "info")

    def _apply_row_colors(self):
        """为所有行应用交替行色"""

        try:
            tree = self.audit_tree

            items = tree.get_children()

            for i, item in enumerate(items):
                existing_tags = list(tree.item(item, "tags") or [])

                existing_tags = [
                    t for t in existing_tags if t not in ("row_even", "row_odd")
                ]

                row_tag = "row_even" if i % 2 == 0 else "row_odd"

                existing_tags.append(row_tag)

                tree.item(item, tags=existing_tags)

        except Exception:
            pass

    # ==================== 隔离区辅助方法 ====================

    # ==================== 列显示名映射 ====================

    _COL_TO_DF = {
        "idx": None,
        "excel_row": "原表行号",
        "factory": "工厂名称",
        "admin": "生产管理员描述",
        "order_date": "订单日期",
        "order_no": "流程订单",
        "code": "物料编码",
        "name": "组件物料描述",
        "quota": "数量-定额",
        "actual": "数量-实际",
        "dev_rate": "偏差率(%)",
        "is_alt": "_is_alt",
        "status": "status_temp",
        "remark": "备注原因",
        "batch_remark": "批量备注原因",
        "audit_result": "audit_result",
        "AI建议": "AI建议",
        "audit_status": "audit_status",
        "audit_source": "audit_source",
        "deviation_amount": "偏差金额",
    }

    _COL_DISPLAY = {
        "idx": "序号",
        "excel_row": "原表行号",
        "factory": "工厂名称",
        "admin": "生产管理员",
        "order_date": "订单日期",
        "order_no": "流程订单",
        "code": "物料号",
        "name": "物料描述",
        "quota": "定额",
        "actual": "实际",
        "dev_rate": "偏差率%",
        "deviation_amount": "偏差金额",
        "is_alt": "替代料",
        "status": "状态",
        "remark": "备注",
        "batch_remark": "批量备注",
        "audit_result": "审核结果",
        "AI建议": "AI建议",
        "audit_status": "审核状态",
        "audit_source": "审核来源",
    }

    def _on_tree_double_click(self, event):
        """双击审核行打开卡片详情(同万能搜索框结果兼容)"""
        print("[DEBUG] 双击事件触发!", event)
        self._show_audit_card(event)

    # ── P1:常用备注自动排序 ──


    def _show_audit_card(self, event):
        selection = self.audit_tree.selection()
        if not selection:
            return
        item = selection[0]

        # 获取 excel_row(从 Treeview 中直接取该列的值)
        excel_row_val = self.audit_tree.set(item, "excel_row")
        if not excel_row_val or excel_row_val == "":
            # 降级:从 item 的 values 中按列索引取
            vals = self.audit_tree.item(item, "values")
            cols = list(self.audit_tree["columns"])
            if "excel_row" in cols:
                idx = cols.index("excel_row")
                if idx < len(vals):
                    excel_row_val = vals[idx]
        if not excel_row_val:
            return

        # 从原始数据中获取完整行数据
        data = {}
        try:
            row_int = int(float(excel_row_val))
            if self.audit_data is not None and "excel_row" in self.audit_data.columns:
                mask = self.audit_data["excel_row"].astype(str).astype(float).astype(int) == row_int
                if mask.any():
                    row_series = self.audit_data[mask].iloc[0]
                    data = row_series.to_dict()
        except Exception:
            pass

        if not data:
            # 如果未找到,降级使用 Treeview 的 values(但可能错位)
            vals = self.audit_tree.item(item, "values")
            cols = list(self.audit_tree["columns"])
            raw = dict(zip(cols, vals))
            # 英文 tree 列名 → 中文 DataFrame 列名（与 display_fields 保持一致）
            _col_to_cn = {
                'excel_row': '原表行号', 'factory': '工厂', 'admin': '车间',
                'order_date': '订单日期', 'order_no': '流程订单',
                'material_category': '物料类型', 'code': '物料编码',
                'name': '物料名称', 'unit': '单位', 'quota': '定额',
                'actual': '实际', 'dev_rate': '偏差率',
                'is_alt': '替代料', 'status': '备注状态',
                'remark': '备注原因', 'batch_remark': '批量备注',
                'audit_result': '审核结果', 'audit_status': '审核状态',
                'audit_source': '审核来源', 'deviation_amount': '偏差金额',
            }
            data = {_col_to_cn.get(k, k): v for k, v in raw.items()}

        # 销毁旧窗口
        if hasattr(self, "_card_win") and self._card_win and self._card_win.winfo_exists():
            self._card_win.destroy()

        self._card_win = tk.Toplevel(self.root)
        self._card_win.title("审核卡片")
        self._card_win.geometry("520x580")
        self._card_win.minsize(450, 500)
        self._card_win.transient(self.root)
        self._card_win.attributes("-topmost", True)

        # 智能位置计算
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        rx = self.root.winfo_rootx() + self.root.winfo_width() + 5
        ry = self.root.winfo_rooty() + 100
        if rx + 520 > screen_width:
            rx = self.root.winfo_rootx() - 525
        if rx < 0:
            rx = 10
        if ry + 580 > screen_height:
            ry = screen_height - 600
        if ry < 0:
            ry = 50
        self._card_win.geometry(f"+{rx}+{ry}")
        self._card_win.lift()
        self._card_win.focus_force()

        card_bg = "#fefefe"
        self._card_win.configure(bg=card_bg)

        tk.Label(self._card_win, text="📋 审核卡片", font=("Microsoft YaHei", 12, "bold"),
                 bg=card_bg).pack(pady=(12, 6))

        text = tk.Text(self._card_win, font=("Microsoft YaHei", 10), bg=card_bg,
                       relief="flat", wrap="word", height=20)
        text.pack(fill="both", expand=True, padx=12, pady=6)

        # 友好字段名映射(使用中文key,和 Treeview 列名一致)
        display_fields = {
            "订单日期": "订单日期",
            "流程订单": "流程订单",
            "工厂": "工厂",
            "车间": "车间",
            "物料类型": "物料类型",
            "物料编码": "物料编码",
            "物料名称": "物料名称",
            "单位": "单位",
            "定额": "定额",
            "实际": "实际",
            "偏差数量": "偏差数量",
            "偏差率": "偏差率",
            "偏差金额": "偏差金额",
            "备注原因": "备注原因",
            "优先级": "优先级",
        }

        # 删除可能引起重复的字段(保留备注原因,删除备注)
        if "备注" in data and "备注原因" in data:
            del data["备注"]

        # 只保留 display_fields 中定义的字段
        filtered_data = {}
        for col_name in display_fields.keys():
            if col_name in data:
                filtered_data[col_name] = data[col_name]

        # 构建显示内容(只使用过滤后的数据)
        lines = []
        for col_name, friendly_name in display_fields.items():
            if col_name not in filtered_data:
                continue
            val = filtered_data[col_name]
            val_str = str(val) if val is not None else ""
            if val_str and val_str not in ("nan", "NaN", "None", ""):
                lines.append(f"{friendly_name}:{val_str}")
        if not lines:
            lines = ["(无数据显示)", f"行ID:{item}"]
        info = "\n".join(lines)

        # 成本换算器（简化版，直接用偏差金额/偏差数量）
        try:
            # 获取偏差金额
            dev_amount_val = None
            for key in ["deviation_amount", "偏差金额"]:
                val = data.get(key)
                if val and str(val).strip() not in ("0", "-", ""):
                    try:
                        dev_amount_val = float(str(val).replace(",", ""))
                        break
                    except:
                        continue
            if dev_amount_val and abs(dev_amount_val) > 0.001:
                # 获取数量偏差（实际-定额）
                dev_qty_val = None
                for key in ["偏差数量", "数量偏差", "dev_qty"]:
                    val = data.get(key)
                    if val:
                        try:
                            dev_qty_val = float(val)
                            if abs(dev_qty_val) > 0.0001:
                                break
                        except:
                            continue
                if dev_qty_val and abs(dev_qty_val) > 0.0001:
                    # 单价 = 偏差金额绝对值 / 偏差数量绝对值
                    unit_price = abs(dev_amount_val) / abs(dev_qty_val)
                    # 单位
                    unit_name = ""
                    for key in ["单位", "组件单位", "unit"]:
                        val = data.get(key)
                        if val and str(val) not in ("nan", "None", ""):
                            unit_name = str(val)
                            break
                    if not unit_name:
                        unit_name = "单位"
                    sign_icon = "↑" if dev_amount_val > 0 else "↓"
                    # 直接显示
                    info += f"\n💰 偏差金额：¥{dev_amount_val:,.2f} {sign_icon} ≈ {abs(dev_qty_val):.1f} {unit_name}（单价 ¥{unit_price:.2f}/{unit_name}）"
                else:
                    info += f"\n💰 偏差金额：¥{dev_amount_val:,.2f}（数量偏差为0或缺失）"
        except Exception as e:
            info += f"\n⚠️ 成本换算失败：{e}"

        text.insert("1.0", info)
        text.configure(state="disabled")

        # 常用备注按钮
        btn_fr = tk.Frame(self._card_win, bg=card_bg)
        btn_fr.pack(pady=(0, 10))

        preset_remarks = ["系统无定额", "替代料", "已核实", "工艺调整", "其他"]
        sorted_remarks, freq = self._get_sorted_remarks(preset_remarks)

        def fill_remark(tag):
            # 更新 Treeview 中显示的备注
            self.audit_tree.set(item, "remark", tag)
            self.audit_tree.set(item, "status", "已备注")
            # 更新原始数据
            if "excel_row" in data:
                try:
                    row_int = int(float(data["excel_row"]))
                    mask = self.audit_data["excel_row"].astype(str).astype(float).astype(int) == row_int
                    if mask.any():
                        self.audit_data.loc[mask, "备注原因"] = tag
                except:
                    pass
            self._record_remark_freq(tag)
            self._card_win.destroy()

        for i, remark in enumerate(sorted_remarks):
            count = freq.get(remark, 0)
            if i < 3 and count > 0:
                btn_font = ("Microsoft YaHei", 10, "bold")
                btn_bg = "#bbdefb"
            else:
                btn_font = ("Microsoft YaHei", 9)
                if "无定额" in remark:
                    btn_bg = "#e3f2fd"
                elif "替代" in remark:
                    btn_bg = "#fff9c4"
                else:
                    btn_bg = "#f5f5f5"
            tk.Button(btn_fr, text=f"{remark}({count})" if count > 0 else remark,
                      command=lambda r=remark: fill_remark(r), bg=btn_bg,
                      font=btn_font, relief="flat", width=12).pack(side="left", padx=3)

    def _show_audit_context_menu(self, event):
        """显示审核表格右键菜单"""

        # 选中点击位置的项

        item = self.audit_tree.identify_row(event.y)

        if item:
            # 如果点击的项不在已选中项中,清除其他选择并选中当前项

            if item not in self.audit_tree.selection():
                self.audit_tree.selection_set(item)

        # 显示菜单

        try:
            self.audit_context_menu.tk_popup(event.x_root, event.y_root)

        finally:
            self.audit_context_menu.grab_release()

    def _filter_audit_tree(self, filter_type=None):

        if self.audit_data is None or len(self.audit_data) == 0:
            return

        for key in self.audit_stat_cards:
            self.audit_stat_cards[key].configure(bg=C["surface2"])
            for child in self.audit_stat_cards[key].winfo_children():
                child.configure(bg=C["surface2"])

        if filter_type:
            self.audit_stat_cards[filter_type].configure(bg="#e8f0fe")
            for child in self.audit_stat_cards[filter_type].winfo_children():
                child.configure(bg="#e8f0fe")

        for row in self.audit_tree.get_children():
            self.audit_tree.delete(row)

        if filter_type == "need_note":
            filtered_data = self.audit_data[self.audit_data["备注原因"].isna()]

        elif filter_type == "ok_note":
            filtered_data = self.audit_data[self.audit_data["备注原因"].notna()]

        elif filter_type == "_color":
            color_val = self.filter_vars.get("_color", tk.StringVar(value="全部")).get()
            if color_val and color_val != "全部":
                color_map = {
                    "🔴 红": self.config.get("priority.red_label", "红"),
                    "🟠 橙": "橙",
                    "🟡 黄": self.config.get("priority.yellow_label", "黄"),
                    "🟢 绿": self.config.get("priority.green_label", "绿"),
                }
                target_color = color_map.get(color_val, color_val)
                filtered_data = self.audit_data[
                    self.audit_data["_priority_label"] == target_color
                ]
            else:
                filtered_data = self.audit_data

        else:
            filtered_data = self.audit_data

        self._update_audit_stats(filtered_data)

        for i, (_, row) in enumerate(filtered_data.iterrows(), 1):
            # ── 与 _refresh_audit_tree 保持完全一致的变量名 ──

            # 备注
            orig_remark = str(row.get("备注原因", row.get("备注", ""))).strip()
            if orig_remark in ("nan", "NaN", "None", ""):
                orig_remark = ""
            remark = orig_remark[:30]

            # 批量备注
            batch_remark = str(row.get("批量备注原因", row.get("批量备注", ""))).strip()
            if batch_remark in ("nan", "NaN", "None", ""):
                batch_remark = ""
            batch_remark = batch_remark[:30]

            has_note = remark != "" or batch_remark != ""

            # 状态
            note_src = str(row.get("备注来源", "")).strip()
            if note_src in ("nan", "NaN", "None", ""):
                note_src = ""
            if remark:
                # 有备注：直接标记已备注
                status = '已备注'
            else:
                # 无备注：按 note_src 判断
                if note_src in ('AI审核合格', 'AI审核待改进', 'AI生成'):
                    status = f"AI生成{'↑' if float(row.get('偏差率(%)', 0)) > 0 else '↓'}"
                elif note_src in ('人工填写', '系统无定额(广宣)', '自动填充', '替代料'):
                    status = '已备注'
                else:
                    status = '需补备注'
            # 物料大类
            _mc_from_df = row.get("material_category", "")
            if _mc_from_df and str(_mc_from_df).strip() not in ("", "nan", "NaN", "None"):
                mat_category = str(_mc_from_df).strip()
            else:
                code = str(row.get("物料编码", row.get("组件物料号", "")))
                mat_code_prefix = code[:3] if code else ""
                _mat_map = {
                    "100": "原辅料", "200": "包材",
                    "400": "食品辅料/食品半成品", "410": "饮料辅料/饮料半成品",
                    "500": "食品成品", "510": "饮料成品", "600": "促销品",
                }
                mat_category = _mat_map.get(mat_code_prefix, mat_code_prefix)

            # 物料描述
            mat_desc = str(row.get("组件物料描述", row.get("物料名称", ""))).strip()
            if not mat_desc:
                mat_desc = str(row.get("物料描述", "")).strip()
            mat_desc = mat_desc[:30]

            # 替代料
            alt_all_descs = getattr(self, "alt_all_descs", set())
            is_alt = "是" if mat_desc and mat_desc in alt_all_descs else ""

            # 偏差率
            dev_rate = row.get("偏差率(%)", row.get("偏差率", 0)) or 0
            try:
                dev_rate = float(dev_rate)
            except Exception:
                dev_rate = 0.0

            # 订单号
            order_no_val = ""
            for _col in ["流程订单", "订单号", "订单编号"]:
                if _col in row.index and pd.notna(row.get(_col)):
                    order_no_val = str(row.get(_col))
                    break

            # 订单类型
            order_type_val = str(row.get("订单类型", ""))

            # audit_result / audit_status / audit_source
            audit_result_val = str(row.get("audit_result", ""))
            audit_status_val = (
                "已审核" if audit_result_val and audit_result_val.strip() not in ("", "nan")
                else "未审核"
            )
            audit_source_val = note_src
            if audit_source_val in ("nan", "NaN", "None", ""):
                _ns = str(row.get("备注来源", ""))
                if _ns in ("AI审核合格", "AI审核待改进", "AI生成"):
                    audit_source_val = "AI审核"
                elif _ns == "人工填写":
                    audit_source_val = "手动"
                elif _ns == "替代料":
                    audit_source_val = "替代料"
                else:
                    audit_source_val = ""

            # 用统一方法构建 values
            values = self._build_audit_values(
                row, i, mat_category, mat_desc, order_no_val,
                order_type_val, dev_rate, is_alt, status,
                remark, batch_remark, audit_result_val,
                audit_status_val, audit_source_val
            )
            item = self.audit_tree.insert("", "end", values=values)

            # 标签
            remark_status = row.get("remark_check_status", "")
            current_tags = []
            if remark_status == "red":
                current_tags.append("remark_red")
            elif remark_status == "yellow":
                current_tags.append("remark_yellow")

            _priority_label = row.get("_priority_label", "")
            if _priority_label:
                if "红" in str(_priority_label):
                    current_tags.append("priority_red")
                elif "橙" in str(_priority_label) or "黄" in str(_priority_label):
                    current_tags.append("priority_yellow")
                else:
                    current_tags.append("priority_green")

            if current_tags:
                self.audit_tree.item(item, tags=current_tags)

        self.log(f"筛选完成:显示 {len(filtered_data)} 条记录", "info")


    # ── 智能审核筛选栏方法 ─────────────────────────────

    def set_filter_and_refresh(self, filter_key: str, filter_value: str):
        """供看板下钻等外部调用，设置筛选器并刷新表格（Task 019）"""
        if filter_key in self.filter_widgets:
            widget = self.filter_widgets[filter_key]
            # 日期筛选器是 tuple，不支持 set
            if isinstance(widget, tuple):
                return
            if hasattr(widget, 'set'):
                widget.set(filter_value)
            self._on_filter_changed(filter_key)
            if hasattr(self, 'log'):
                self.log(f"[019] 下钻筛选：{filter_key} = {filter_value}", "info")
        else:
            if hasattr(self, 'log'):
                self.log(f"[019] 筛选器 '{filter_key}' 不存在，无法下钻", "error")

    def _on_filter_changed(self, col_key):
        """任一筛选下拉框变化时,组合所有筛选条件并刷新表格(统一使用 FilterEngine)"""
        print(f"[DEBUG] _on_filter_changed called with key={col_key}")

        if self.audit_data is None or len(self.audit_data) == 0:
            return

        # 统一使用 FilterEngine 进行筛选
        from modules.audit.filters.filter_engine import FilterEngine

        filters = {}

        # 1. 搜索关键词
        search_text = self.search_var.get().strip()
        if search_text and search_text != "输入任意关键词,实时过滤全部列...":
            filters['search'] = search_text

        # 2. 日期范围
        if "order_date" in self.filter_widgets:
            date_widgets = self.filter_widgets["order_date"]
            if isinstance(date_widgets, tuple) and len(date_widgets) == 2:
                start_d = date_widgets[0].get_date().strftime('%Y-%m-%d') if date_widgets[0].get_date() else ''
                end_d = date_widgets[1].get_date().strftime('%Y-%m-%d') if date_widgets[1].get_date() else ''
                if start_d:
                    filters['date_start'] = start_d
                if end_d:
                    filters['date_end'] = end_d

        # 3. 顶部栏下拉框值
        for key, cb in self.filter_widgets.items():
            if key == "order_date" or isinstance(cb, tuple):
                continue
            val = cb.get()
            if val and val != "全部":
                filters[key] = val

        # 4. 侧边栏条件(从 FilterPanel 获取,不覆盖顶部栏已有的 key)
        if hasattr(self, 'filter_panel'):
            sidebar_filters = self.filter_panel.get_filters()
            for k, v in sidebar_filters.items():
                if k not in filters and v and v != '全部':
                    filters[k] = v

        # 使用 FilterEngine 统一筛选
        engine = FilterEngine()
        df_filtered = engine.apply(filters, self.audit_data)

        import sys


        # ── 异常突变检测(保留在View,依赖View状态)──
        try:
            self.mutation_materials = set()

            if hasattr(self, "rule_engine") and "订单日期" in df_filtered.columns:
                df_dates = pd.to_datetime(
                    df_filtered["订单日期"].astype(str).str[:10], errors="coerce"
                )

                unique_dates = sorted(set(df_dates.dropna()))

                if len(unique_dates) >= 5:
                    split_idx = int(len(unique_dates) * 0.7)

                    early_dates = set(unique_dates[:split_idx])

                    recent_dates = set(unique_dates[split_idx:])

                    df_temp = df_filtered.copy()

                    df_temp["date_key"] = df_dates

                    early_df = df_temp[df_temp["date_key"].isin(early_dates)]

                    recent_df = df_temp[df_temp["date_key"].isin(recent_dates)]

                    early_stats = (
                        early_df.groupby("组件物料号")["偏差率(%)"]
                        .agg(["mean", "std"])
                        .reset_index()
                    )

                    for _, row in recent_df.iterrows():
                        mat = row.get("组件物料号")

                        if pd.isna(mat):
                            continue

                        early_row = early_stats[early_stats["组件物料号"] == mat]

                        if not early_row.empty:
                            early_mean = early_row["mean"].values[0]

                            early_std = early_row["std"].values[0]

                            curr_dev = row.get("偏差率(%)", 0)

                            if (
                                pd.notna(early_mean)
                                and pd.notna(early_std)
                                and early_std > 0
                            ):
                                z_score = (curr_dev - early_mean) / early_std

                                if abs(z_score) > 2:
                                    self.mutation_materials.add(mat)
        except Exception as e:
            self.log(f"异常突变检测出错:{e}", "error")

        # 刷新表格和统计
        self.filtered_data = df_filtered  # ← 添加这行,保存筛选后的数据
        self._refresh_audit_tree(df_filtered)
        self._update_audit_stats(df_filtered)
        self.log(f"筛选完成:显示 {len(df_filtered)} 条记录", "info")

    def _reset_all_filters(self):
        """重置所有筛选条件"""

        for key, widget in self.filter_widgets.items():
            if key == "name":
                # Entry 控件:清空文本

                widget.delete(0, tk.END)

            elif key == "order_date":
                # 日期控件:清空两个输入框

                if isinstance(widget, tuple) and len(widget) == 2:
                    widget[0].delete(0, tk.END)

                    widget[1].delete(0, tk.END)

            else:
                # Combobox 控件:重置为"全部"

                widget.set("全部")

        if self.audit_data is not None:
            self._refresh_audit_tree(self.audit_data)

        if self.filter_status_lbl:
            self.filter_status_lbl.configure(text="")

        if hasattr(self, "status_filter_label"):
            self.status_filter_label.configure(
                text=f"📋 显示全部 | 共 {len(self.audit_data)} 条"
            )

        # P1-1-4 重置万能搜索框

        self.search_var.set("")

        self.search_entry.delete(0, "end")

        self.search_entry.insert(0, "输入任意关键词,实时过滤全部列...")

        self.log("已重置所有筛选条件", "info")

        if (
            hasattr(self, "audit_data")
            and self.audit_data is not None
            and len(self.audit_data) > 0
        ):
            self._enable_audit_buttons()

    def _update_filter_options(self):
        """根据当前 audit_data 更新筛选下拉框的值列表"""

        if self.audit_data is None or len(self.audit_data) == 0:
            return

        # 确保 status_temp 列存在

        if "status_temp" not in self.audit_data.columns:
            self.audit_data["status_temp"] = self.audit_data["备注原因"].apply(
                lambda x: (
                    "已备注" if pd.notna(x) and str(x).strip() != "" else "需补备注"
                )
            )

        col_map = {
            "factory": "工厂名称",
            "admin": "生产管理员描述",
            "name": "组件物料描述",
            "status": "status_temp",
            "dev_rate": "偏差率(%)",
            "is_alt": None,  # 特殊处理:替代料筛选
            "remark": "备注原因",
        }

        dev_rate_presets = self.config.get(
            "filter.dev_rate_presets",
            ["全部", ">10%", ">20%", ">30%", "绝对值>10%", "<-10%", "<-20%"],
        )

        is_alt_presets = self.config.get("filter.is_alt_presets", ["全部", "是", "否"])

        for key, cb in self.filter_widgets.items():
            # name 是 Entry 控件,不需要更新下拉选项

            if key == "name":
                continue

            # material_category 单独在循环后处理(基于全量数据)
            if key == "material_category":
                continue

            if key == "dev_rate":
                cb["values"] = dev_rate_presets

                if cb.get() not in dev_rate_presets:
                    cb.set("全部")

                continue

            if key == "remark":
                # 备注筛选:已填写的值 + "为空" 选项

                str_vals = sorted(
                    [
                        str(v)
                        for v in self.audit_data["备注原因"].dropna()
                        if v != "" and pd.notna(v)
                    ]
                )

                seen = set()

                unique_str = []

                for v in str_vals:
                    if v not in seen:
                        seen.add(v)

                        unique_str.append(v)

                cb["values"] = ["全部", "为空", "不为空"] + unique_str

                if cb.get() not in cb["values"]:
                    cb.set("全部")

                continue

            if key == "ai_result":
                src_vals = self.audit_data["备注来源"].dropna().unique()

                opts = ["全部"]

                if any(v == "AI审核合格" for v in src_vals):
                    opts.append("合格")

                if any(v == "AI审核待改进" for v in src_vals):
                    opts.append("需改进")

                if any(v.startswith("AI建议") for v in src_vals):
                    opts.append("AI建议")

                if any(
                    v not in ["AI审核合格", "AI审核待改进"]
                    and not v.startswith("AI建议")
                    and v != ""
                    for v in src_vals
                ):
                    opts.append("未处理")

                cb["values"] = opts

                if cb.get() not in opts:
                    cb.set("全部")

                continue

            if key == "is_alt":
                # 替代料筛选:固定选项

                cb["values"] = is_alt_presets

                if cb.get() not in is_alt_presets:
                    cb.set("全部")

                continue

            df_col = col_map.get(key)

            if df_col is None or df_col not in self.audit_data.columns:
                continue

            unique_vals = self.audit_data[df_col].dropna()

            if key == "status":
                unique_vals = [v for v in unique_vals if v != ""]

            str_vals = sorted([str(v) for v in unique_vals if v != "" and pd.notna(v)])

            # 去重保持顺序

            seen = set()

            unique_str = []

            for v in str_vals:
                if v not in seen:
                    seen.add(v)

                    unique_str.append(v)

            cb["values"] = ["全部"] + unique_str

            if cb.get() not in cb["values"]:
                cb.set("全部")

        # ── material_category 单独处理:必须基于全量数据,避免筛选后选项丢失 ──
        if "material_category" in self.filter_widgets:
            cb_cat = self.filter_widgets["material_category"]
            # 优先使用 full_audit_data,回退到 audit_data
            data_src = (
                self.full_audit_data
                if hasattr(self, "full_audit_data") and self.full_audit_data is not None
                else self.audit_data
            )
            if data_src is not None and "material_category" in data_src.columns:
                unique_cats = sorted(
                    [str(v) for v in data_src["material_category"].dropna().unique() if v != ""]
                )
                cat_options = ["全部"] + unique_cats
                cb_cat["values"] = cat_options
                if cb_cat.get() not in cat_options:
                    cb_cat.set("全部")
                print(f"[DEBUG] 物料大类下拉框已更新,选项: {cat_options}")
            else:
                print("[DEBUG] material_category 列不存在,物料大类下拉框保持不变")

    def _collect_filters(self):
        """收集所有筛选控件的当前值"""

        filters = {}

        try:
            for key, widget in self.filter_widgets.items():
                if isinstance(widget, tuple):
                    # 日期范围

                    filters[key] = (widget[0].get().strip(), widget[1].get().strip())

                elif isinstance(widget, tk.Entry):
                    val = widget.get().strip()

                    if val and val != "输入任意关键词,实时过滤全部列...":
                        filters[key] = val

                else:
                    val = widget.get()

                    if val and val != "全部":
                        filters[key] = val

        except Exception:
            pass

        return filters

    def _restore_filters(self):
        """从 StateStore 恢复筛选条件到 UI 控件"""

        if not hasattr(self, "state"):
            return

        saved = self.state.get("filters", "all", {})

        if not saved:
            return

        try:
            for key, val in saved.items():
                if key not in self.filter_widgets:
                    continue

                widget = self.filter_widgets[key]

                if (
                    isinstance(widget, tuple)
                    and isinstance(val, (list, tuple))
                    and len(val) == 2
                ):
                    try:
                        widget[0].delete(0, "end")

                        widget[0].insert(0, str(val[0]))

                        widget[1].delete(0, "end")

                        widget[1].insert(0, str(val[1]))

                    except Exception:
                        pass

                elif isinstance(widget, tk.Entry):
                    try:
                        widget.delete(0, "end")

                        widget.insert(0, str(val))

                    except Exception:
                        pass

                elif hasattr(widget, "set"):
                    try:
                        widget.set(str(val))

                    except Exception:
                        pass

        except Exception:
            pass

    def _restore_sort_state(self):
        """从 StateStore 恢复排序状态"""

        if not hasattr(self, "state"):
            return

        saved = self.state.get("sort", "columns", [])

        if not saved or not isinstance(saved, list):
            return

        try:
            if not hasattr(self, "audit_tree"):
                return

            tree_cols = list(self.audit_tree["columns"])

            valid = [(col, asc) for col, asc in saved if col in tree_cols]

            if valid:
                self.sort_columns = valid

                self._on_tree_sort.__wrapped__(self) if hasattr(
                    self._on_tree_sort, "__wrapped__"
                ) else None

                # Fallback: just refresh display

                self._update_sort_indicators()

            if hasattr(self, "state"):
                self.state.set("sort", "columns", self.sort_columns, auto_save=True)

        except Exception:
            pass

    def _update_sort_indicators(self):

        if not hasattr(self, "audit_tree"):
            return

        for col_id in self.audit_tree["columns"]:
            base = self._COL_DISPLAY.get(col_id, col_id)

            self.audit_tree.heading(col_id, text=base)

        for idx, (col_id, asc) in enumerate(self.sort_columns, start=1):
            base = self._COL_DISPLAY.get(col_id, col_id)

            arrow = "↑" if asc else "↓"

            new_text = base + " " + arrow if idx == 1 else f"{base} [{idx}]{arrow}"

            self.audit_tree.heading(col_id, text=new_text)

    # ── S01 库存检查方法 ──────────────────────────────

    def _on_tree_sort(self, col_id):
        """多列同时排序,每列三轮循环:正序 → 倒序 → 取消排序 → 正序..."""

        # 查找该列是否已在排序列表中
        found = False
        new_sort_columns = []
        for cid, asc in self.sort_columns:
            if cid == col_id:
                found = True
                # 三态循环:True(正序) → False(倒序) → 移除(取消)
                if asc == True:
                    new_sort_columns.append((cid, False))  # 正序 → 倒序
                # False → 不添加(取消排序)
            else:
                new_sort_columns.append((cid, asc))

        if not found:
            # 新列追加到末尾,初始为正序
            new_sort_columns.append((col_id, True))

        self.sort_columns = new_sort_columns
        self._apply_sort_and_refresh()

    def _apply_sort_and_refresh(self):

        if self.audit_data is None or self.audit_data.empty:
            return

        if not self.sort_columns:
            self._refresh_audit_tree(self.audit_data)

            return

        valid = []

        for col_id, asc in self.sort_columns:
            df_col = self._COL_TO_DF.get(col_id)

            if df_col and df_col in self.audit_data.columns:
                valid.append((df_col, asc))

        if not valid:
            self._refresh_audit_tree(self.audit_data)

            return

        by = [col for col, _ in valid]

        asc_list = [asc for _, asc in valid]

        df_sorted = (self.filtered_data if hasattr(self, 'filtered_data') and self.filtered_data is not None else self.audit_data).copy()

        for col in by:
            if col in ("偏差率(%)", "偏差金额", "数量-定额", "数量-实际"):
                df_sorted[col] = pd.to_numeric(df_sorted[col], errors="coerce").fillna(
                    0
                )

        df_sorted = df_sorted.sort_values(by=by, ascending=asc_list, na_position="last")

        self._refresh_audit_tree(df_sorted, skip_auto_sort=True)

        self._update_sort_indicators()

    def _init_sort_columns(self):

        for col_id in self.audit_tree["columns"]:
            self.audit_tree.heading(
                col_id, command=lambda cid=col_id: self._on_tree_sort(cid)
            )

        self.sort_columns = []

    def _update_audit_stats(self, filtered_data=None):
        """更新统计卡片(联动筛选后的数据)"""

        if self.audit_data is None or len(self.audit_data) == 0:
            self.log(f"[DEBUG] _update_audit_stats: audit_data 为空,跳过", "info")
            return

        data = filtered_data if filtered_data is not None else self.audit_data

        self.log(f"[DEBUG] _update_audit_stats: data={len(data)}行, 列={list(data.columns)[:10]}", "info")

        total = len(data)

        high_dev = len(data[data["偏差率(%)"].abs() > 10])

        need_note = data[
            data["备注原因"].isna() | (data["备注原因"].astype(str).str.strip() == "")
        ]

        ok_note = data[
            data["备注原因"].notna() & (data["备注原因"].astype(str).str.strip() != "")
        ]

        # 更新四个统计卡片

        self.audit_stat_labels["total"].configure(text=str(total))

        self.audit_stat_labels["high_dev"].configure(text=str(high_dev))

        self.audit_stat_labels["need_note"].configure(text=str(len(need_note)))

        self.audit_stat_labels["ok_note"].configure(text=str(len(ok_note)))

        # 同步更新统一按钮行状态标签

        if hasattr(self, "unified_result_lbl"):
            self.unified_result_lbl.configure(
                text=f"筛选结果:{total} 条 | 偏差>10%: {high_dev} | 需补备注: {len(need_note)}"
            )

        # 总偏差金额 + 实物量换算
        data = filtered_data if filtered_data is not None else self.audit_data
        if data is not None and not data.empty and '偏差金额' in data.columns:
            total_amount = data['偏差金额'].fillna(0).sum()
            # 单位一致性检测
            unit_col = next((c for c in ['组件单位', '单位'] if c in data.columns), None)
            if unit_col:
                units = data[unit_col].dropna().unique()
                if len(units) == 1:
                    unit = str(units[0])
                    # 计算总数量偏差绝对值
                    if '偏差数量' in data.columns:
                        total_qty_abs = data['偏差数量'].abs().sum()
                    else:
                        actual_col = next((c for c in ['数量-实际', '实际'] if c in data.columns), None)
                        quota_col = next((c for c in ['数量-定额', '定额'] if c in data.columns), None)
                        if actual_col and quota_col:
                            total_qty_abs = (data[actual_col] - data[quota_col]).abs().sum()
                        else:
                            total_qty_abs = 0
                    if total_qty_abs > 0 and abs(total_amount) > 0.01:
                        avg_price = abs(total_amount) / total_qty_abs
                        est_qty = abs(total_amount) / avg_price
                        text = f"💸 总偏差金额:¥{total_amount:,.2f} ≈ {est_qty:.1f} {unit}(均价 ¥{avg_price:.2f}/{unit})"
                    else:
                        text = f"💸 总偏差金额:¥{total_amount:,.2f}"
                else:
                    unit_preview = ', '.join([str(u) for u in list(units)[:3]])
                    text = f"💸 总偏差金额:¥{total_amount:,.2f}(多种单位:{unit_preview}...,无法汇总实物量)"
            else:
                text = f"💸 总偏差金额:¥{total_amount:,.2f}"
            if hasattr(self, 'summary_cost_lbl'):
                self.summary_cost_lbl.config(text=text)
        else:
            if hasattr(self, 'summary_cost_lbl'):
                self.summary_cost_lbl.config(text="")

    def _on_search_delayed(self, event):

        if hasattr(self, "_search_timer"):
            self.root.after_cancel(self._search_timer)

        self._search_timer = self.root.after(
            300, lambda: self._on_filter_changed("search")
        )

    # ==================== 预检报告弹窗 ====================

    def _enable_audit_buttons(self):
        """统一启用所有审核相关按钮"""

        btn_names = [
            "load_audit_btn",
            "unified_ai_btn",
            "cancel_audit_btn",
            "unified_export_btn",
            "save_audit_btn",
            "export_db_btn",
            "import_db_btn",
            "tree_view_btn",
            "resume_btn",
            "quarantine_btn",
            "auto_close_btn",
            "cancel_auto_close_btn",
            "bom_btn",
            "cleanup_btn",
            "audit_ai_btn",
            "audit_export_btn",
        ]

        enabled = 0

        for name in btn_names:
            btn = getattr(self, name, None)

            if btn and hasattr(btn, "configure"):
                try:
                    btn.configure(state="normal")

                    enabled += 1

                except Exception:
                    pass

        return enabled

    def _show_precheck_report(self, df):
        """F6 预检报告弹窗"""

        if df is None or df.empty:
            return

        total = len(df)

        rate_col = None

        for col in ["偏差率(%)", "偏差率", "偏差率%", "dev_rate", "rate"]:
            if col in df.columns:
                rate_col = col

                break

        if rate_col:
            clean_rates = pd.to_numeric(df[rate_col], errors="coerce").dropna()

            abnormal = (clean_rates.abs() >= 10).sum()

            warning = ((clean_rates.abs() >= 5) & (clean_rates.abs() < 10)).sum()

            normal = (clean_rates.abs() < 5).sum()

        else:
            abnormal = warning = normal = 0

        status_col = None

        for col in ["审核状态", "audit_status", "状态"]:
            if col in df.columns:
                status_col = col

                break

        if status_col:
            reviewed = (df[status_col] == "已审核").sum()

            un_reviewed = total - reviewed

        else:
            reviewed = un_reviewed = 0

        msg = (
            f"数据加载完成\n\n"
            f"总行数:{total}\n"
            f"偏差异常(≥10%):{abnormal}\n"
            f"偏差关注(5%-10%):{warning}\n"
            f"偏差正常(<5%):{normal}\n\n"
            f"已审核:{reviewed}\n"
            f"未审核:{un_reviewed}"
        )

        # ── 汇总换算:偏差总金额 + 实物量估算 ──
        try:
            # 查找偏差金额列
            amount_col = None
            for col in ['偏差金额', '偏差金额(含税)', 'deviation_amount']:
                if col in df.columns:
                    amount_col = col
                    break
            if amount_col:
                amount_sum = df[amount_col].fillna(0).sum()
                if abs(amount_sum) > 0.01:
                    # 计算总数量偏差(绝对值)
                    qty_actual_col = next((c for c in ['数量-实际', '实际'] if c in df.columns), None)
                    qty_quota_col = next((c for c in ['数量-定额', '定额'] if c in df.columns), None)
                    if qty_actual_col and qty_quota_col:
                        qty_actual = pd.to_numeric(df[qty_actual_col], errors='coerce').fillna(0)
                        qty_quota = pd.to_numeric(df[qty_quota_col], errors='coerce').fillna(0)
                        total_qty_abs = (qty_actual - qty_quota).abs().sum()
                        unit_col = next((c for c in ['组件单位', '单位'] if c in df.columns), None)
                        if total_qty_abs > 0 and unit_col:
                            unit = df[unit_col].iloc[0] if len(df) > 0 else ""
                            avg_price = amount_sum / total_qty_abs
                            if avg_price > 0 and unit:
                                est_qty = abs(amount_sum) / avg_price
                                msg += f"\n\n💸 偏差总金额:¥{amount_sum:,.2f} ≈ {est_qty:.1f} {unit}(均价 ¥{avg_price:.2f}/{unit})"
                            else:
                                msg += f"\n\n💸 偏差总金额:¥{amount_sum:,.2f}(无法换算实物量)"
                        else:
                            msg += f"\n\n💸 偏差总金额:¥{amount_sum:,.2f}(无法换算实物量)"
                    else:
                        msg += f"\n\n💸 偏差总金额:¥{amount_sum:,.2f}(无法换算实物量)"
                else:
                    msg += f"\n\n💸 偏差总金额:¥{amount_sum:,.2f}"
            else:
                msg += f"\n\n💸 偏差总金额:无法计算(缺少金额列)"
        except Exception as e:
            self.log(f"预检报告汇总换算出错:{e}", "warn")

        # 改为日志输出,不弹模态窗口
        self.log("=== 📊 预检报告 ===", "info")
        for line in msg.strip().split("\n"):
            if line.strip():
                self.log(line, "info")
        self.log("=== 预检报告结束 ===", "info")
        # 更新状态栏提示
        if hasattr(self, "status_lbl"):
            self.status_lbl.configure(
                text=f"数据加载完成,共{total}条,预检报告已写入日志"
            )

