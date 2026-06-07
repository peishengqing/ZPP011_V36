# ZPP011 PySide6 迁移方案（QTableView 版）

> 版本：v1.0 | 日期：2026-06-03 | 签发：裴哥

---

## 一、现状分析

### 当前技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| GUI 框架 | tkinter + ttk | Python 内置，无需额外依赖 |
| 表格控件 | ttk.Treeview | 功能弱，排序/筛选需手动实现，大数据卡顿 |
| 图标/主题 | 自定义 C 字典 + clam 主题 | 颜色字典 `widgets.C` |
| 日期选择 | tkcalendar.DateEntry | 第三方，需 pip install |

### 受影响的文件清单

**必须全部重写的文件（直接依赖 tkinter）：**

| 文件 | 行数(约) | 迁移难度 | 说明 |
|------|-----------|----------|------|
| `gui/app.py` | 300 | ⭐⭐⭐⭐ | 主窗口类 ZPP011Beautiful，核心入口 |
| `gui/ui_builder.py` | 400 | ⭐⭐⭐⭐⭐ | 全部 UI 构建逻辑，工作量最大 |
| `gui/events.py` | 166 | ⭐⭐ | 入口 + ModeSelector，需适配 QApplication |
| `gui/filter_panel.py` | 300 | ⭐⭐⭐ | 侧边栏筛选面板，全部 tkinter 控件 |
| `gui/event_handlers/table_events.py` | 2500 | ⭐⭐⭐⭐⭐ | Treeview 操作核心，2500 行需全部重写 |
| `gui/event_handlers/table_values_builder.py` | 200 | ⭐⭐⭐ | Treeview values 构建，适配 QAbstractTableModel |
| `gui/event_handlers/audit_core_events.py` | 500 | ⭐⭐⭐ | 审核逻辑，UI 部分需改 |
| `gui/event_handlers/audit_batch_events.py` | 600 | ⭐⭐⭐ | 批量操作，UI 部分需改 |
| `gui/event_handlers/analysis_events.py` | 700 | ⭐⭐⭐ | 分析事件，UI 部分需改 |
| `gui/event_handlers/export_events.py` | 300 | ⭐⭐ | 导出事件，UI 部分较少 |
| `gui/event_handlers/menu_events.py` | 200 | ⭐⭐ | 菜单事件，需改菜单创建方式 |
| `gui/event_handlers/ui_helpers.py` | 150 | ⭐⭐⭐ | UI 辅助，可能依赖 tkinter 控件 |
| `gui/event_handlers/utils_events.py` | 200 | ⭐⭐ | 工具事件，UI 部分需改 |
| `gui/benefit_report_dialog.py` | 400 | ⭐⭐⭐⭐ | 对话框，tkcalendar 需替换 |
| `gui/health_check_dialog.py` | 150 | ⭐⭐ | 对话框，需重写 |
| `gui/history_compare_dialog.py` | 200 | ⭐⭐ | 对话框，需重写 |
| `gui/import_wizard.py` | 300 | ⭐⭐⭐ | 导入向导，较复杂 |
| `gui/inventory_view.py` | 250 | ⭐⭐⭐ | 库存视图，另一个模式的主界面 |
| `gui/management_dashboard.py` | 500 | ⭐⭐⭐⭐ | 管理看板，matplotlib 嵌入 tkinter |
| `gui/rule_config_dialog.py` | 300 | ⭐⭐⭐ | 规则配置对话框 |
| `gui/tree_utils.py` | 100 | ❌ | **直接删除**，Treeview 相关工具函数 |
| `gui/stock_*.py` | 300 | ⭐⭐⭐ | 库存相关 UI |

**不需要改的文件（纯业务逻辑，无 tkinter 依赖）：**

`core/*`、`analysis/*`、`modules/*`、`config/*`、`utils/*`、`widgets.py`（颜色字典，需保留但改格式）

---

## 二、PySide6 对应关系

### 控件映射表

