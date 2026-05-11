# ZPP011 偏差分析器（v36 模块化）

## ⚠️ v36 封板声明

- ✅ 本版本已完成模块化重构
- ✅ 业务逻辑 **永久冻结**
- ✅ 偏差率 / 金额 / 审核规则 **不再变更**

**后续任何修改：**
- ❌ 不得改动 `analyzer.py` 核心计算
- ❌ 不得改动 `storage.py` 审核结构
- ✅ 仅允许调整 GUI / 配置 / 新增 Sheet

**维护原则：**
> 算偏差的不动，算金额的不动，存审核的不动。

---

## 一、项目结构速览

```
E:\zpp011_dev\模块化脚本\
├── main.py              # 程序入口（只启动 GUI）
├── logger.py            # 统一日志规范
├── exceptions.py        # 异常层级定义
├── gui/                 # 界面与交互
├── analysis/            # 偏差分析与 Excel 构建
├── domain/              # 业务领域（替代料等）
├── storage/             # SQLite 审核库
├── export/              # PPT 自动生成
├── utils/               # 工具函数
└── config/              # 阈值 / 路径 / 常量
```

---

## 二、如何启动

```bash
cd E:\zpp011_dev\模块化脚本
python main.py
```

---

## 三、模块职责速记

| 目录 | 一句话职责 | 核心文件 |
|---|---|---|
| gui/ | 界面长什么样、点了干嘛 | app.py / events.py / ui_builder.py |
| analysis/ | 偏差怎么算、Excel 怎么写 | analyzer.py / sheets/ |
| domain/ | 业务概念（替代料、异常检测） | alt_material/ / anomaly/ / deviation/ |
| storage/ | 审核结果存哪 | storage.py |
| export/ | PPT 怎么生成 | ppt_generator.py |
| utils/ | 通用工具 | helpers.py |
| config/ | 所有可变配置 | settings.py / paths.py |

---

## 四、常见问题

### ❓ 改阈值去哪？
→ `config/settings.py` → `DEFAULT_THRESHOLD`

### ❓ 改 Excel 样式/颜色去哪？
→ `analysis/sheets/write_sheet_util.py` 或 `config/settings.py` → `COLORS`

### ❓ 加新 Sheet 去哪？
→ `analysis/sheets/` → 新建 `sheet11_xxx.py`

### ❓ 改按钮行为去哪？
→ `gui/events.py` → 找对应的 `_xxx` 方法

### ❓ 改备注分类逻辑去哪？
→ `utils/helpers.py` → `standardize_remark()`

---

## 五、模块依赖关系

```
main.py
  └─ gui/app.py
        ├─ gui/ui_builder.py
        └─ gui/events.py

analysis/analyzer.py
      ├─ analysis/sheets/*
      ├─ domain/alt_material/alt_manager.py
      ├─ storage/storage.py
      └─ config/settings.py

utils/helpers.py  ← 被多个模块调用
config/paths.py    ← 被 IO 相关模块调用
```

### 依赖原则（非常重要）

- ✅ gui → analysis（允许）
- ✅ analysis → domain / storage（允许）
- ❌ analysis ↛ gui（禁止）
- ❌ domain ↛ analysis（禁止）
- ❌ storage ↛ analysis（禁止）

---

## 六、异常层级规范

### 异常结构
```
├── GUIError
│   └── UserCancelError
├── AnalysisError
│   ├── DataColumnMissingError
│   └── InvalidDataError
├── StorageError
│   └── DatabaseWriteError
└── ExportError
    └── PPTGenerateError
```

### 允许/禁止表

| 层级 | 允许抛出 | 禁止抛出 |
|---|---|---|
| gui/ | GUIError, UserCancelError | sqlite3.Error, AnalysisError |
| analysis/ | AnalysisError, DataColumnMissingError, InvalidDataError | sqlite3.Error, OSError, GUIError |
| storage/ | StorageError, DatabaseWriteError | Exception, AnalysisError, GUIError |
| export/ | ExportError, PPTGenerateError | OSError(直接), AnalysisError |

### 使用口诀
> GUI 只抛 GUI 错 / 分析只抛分析错 / 存储只抛存储错 / 业务错，不准吞 / 实现错，不准漏

---

## 七、新人上手建议

1. 先跑一遍程序：`python main.py`
2. 打开 `main.py`，确认入口
3. 按本 README 对照目录
4. **不要一开始就改 `analyzer.py`**
5. 从 `gui/events.py` 入手改交互
6. 从 `config/settings.py` 入手改配置

---

## 八、日志规范（logger.py）

### 使用方法

```python
from logger import get_logger
log = get_logger("gui")       # GUI 层
log = get_logger("analysis")   # 分析层
log = get_logger("storage")   # 存储层
log = get_logger("export")    # 导出层
```

### 日志文件位置

```
temp\zpp011.log
```

### 级别使用规范

| 级别 | 场景 | 示例 |
|---|---|---|
| DEBUG | 开发调试、变量值 | `log.debug(f"读取文件：{path}")` |
| INFO | 正常流程节点 | `log.info("分析完成")` |
| WARNING | 不影响主流程的问题 | `log.warning("文件不存在")` |
| ERROR | 明确失败但能继续 | `log.error("字段缺失")` |
| CRITICAL | 程序必须终止 | `log.critical("致命错误")` |

### 禁止行为

❌ `print()` 语句禁止出现在业务代码中（用 `log.info()` 替代）

---

## 九、print 禁止清单

> 核心原则：**print 只允许出现在"临时调试脚本"**

| 允许场景 | 说明 |
|---|---|
| 一次性临时脚本 | 用完即删，不提交 |
| 交互式调试 | 不提交 |

### 禁止位置

| 位置 | 原因 |
|---|---|
| gui/ | GUI 程序不应向 stdout 说话 |
| analysis/ | 不利于排查问题 |
| storage/ | 无法区分错误级别 |
| export/ | 无法记录历史 |
| utils/ | 工具函数不应决定"怎么说" |
| config/ | 配置模块不应有副作用 |
| main.py | 启动入口应保持干净 |

### 唯一例外

```python
if __name__ == "__main__":
    print("debug only")  # 仅限本地调试，不提交仓库
```

---

## 十一、安全红线

> **能换皮，不动骨；能动配置，不动算法。**

### 明确允许的修改区域

| 区域 | 允许操作 |
|---|---|
| gui/ | 布局、美化、按钮文案 |
| config/ | 阈值、颜色、路径 |
| utils/ | 新增工具函数 |
| analysis/sheets/ | 新增 / 调整 Sheet |
| export/ppt/ | PPT 模板 / 样式 |
| logger.py | 日志格式 / 级别 |
| exceptions.py | 新增异常类型 |

### 明确禁止的区域（红线）

| 区域 | 原因 |
|---|---|
| analyzer.py | 核心计算逻辑 |
| domain/alt_material/ | 业务规则 |
| storage/storage.py | 审核数据一致性 |
| 偏差率 / 金额算法 | 财务准确性 |

### 需要双人确认的区域

| 区域 | 条件 |
|---|---|
| analysis/analyzer.py | 任何逻辑修改 |
| Sheet 数据结构 | 影响 Excel |
| 审核字段 | 影响 SQLite |

---

## 十二、版本记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v36 | 2026-05-11 | 模块化重构完成 |
