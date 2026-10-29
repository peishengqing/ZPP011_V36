# ZPP011 数据分析平台使用说明书

## 📋 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [服务层详解](#3-服务层详解)
4. [使用指南](#4-使用指南)
5. [API 参考](#5-api-参考)
6. [常见问题](#6-常见问题)
7. [维护指南](#7-维护指南)

---

## 1. 项目概述

### 1.1 项目简介
ZPP011 是一个基于 PySide6 的数据分析平台，专注于替代料偏差预警、数据审核、变更检测等工厂数据分析场景。平台采用模块化设计，实现了文件加载、数据预处理、状态恢复、审核处理、报表生成等完整工作流。

### 1.2 技术栈
- **GUI 框架**: PySide6
- **数据处理**: pandas, numpy
- **数据库**: SQLite (通过 peewee ORM)
- **设计模式**: 服务层模式、依赖注入、信号槽机制

### 1.3 主要特性
- 📊 **多源数据导入**: 支持 Excel 文件导入和解析
- 🔍 **变更检测**: 自动识别已审核数据的变动（数量、备注等）
- 🛡️ **隔离区管理**: 隔离可疑数据，防止误操作
- 📈 **实时看板**: 替代料偏差预警看板，支持筛选和标记
- 📋 **审核工作流**: 完整的审核、备注、状态管理系统
- 🔔 **变动通知**: 变动记录弹窗提醒，标记已读时序清晰

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────┐
│              GUI 视图层                          │
│  MainWindow, Components, Views, Dialogs         │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│  控制器层 (Controllers)                           │
│  AnalysisController, AuditController, ...         │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│  服务层 (Services)                                │
│  DataService (协调器)                             │
│  ├── DataPreprocessor (数据预处理)                │
│  ├── ReadStatusService (状态与变更检测)          │
│  ├── AuditResultService (审核结果恢复)           │
│  └── QuarantineService (隔离区状态)              │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│  核心功能层 (Core)                                 │
│  read_status.py, fingerprint.py, quarantine.py  │
└─────────────────────────────────────────────────┘
```

### 2.2 服务层职责

| 服务 | 职责 | 关键方法 |
|------|------|----------|
| **DataService** | 协调各子服务，提供统一数据接口 | `preprocess_audit_data()`, `get_factory_data()` |
| **DataPreprocessor** | 数据清洗、规范化、增强 | `clean_columns()`, `add_data_id_and_fingerprint()` |
| **ReadStatusService** | 读取状态恢复、变更检测 | `restore_read_status()`, `detect_and_notify_changes()` |
| **AuditResultService** | 审核结果数据恢复 | `restore_audit_results()` |
| **QuarantineService** | 隔离区状态管理 | `restore_quarantine_status()` |

### 2.3 核心数据流

```
Excel 文件 → 解析 → DataFrame → DataService.preprocess_audit_data()
                                                   ↓
                                            数据预处理流水线:
                                            1. 清理冗余列
                                            2. 数值转换
                                            3. 添加 DataID
                                            4. 恢复读取状态
                                            5. 恢复审核结果
                                            6. 变动检测
                                            7. 列重排
                                                   ↓
                                            展示到 GUI
```

---

## 3. 服务层详解

### 3.1 DataService - 统一数据服务层

`DataService` 是应用的核心协调器，负责管理所有子服务并提供统一的数据处理接口。

#### 初始化
```python
from gui_pyside6.services.data_service import DataService
data_service = DataService()
```

#### 核心方法

##### `preprocess_audit_data(df, previous_df=None) -> pd.DataFrame`

**功能**: 完整的数据处理工作流

**参数**:
- `df` (pd.DataFrame): 原始数据 DataFrame
- `previous_df` (pd.DataFrame, optional): 上一次的数据（用于变动检测）

**处理步骤**:
1. **数据清洗**:
   - 清理冗余列（替代料组、净偏差、偏差率等）
   - 去除重复列
2. **列名规范化**:
   - 偏差率数值列统一为 `偏差率(%)`
   - 自动转换字符串格式为数值格式
3. **数据增强**:
   - 添加 `data_id` 唯一标识
   - 添加 `fingerprint` 指纹（金额|率）
4. **状态恢复**:
   - 从 SQLite 恢复读取状态（`_read`, `_read_source`）
   - 恢复审核结果（`审核结果`, `备注来源`）
   - 恢复隔离区状态（`_quarantined`）
5. **变动检测** (如果提供 `previous_df`):
   - 检测已审核记录的变动（实际数量、备注原因、产量）
   - 标记为未读并弹窗提醒
6. **列重排**:
   - 将有关系列放在一起（如偏差率移到偏差金额后）
   - 调整产量相关列位置

**示例**:
```python
df = data_service.preprocess_audit_data(raw_df)
```

##### `get_factory_data(df) -> dict`

**功能**: 按工厂分组 DataFrame

**返回**: 字典 `{工厂名: 分组后的 DataFrame}`

**示例**:
```python
factories = data_service.get_factory_data(df)
# {'南京': df1, '上海': df2}
```

##### `get_combined_factory_data(df) -> tuple`

**功能**: 获取按工厂分组的数据和全部数据

**返回**: `(factories_dict, all_data.DataFrame)`

**示例**:
```python
factories, all_data = data_service.get_combined_factory_data(df)
```

##### `get_audit_changes(df) -> list`

**功能**: 获取审核变更详情

---

### 3.2 DataPreprocessor - 数据预处理服务

负责数据的清洗、规范化、增强和重排。

#### 配置常量

```python
# 数值列定义
NUMERIC_COLUMN_DEFS = [
    '定额', '实际', '偏差数量', '偏差金额', '偏差金额(含税)',
    '净偏差数量', '净偏差金额', '净偏差率(%)'
]

# 冗余列对（移除列表，保留第二个）
REDUNDANT_COL_PAIRS = [
    ('替代料组', '_替代料组'),
    ('净偏差', '净偏差金额'),
    ('净偏差', '净偏差数量'),
    ('偏差率', '偏差率(%)')
]
```

#### 核心方法

##### `clean_columns(df) -> pd.DataFrame`

**功能**: 清理冗余列和重复列

**移除的规则**:
1. `替代料组` 列（保留 `_替代料组`）
2. `净偏差` 列（保留 `净偏差金额`、`净偏差数量`）
3. `偏差率` 字符串列（保留 `偏差率(%)` 数值列）
4. 数据库中的重复列（保留第一个）

##### `convert_numeric_cols(df) -> pd.DataFrame`

**功能**: 确保关键数值列为数值类型

**处理**:
1. `偏差率(%)` 和 `偏差率` 列：移除 % 符号并转换为数值
2. 其他数值列（定额、实际、偏差数量等）确保为数值类型
3. 如果 `偏差率` 列为空，从 `偏差率(%)` 自动生成

##### `normalize_alt_flag(df) -> pd.DataFrame`

**功能**: 标准化是否替代料标识

**规则**:
- 空值或非正项 → "否"
- "是"、"true"、"1"、"yes"、"y"、包含"替代"或"alt" → "是"

##### `add_data_id_and_fingerprint(df) -> pd.DataFrame`

**功能**: 添加数据唯一标识和指纹

**DataID 规则**:
- 有工厂列: `工厂|订单日期|流程订单|物料编码`
- 无工厂列: `订单日期|流程订单|物料编码`

**Fingerprint 规则**: `偏差金额（保留2位小数）|偏差率(%)（保留1位小数）`

##### `reorder_columns(df) -> pd.DataFrame`

**功能**: 调整列顺序

**规则**:
1. `偏差率(%)` 移到 `偏差金额` 或 `偏差金额(含税)` 后面
2. `产量` 和 `产量单位` 移到 `产品物料描述` 后面

---

### 3.3 ReadStatusService - 读取状态与变更检测服务

负责恢复读取状态和检测已审核记录的变更。

#### 核心方法

##### `restore_read_status(df) -> pd.DataFrame`

**功能**: 恢复已读状态并检测变更

**基线策略**:
- 从数据库加载历史状态和快照
- 无基线的新记录 → 静默建立基线（使用当前值）
- 有基线的旧记录 → 与当前值比对

**变更检测**:
- 实际数量变化 → 标记未读，行红标
- 备注原因变化 → 标记未读，行红标
- 产量变化 → 标记未读，行红标

**返回**: 添加以下列的 DataFrame:
- `_read` (int): 0=未读, 1=已读
- `_read_source` (str): 来源（manual, 系统标记等）
- `_post_audit_changed` (int): 0=无变更, 1=有变更

##### `detect_and_notify_changes(old_df, new_df)`

**功能**: 同会话重新分析时，检测已审核记录的变动

**使用场景**: 用户重新加载数据，需要对比历史状态

**通知方式**:
- 记录变动历史到数据库
- 触发 `log_signal` 发送警告
- 在 `last_audit_changes` 存储变动详情

##### `get_audit_changes(df) -> list`

**功能**: 获取审核变更详情（从理论上来）

**返回**: 变更列表，包含 `(data_id, field, old_value, new_value)`

##### `mark_changes_as_read(changes, df)`

**功能**: 把变动记录一次性标记为已读，并重建快照基线

---

### 3.4 AuditResultService - 审核结果恢复服务

从数据库恢复审核结果和备注来源。

#### 核心方法

##### `restore_audit_results(df) -> pd.DataFrame`

**功能**: 恢复 `审核结果` 和 `备注来源` 两列

**实现**:
- 优先使用 `merge` 向量化操作（性能优化）
- 回退到 `map(lambda)` 逻辑

**AI 建议**: 已停用，该列会强制清空

**返回**: 添加了 `审核结果` 和 `备注来源` 列的 DataFrame

---

### 3.5 QuarantineService - 隔离区状态服务

管理隔离区状态，标记嫌疑数据。

#### 核心方法

##### `restore_quarantine_status(df) -> pd.DataFrame`

**功能**: 添加隔离标记列 `_quarantined`

**规则**:
- `data_id` 在隔离列表 → `_quarantined = 1`
- 否则 → `_quarantined = 0`

**返回**: 添加 `_quarantined` 列的 DataFrame

---

### 3.6 DataGrouping - 数据分组函数

提供数据分组功能，按指定列拆分 DataFrame。

#### 函数定义

```python
# data_grouping.py
# 注意：已从类改为纯函数

def process_analysis_results(df: pd.DataFrame, groupby_col: str = '工厂', ...) -> dict
def get_combined_factory_data(df: pd.DataFrame, groupby_col: str = '工厂') -> tuple
```

---

### 3.7 Utils - 通用工具函数

提供跨服务使用的通用函数。

#### 核心函数

- `find_real_qty_col(df) -> str`: 查找实际数量列名
- `find_remark_col(df) -> str`: 查找备注列名
- `find_yield_col(df) -> str`: 查找产量列名
- `norm_note(v) -> str`: 规范化备注文本
- `safe_qty(v) -> float|None`: 安全转换数量为数值
- `build_data_id(row: dict, df: pd.DataFrame) -> str`: 构建唯一 data_id
- `classify_row_color_keys(df) -> list`: 自动分类行颜色规则

---

## 4. 使用指南

### 4.1 快速开始

#### 导入服务
```python
from gui_pyside6.services.data_service import DataService
init_data_service = DataService()
```

#### 导入文件
```python
import pandas as pd
df = pd.read_excel("data.xlsx")
```

#### 预处理
```python
df = init_data_service.preprocess_audit_data(df)
```

#### 查看按工厂分组
```python
factories = init_data_service.get_factory_data(df)
for factory, factory_df in factories.items():
    print(f"{factory}: {len(factory_df)} 行")
```

---

### 4.2 完整工作流

#### 数据加载与处理
```python
# 1. 加载原始数据
df = pd.read_excel("data.xlsx")

# 2. 历史数据（用于变动检测）
previous_df = None  # 如果没有历史记录，不传

# 3. 预处理
df = data_service.preprocess_audit_data(df, previous_df)

# 4. 检查状态
print(f"未读记录: {len(df[df['_read'] == 0])}")
print(f"已审核记录: {len(df[df['审核状态'] == '已审核'])}")
print(f"隔离记录: {len(df[df['_quarantined'] == 1])}")

# 5. 创建视图模型
from api.views.data_view import DataView
view_model = DataView(df)
```

#### 变动检测
```python
# 同会话重新分析
previous_df = load_previous_data()  # 从记忆或临时状态恢复
data_service.read_status_service.detect_and_notify_changes(previous_df, df)

# 获取变更详情
changes = data_service.get_audit_changes(df)
if changes:
    print(f"发现 {len(changes)} 条变更记录")
```

---

### 4.3 高级功能

#### 恢复读取状态
```python
data_ids = df['data_id'].tolist()
status_map = data_service.read_status_service.get_read_status(data_ids)
df = data_service.read_status_service.restore_read_status(df)
```

#### 标记变动为已读
```python
changes = data_service.last_audit_changes
data_service.mark_changes_as_read(changes, df)
```

#### 隔离区管理
```python
from core.quarantine_manager import get_quarantined_ids, quarantine_ids, release_ids

# 隔离指定 data_id
quarantine_ids(['id1', 'id2'])
df = data_service.quarantine_service.restore_quarantine_status(df)

# 释放隔离
release_ids(['id1'])
```

---

## 5. API 参考

### 5.1 DataService API

| 方法 | 参数 | 返回 | 描述 |
|------|------|------|------|
| `preprocess_audit_data` | `df: pd.DataFrame`, `previous_df: pd.DataFrame` | `pd.DataFrame` | 完整数据处理工作流 |
| `get_factory_data` | `df: pd.DataFrame` | `dict` | 按工厂分组 |
| `get_combined_factory_data` | `df: pd.DataFrame` | `tuple(dict, DataFrame)` | 工厂分组和全部数据 |
| `log` | `msg: str`, `level: str` | `None` | 日志输出 |

### 5.2 DataPreprocessor API

| 方法 | 参数 | 返回 | 描述 |
|------|------|------|------|
| `clean_columns` | `df: pd.DataFrame` | `pd.DataFrame` | 清理冗余和重复列 |
| `convert_numeric_cols` | `df: pd.DataFrame` | `pd.DataFrame` | 数值列转换 |
| `normalize_alt_flag` | `df: pd.DataFrame` | `pd.DataFrame` | 标准化替代料标识 |
| `add_data_id_and_fingerprint` | `df: pd.DataFrame` | `pd.DataFrame` | 添加标识和指纹 |
| `reorder_columns` | `df: pd.DataFrame` | `pd.DataFrame` | 调整列顺序 |
| `snapshot_qty_for` | `df: pd.DataFrame`, `data_id` | `float|None` | 获取指定数据的实际数量 |
| `snapshot_note_for` | `df: pd.DataFrame`, `data_id` | `str` | 获取指定数据的备注原因 |

### 5.3 ReadStatusService API

| 方法 | 参数 | 返回 | 描述 |
|------|------|------|------|
| `restore_read_status` | `df: pd.DataFrame` | `pd.DataFrame` | 恢复读取状态 |
| `detect_and_notify_changes` | `old_df: pd.DataFrame`, `new_df: pd.DataFrame` | `None` | 检测并通知变动 |
| `mark_changes_as_read` | `changes: list`, `df: pd.DataFrame` | `int` | 标记变动为已读 |

### 5.4 AuditResultService API

| 方法 | 参数 | 返回 | 描述 |
|------|------|------|------|
| `restore_audit_results` | `df: pd.DataFrame` | `pd.DataFrame` | 恢复审核结果 |

### 5.5 QuarantineService API

| 方法 | 参数 | 返回 | 描述 |
|------|------|------|------|
| `restore_quarantine_status` | `df: pd.DataFrame` | `pd.DataFrame` | 恢复隔离状态 |

### 5.6 Utils API

| 函数 | 参数 | 返回 | 描述 |
|------|------|------|------|
| `find_real_qty_col` | `df: pd.DataFrame` | `str` | 查找实际数量列 |
| `find_remark_col` | `df: pd.DataFrame` | `str` | 查找备注列 |
| `find_yield_col` | `df: pd.DataFrame` | `str` | 查找产量列 |
| `norm_note` | `v` | `str` | 规范化备注 |
| `safe_qty` | `v` | `float|None` | 安全数量转换 |
| `build_data_id` | `row: dict`, `df: pd.DataFrame` | `str` | 构建 data_id |

---

## 6. 常见问题

### Q1: 为什么数据提示变动？
**A**: 变更检测功能发现已审核记录的以下内容发生变化：
- 实际数量变化
- 备注原因变化
- 产量变化

该记录会被标记为未读并显示红色背景。

### Q2: 如何清除变动检测？
**A**: 使用 `mark_changes_as_read(changes, df)` 方法，将变动记录标记为已读并重建基线。

### Q3: 为什么有些审核结果没有恢复？
**A**: 可能的原因：
1. 数据库中没有历史记录
2. `data_id` 格式不正确
3. 网络连接问题（如使用云端数据库）

### Q4: 如何自定义清理规则？
**A**: 修改 `data_preprocessor.py` 中的配置常量：
```python
# 添加新的冗余列对
REDUNDANT_COL_PAIRS = [
    ('替代料组', '_替代料组'),
    ('净偏差', '净偏差金额'),
    # 添加新的列对
    ('旧列', '新列'),
]
```

### Q5: 变动检测不工作怎么办？
**A**: 确保提供了 `previous_df` 参数，并且数据包含 `data_id` 列。

### Q6: 如何重置整个状态？
**A**: 销毁并重新创建 `DataService` 实例。

---

## 7. 维护指南

### 7.1 数据库维护

**备份数据库**:
```python
import shutil
import os

from core.read_status import get_db_path
db_path = get_db_path()
backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy(db_path, backup_path)
```

**清理旧数据**:
```python
from core.read_status import clear_read_status_history, clear_audit_changes
clear_read_status_history(days_old=30)
clear_audit_changes(days_old=30)
```

### 7.2 日志分析

**日志级别**:
- `info`: 一般信息
- `warning`: 警告（如数据变动）
- `error`: 错误
- `alert`: 重要通知

### 7.3 性能调优

**配置**:
- 数据库锁定超时：核心配置
- 并发数：根据系统资源调整
- 批处理大小：已读批量提交大小

**监控**:
- 数据库连接数
- 内存使用情况
- 响应时间

### 7.4 代码组织

**入口点**: `main_window.py`
**服务协调**: `data_service.py`
**核心逻辑**: `core/` 目录

### 7.5 测试

**单元测试**:
```bash
pytest tests/unit/
```

**集成测试**:
```bash
# 需要测试数据
pytest tests/integration/
```

---

## 📞 支持与反馈

- **项目主页**: 内部 Git 仓库
- **问题反馈**: 联系开发团队
- **技术支持**: 部门内部系统

---

## 📝 版本信息

| 版本 | 日期 | 备注 |
|------|------|------|
| v1.0 | 2026-06-23 | 初始 PySide6 迁移版 |
| v42.0 | 2026-09-28 | 首个稳定版本 |
| v43.0 | 2026-10-29 | 服务层重构完成 |

---

**文档维护**: [裴哥]  
**最后更新**: 2026-10-29