| tkinter | PySide6 | 说明 |
|---------|----------|------|
| `tk.Tk()` | `QApplication` + `QMainWindow` | 应用入口 |
| `ttk.Frame` | `QWidget` / `QFrame` | 容器 |
| `ttk.Label` | `QLabel` | 文本标签 |
| `ttk.Entry` / `tk.Entry` | `QLineEdit` | 单行输入 |
| `ttk.Button` | `QPushButton` | 按钮 |
| `ttk.Combobox` | `QComboBox` | 下拉选择 |
| `ttk.Checkbutton` | `QCheckBox` | 复选框 |
| `ttk.Radiobutton` | `QRadioButton` | 单选框 |
| `ttk.Progressbar` | `QProgressBar` | 进度条 |
| `ttk.Treeview` | **`QTableView` + `QAbstractTableModel`** | 核心迁移点 |
| `ttk.Notebook` | `QTabWidget` | 标签页 |
| `tk.scrolledtext` | `QTextEdit` / `QPlainTextEdit` | 多行文本 |
| `tk.messagebox` | `QMessageBox` | 弹窗提示 |
| `tk.filedialog` | `QFileDialog` | 文件选择 |
| `tk.simpledialog` | `QInputDialog` | 简单输入对话框 |
| `tkcalendar.DateEntry` | `QDateEdit` | 日期选择（PySide6 内置） |
| `tk.Menu` / `root.menu_add` | `QMenuBar` + `QMenu` | 菜单栏 |
| `tk.Toplevel` | `QDialog` / `QMainWindow` | 子窗口 |
| `ttk.LabelFrame` | `QGroupBox` | 分组框 |
| `tk.Canvas` | `QGraphicsView` / `QChartView` | 图表（matplotlib 可嵌入） |
| `widgets.C` 颜色字典 | Qt StyleSheet | 样式表替代 |

### 布局管理器映射

| tkinter | PySide6 | 说明 |
|---------|----------|------|
| `pack()` | `QVBoxLayout` / `QHBoxLayout` | 线性布局 |
| `grid()` | `QGridLayout` | 网格布局 |
| `place()` | 绝对定位（不推荐）| — |

> ⚠️ **注意**：tkinter 的 `pack`/`grid`/`place` 不能混用，PySide6 的 Layout 体系更严格，需要整体规划布局结构。

---

## 三、核心迁移点：Treeview → QTableView

这是整个迁移中**工作量最大、风险最高**的部分。

### 当前 Treeview 用法梳理

`table_events.py` 中 Treeview 的操作方式：

```python
# 当前用法（tkinter）
self.audit_tree = ttk.Treeview(parent, columns=col_ids, show='headings')
self.audit_tree.insert('', 'end', values=row_values)  # 插入行
self.audit_tree.set(item, 'remark', new_value)        # 修改单元格
self.audit_tree.delete(*items)                         # 删除行
self.audit_tree.selection()                             # 获取选中行
self.audit_tree.yview_scroll()                         # 滚动
```

### QTableView 对应实现

PySide6 使用 **Model-View** 架构，数据不直接操作 View，而是通过 Model：

```python
# PySide6 用法
class AuditTableModel(QAbstractTableModel):
    def __init__(self, data: pd.DataFrame):
        super().__init__()
        self._data = data

    def rowCount(self, parent=...): ...
    def columnCount(self, parent=...): ...
    def data(self, index, role=...): ...
    def headerData(self, section, orientation, role=...): ...

# View 绑定 Model
self.table_view = QTableView()
self.model = AuditTableModel(self.audit_data)
self.table_view.setModel(self.model)

# 插入行 → 在 Model 中操作 _data，然后 layoutChanged.emit()
# 修改单元格 → 在 Model 中 setData()，自动刷新 View
# 删除行 → 在 Model 中 removeRows()
# 获取选中行 → self.table_view.selectionModel().selectedRows()
```

### 功能对比

| 功能 | tkinter Treeview（当前实现） | PySide6 QTableView（迁移后） |
|------|---------------------------|----------------------------|
| 数据绑定 | 手动 insert/delete，数据在 View 里 | Model-View 分离，数据在 DataFrame 里 |
| 排序 | 手动实现（`_apply_sort_and_refresh`）| **内置**，`setSortingEnabled(True)` |
| 筛选 | 手动实现（`FilterEngine`）| 可用 `QSortFilterProxyModel` 简化 |
| 单元格编辑 | 手动弹窗 + `tree.set()` | **内置**，重写 `setData()` 即可 |
| 虚拟滚动 | 需手动实现 `displaycolumns` | **内置**，`setRowHidden()` 或 Model 分页 |
| 列宽拖拽 | 支持（需手动保存）| **内置**，`horizontalHeader().setSectionResizeMode()` |
| 复选框列 | 手动用 `text="☑"` | **内置**，`CheckStateRole` |
| 颜色单元格 | 手动 `tag_configure` | **内置**，`BackgroundRole` |
| 右键菜单 | `bind("<Button-3>")` | **内置**，`setContextMenuPolicy()` |
| 大数据性能 | >5000 行明显卡顿 | >50000 行仍流畅（内置虚拟渲染） |

### 迁移策略

**不建议**逐行翻译 Treeview 操作，而是：

1. **保留 `self.audit_data`（DataFrame）为唯一数据源**
2. **`AuditTableModel` 只做 DataFrame → Qt 的桥梁**，不直接修改数据
3. **所有数据修改操作**（审核、备注、筛选）**直接操作 DataFrame**
4. **操作后调用 `model.layoutChanged.emit()` 刷新 View**

