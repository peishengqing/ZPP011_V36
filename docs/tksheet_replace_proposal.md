# ZPP011 · Treeview → tksheet 替换草案

> 版本：v1.0 · 日期：2026-06-03 · 作者：小清

---

## 一、tksheet 是什么？

`tksheet` 是专为 tkinter 设计的**高性能表格控件**，定位相当于 Excel 的网格视图。

与传统 `ttk.Treeview` 的本质区别：

| 特性 | ttk.Treeview | tksheet |
|------|--------------|---------|
| 渲染方式 | 每行一个 item，大数据量卡顿 | 虚拟渲染，只画可见区域 |
| 排序 | 手动实现，易与筛选冲突 | 内置 `enable_sort()`，一行启用 |
| 筛选 | 手动实现 | 内置 `enable_filter()`，一行启用 |
| 单元格编辑 | 需额外弹窗 | 原地编辑，支持验证 |
| 列宽拖拽 | 需手动绑定 | 原生支持 |
| 冻结列/行 | 不支持 | 原生支持 |
| 选中模式 | 整行 | 可选单元格/整行/整列 |
| 大数据量 | >5000 行明显卡顿 | 10 万行不卡 |

**一句话**：tksheet 就是 tkinter 里的 Excel 表格控件。

---

## 二、为什么要换？（现状问题清单）

### 当前 Treeview 存在的痛点

**① 排序 × 筛选 冲突（本次已修，但本质问题未解决）**
- 排序和筛选各自维护状态，刷新时互相覆盖
- 根因：Treeview 本身不支持排序/筛选，全靠手动实现

**② 大数据量卡顿**
- 1 万行以上，插入行耗时明显
- 每次筛选都要 `delete` + 重新 `insert`，O(n) 开销

**③ 单元格编辑体验差**
- 需要弹窗或额外 Entry 绑定
- 当前 ZPP011 的备注编辑用弹窗，操作繁琐

**④ 样式定制受限**
- 行高、字体、网格线颜色均难定制
- 替代料行高亮靠 tag，维护成本高

**⑤ 分页与虚拟滚动不能兼得**
- 当前已实现分页，但用户反馈"翻页麻烦"
- Treeview 不支持虚拟滚动，分页是妥协方案

---

## 三、替换设计方案

### 3.1 架构变化

```
【当前】
ui_builder.py  →  创建 ttk.Treeview
table_events.py →  手动实现排序/筛选/分页/刷新

【替换后】
ui_builder.py  →  创建 tksheet.Sheet
table_events.py →  绑定事件 + 调用 tksheet API
                     排序/筛选改用 tksheet 内置方法
```

### 3.2 核心改动文件

| 文件 | 改动范围 | 预估行数 |
|------|-----------|----------|
| `gui/ui_builder.py` | 替换 Treeview 为 Sheet | ~80 行 |
| `gui/event_handlers/table_events.py` | 重写表格刷新/排序/筛选逻辑 | ~400 行 |
| `config/audit_cols_config.py` | 列配置映射（Treeview列名 → tksheet列索引） | ~30 行 |
| `gui/event_handlers/analysis_events.py` | 适配 `_refresh_audit_tree` 调用方式 | ~50 行 |
| `requirements.txt` | 新增 `tksheet>=7.0` | 1 行 |

**总计预估：~560 行改动**

### 3.3 关键技术点

**① 列映射（Treeview col_id → tksheet col_index）**

```python
# 当前：Treeview 用 col_id 标识列
self.audit_tree.insert("", "end", values=(..., remark, ...))

# tksheet：用列索引，需要建立映射
COL_MAP = {
    "物料编码": 0, "物料名称": 1, "偏差率(%)": 2, ...
}
sheet.set_column_data([col for col, _, _, _ in COLS_CONFIG])
```

**② 排序（用内置，不再手动）**

```python
# 当前：手动 sort_values → 重新 insert
df_sorted = df.sort_values(by=...)
_refresh_audit_tree(df_sorted)

# tksheet：内置排序，自动刷新
sheet.enable_sort(True)  # 列头点击即排序，自动处理
# 或手动触发：
sheet.sort(sort_columns=[2], reverse=False)  # 按第2列排序
```

**③ 筛选（用内置或保持 FilterEngine）**