这样 `table_events.py` 中约 60% 的代码（直接操作 Treeview 的代码）可以删除，改为操作 DataFrame + 触发刷新。

---

## 四、分阶段实施计划

### 阶段 0：准备（1~2 天）

**目标**：环境就绪，验证 PySide6 可行性

- [ ] `pip install PySide6` 验证安装
- [ ] 写最小 Demo：QMainWindow + QTableView + pandas DataFrame 显示
- [ ] 验证 PySide6 打包（`build_exe.py` 需修改，PySide6 的 plugin 路径不同）
- [ ] 确认 `widgets.C` 颜色字典 → Qt StyleSheet 的转换方案
- [ ] 新建分支 `feature/pyside6-migration`

**交付物**：`docs/pyside6_demo.py`（最小可运行 Demo）

---

### 阶段 1：骨架搭建（3~5 天）

**目标**：PySide6 主窗口能启动，左侧面板 + 右侧表格区域布局完成，表格能显示数据（只读）

- [ ] 重写 `gui/events.py:run_app()` → 创建 `QApplication` + `QMainWindow`
- [ ] 重写 `gui/app.py:ZPP011Beautiful` → 继承 `QMainWindow`
- [ ] 重写 `gui/ui_builder.py` → 用 `QHBoxLayout`/`QVBoxLayout` 搭建布局
  - 顶部标题栏（`QWidget` + `QHBoxLayout`）
  - 左侧文件选择卡片（`QGroupBox`）
  - 左侧筛选面板（`QGroupBox` + `QFormLayout`）
  - 右侧主表格区域（`QTableView`）
  - 底部状态栏（`QStatusBar`）
- [ ] 实现 `AuditTableModel`（只读，显示 DataFrame）
- [ ] 迁移颜色方案：`widgets.C` → `qss/style.qss`（Qt StyleSheet 文件）
- [ ] 验证：启动程序，加载 Excel，表格正确显示数据

**交付物**：程序能启动，表格显示数据，但所有按钮/菜单无功能

---

### 阶段 2：表格交互（5~7 天）

**目标**：表格支持排序、筛选、选中、双击编辑，功能等同当前 Treeview

- [ ] 实现 `AuditTableModel.setData()` — 支持单元格编辑
- [ ] 实现 `AuditTableModel.flags()` — 控制哪些列可编辑
- [ ] 表格排序：`tableView.setSortingEnabled(True)` + Model 支持 `sort()`
- [ ] 表格筛选：实现 `AuditSortFilterProxyModel`（替代当前 `FilterEngine` 的表格部分）
- [ ] 选中行操作：`selectionModel().selectedRows()` 替代 `tree.selection()`
- [ ] 右键菜单：`setContextMenuPolicy(Qt.CustomContextMenu)` 替代 `bind("<Button-3>")`
- [ ] 双击编辑：`doubleClicked` 信号替代 `bind("<Double-1>")`
- [ ] 复选框列：`CheckStateRole` 替代手动 `text="☑"`
- [ ] 颜色单元格：`BackgroundRole` 替代 `tag_configure`
- [ ] 滚动保持：`scrollTo()` 替代 `see()`

**交付物**：表格交互完全可用，排序/筛选不冲突（当前 bug 根治）

---

### 阶段 3：事件处理迁移（5~7 天）

**目标**：所有按钮、菜单、事件处理逻辑迁移到 PySide6

- [ ] 重写 `gui/event_handlers/table_events.py`
  - `Treeview` 操作全部改为 `Model` 操作
  - 信号连接：`cellChanged` → `on_cell_changed`，替代 `tree.bind("<<TreeviewSelect>>")`
- [ ] 重写 `gui/event_handlers/audit_core_events.py`
  - `messagebox` → `QMessageBox`
  - `filedialog` → `QFileDialog`
- [ ] 重写 `gui/event_handlers/audit_batch_events.py`
- [ ] 重写 `gui/event_handlers/analysis_events.py`
- [ ] 重写 `gui/event_handlers/export_events.py`
- [ ] 重写 `gui/event_handlers/menu_events.py`
  - `root.menu_add()` → `menuBar().addMenu()`
- [ ] 重写 `gui/event_handlers/ui_helpers.py`
- [ ] 重写 `gui/event_handlers/utils_events.py`
- [ ] 删除 `gui/tree_utils.py`

**交付物**：所有按钮/菜单功能正常，AI 审核/导出/分析均可执行

---

### 阶段 4：对话框与子窗口（3~5 天）

**目标**：所有对话框、子窗口迁移完成