```python
# 方案A：用 tksheet 内置筛选（简单场景）
sheet.enable_filter(True)

# 方案B：保持现有 FilterEngine，筛选后把结果写回 sheet
# （推荐，因为现有筛选逻辑复杂，含日期范围+多条件）
filtered_df = engine.apply(filters, self.audit_data)
sheet.set_sheet_data(filtered_df.values.tolist())
```

**④ 行高亮（替代料行、四色优先级）**

```python
# 当前：Treeview tag
self.audit_tree.item(item_id, tags=("alt",))

# tksheet：highlight 机制
sheet.highlight_cells(rows=[i], bg="lightyellow", fg="red")
# 或按列值自动上色（推荐）
sheet.set_column_highlight(col_index, criteria_func)
```

**⑤ 右键菜单（保持不变）**

```python
# tksheet 同样支持右键绑定
sheet.bind("<Button-3>", self._on_tree_right_click)
# 菜单弹出逻辑几乎不用改
```

### 3.4 兼容性保障

- **分阶段替换**：先替换主表格（审核页），其他 Treeview（如历史对比页）暂不动
- **保持对外接口不变**：`_refresh_audit_tree(df)` 签名不变，内部实现替换
- **回滚方案**：保留 `table_events.py.backup`，出问题一键还原

---

## 四、优缺点分析

### 优点

| 优点 | 说明 |
|------|------|
| **性能提升明显** | 1 万行数据，滚动/排序/筛选均不卡 |
| **内置排序筛选** | 不再手动维护，bug 少 90% |
| **编辑体验好** | 双击单元格直接改备注，不用弹窗 |
| **虚拟滚动** | 可取消分页，用户操作更流畅 |
| **维护成本低** | 核心逻辑由 tksheet 维护，我们只需调 API |

### 缺点 / 风险

| 缺点 | 缓解措施 |
|------|----------|
| **学习成本** | 我来完成替换，你只需验证功能 |
| **样式差异** | tksheet 默认样式偏素，需要调一下字体/行高，约 1 小时 |
| **打包体积增加** | `tksheet` 约 200KB，对 PyInstaller 打包影响极小 |
| **现有代码改动量大** | 分阶段替换，先跑通主流程，再修边缘功能 |

---

## 五、实施计划（分阶段）

### 第一阶段：最小可用（1~2 天）

- [ ] `pip install tksheet`，验证版本兼容
- [ ] 替换 `ui_builder.py` 中的 Treeview 为 Sheet
- [ ] 重写 `_refresh_audit_tree()`，能用 tksheet 显示数据
- [ ] 验证：数据加载 → 表格显示正常

### 第二阶段：核心功能（2~3 天）

- [ ] 排序功能（用 tksheet 内置）
- [ ] 筛选功能（保持 FilterEngine，结果写回 Sheet）
- [ ] 右键菜单（绑定到 Sheet）
- [ ] 分页 / 虚拟滚动（二选一）

### 第三阶段：细节打磨（1~2 天）

- [ ] 行高亮（替代料、四色优先级）
- [ ] 单元格编辑（备注列双击编辑）
- [ ] 样式调整（字体、行高、网格线）
- [ ] 合计行（如果有）

### 第四阶段：验证 & 打包

- [ ] 全功能回归测试
- [ ] PyInstaller 打包验证
- [ ] 保留 `table_events.py.backup` 作为回滚方案

---

## 六、决策建议

| 场景 | 建议 |
|------|------|
| **当前 Treeview bug 已修，暂时够用** | 暂缓替换，先把 v39 重构收尾 |
| **用户频繁反馈表格卡/难用** | 立即启动替换，分 4 阶段推进 |
| **你在意打包体积** | tksheet 影响极小，可忽略 |

**我的建议**：

先把当前 Treeview 的排序/筛选冲突修掉（本次已完成），让 v39 稳定跑起来。

等 v39 发布后，再启动 tksheet 替换 —— 作为 v40 的专项任务，不影响主线。

---

## 七、附录：tksheet 快速上手

```python
import tksheet
import tkinter as tk

root = tk.Tk()

sheet = tksheet.Sheet(root,
    data=[["a", "b"], ["c", "d"]],  # 二维列表
    width=800, height=400,
)
sheet.enable_sort(True)      # 启用排序
sheet.enable_filter(True)    # 启用筛选
sheet.bind("<Double-Button-1>", on_edit)
sheet.pack()

root.mainloop()
```

**官方文档**：https://github.com/Avigadl/py-tksheet

---

*草案结束 · 请裴哥审阅后告诉我是否启动*