- [ ] 重写 `gui/benefit_report_dialog.py`（`QDialog`）
- [ ] 重写 `gui/health_check_dialog.py`
- [ ] 重写 `gui/history_compare_dialog.py`
- [ ] 重写 `gui/import_wizard.py`
- [ ] 重写 `gui/rule_config_dialog.py`
- [ ] 重写 `gui/management_dashboard.py`（matplotlib 嵌入 `QChartView`）
- [ ] 重写 `gui/inventory_view.py`（另一个模式的主界面）
- [ ] `tkcalendar.DateEntry` → `QDateEdit`（PySide6 内置，无需额外依赖）

**交付物**：所有对话框功能正常

---

### 阶段 5：打包与验证（2~3 天）

**目标**：PySide6 版本成功打包为 exe

- [ ] 修改 `build_exe.py`：PySide6 的 plugin 路径（`plugins/platforms/` 等）需加入打包
- [ ] 验证 `PyInstaller` + PySide6 打包成功
- [ ] 验证 exe 在干净环境中可运行（无 Python 环境）
- [ ] 功能验证清单：
  - [ ] 启动验证
  - [ ] 加载 Excel 文件
  - [ ] AI 审核
  - [ ] 导出
  - [ ] 排序 + 筛选
  - [ ] 所有对话框

**交付物**：`ZPP011偏差分析器_v42.0_PySide6.exe`

---

### 阶段 6：清理与发布（1~2 天）

- [ ] 删除所有 tkinter 相关代码
- [ ] 更新 `requirements.txt`（去掉 tkinter 相关，加入 PySide6）
- [ ] 更新 `docs/` 中的使用文档
- [ ] Git 合并 `feature/pyside6-migration` → `main`
- [ ] 发布 v42.0

---

## 五、风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| PySide6 打包后 exe 体积暴增 | 高 | 中 | PySide6 ~120MB，比 tkinter 大 ~40MB，可接受 |
| PySide6 打包后运行报错（plugin 缺失）| 高 | 高 | 提前验证 `QApplication.addLibraryPath()`，参考 PyInstaller 官方 PySide6 hook |
| 业务逻辑被误改（不止 UI）| 中 | 高 | 核心逻辑（`core/`、`analysis/`、`modules/`）不动，只改 `gui/` |
| 布局还原度不高（界面丑）| 中 | 中 | 用 Qt StyleSheet 精细调整，参考当前 `widgets.C` 颜色方案 |
| matplotlib 嵌入 PySide6 有问题 | 中 | 中 | 用 `matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg`，PySide6 兼容 |
| 开发期间 v41.x 的 bug 修复无法合并 | 高 | 中 | 在 `main` 分支继续修 v41.x，迁移完成后合并 |
| AI 审核等功能依赖 `self.audit_tree` 属性 | 高 | 高 | 全局搜索 `self.audit_tree`，全部改为 `self.table_view` + `self.model` |

---

## 六、文件变更统计

| 操作 | 文件数 | 说明 |
|------|--------|------|
| **删除** | 1 | `gui/tree_utils.py` |
| **全部重写** | ~20 | `gui/*.py` + `gui/event_handlers/*.py` |
| **小幅修改** | ~5 | `build_exe.py`、`main.py`、`utils/version_history.py` |
| **新建** | 2 | `gui/models/audit_table_model.py`、`qss/style.qss` |
| **不动** | ~50 | `core/`、`analysis/`、`modules/`、`config/`、`utils/` |

**预计总行数变化**：当前 `gui/` 约 8000 行，迁移后预计 **6000~7000 行**（Model-View 架构减少冗余代码）。

---

## 七、决策检查点

在开始阶段 1 之前，请确认以下决定：

- [ ] **PySide6 版本**：建议 `PySide6==6.6.x`（稳定版），不要用最新版
- [ ] **Python 版本**：当前用 3.11，PySide6 6.6 支持 3.9~3.12，无需升级 Python
- [ ] **迁移期间 v41.x 维护**：是否在 `main` 分支继续发布 v41.4/v41.5 bug 修复？
- [ ] **打包工具**：继续用 `PyInstaller`（需验证 PySide6 hook），还是换 `Nuitka`？
- [ ] **目标版本号**：迁移完成后发布 v42.0，还是延续 v41.x？

---

## 八、总结

| 项目 | 说明 |
|------|------|
| **总工作量** | 约 **3~4 周**（1 人） |
| **最大风险** | PySide6 打包（plugin 路径问题） |
| **最大收益** | 排序/筛选 bug 根治，大数据性能提升，界面现代化 |
| **能否回退** | 能，`feature/pyside6-migration` 分支独立，不影响 `main` |
| **建议** | **先完成阶段 0（Demo 验证），再决定是否继续** |

---

*本方案由 Qclaw 拟定，待裴哥确认后启动阶段 0。*
