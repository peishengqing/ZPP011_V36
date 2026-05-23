# S01 导入迁移指南

**任务编号**：ZPP011-TASK-TD-003  
**更新时间**：2026-05-22 19:30  

---

## 一、导入变更对照表

| 原导入语句 | 新导入语句 | 迁移状态 |
|------------|------------|----------|
| `from utils.helpers import standardize_remark` | `from utils.helpers import standardize_remark` | ✅ 保留（纯工具） |
| `from utils.file_utils import read_excel` | `from services.file_service import FileService` | ⚠️ 需重构 |
| `from utils.excel_utils import save_excel` | `from services.export_service import ExportService` | ⚠️ 需重构 |
| `from utils.log_utils import log_message` | `from services.config_service import ConfigService` | ⚠️ 需重构 |
| `import analyzer` | `from services.data_service import DataService` | ⚠️ 需重构 |
| `from audit_presenter import AuditPresenter` | `from services.audit_service import AuditService` | ⚠️ 需重构 |

---

## 二、迁移示例

### 示例 1：文件读取

**原代码**（events.py）：
```python
from utils.file_utils import read_excel

df = read_excel(file_path)
```

**新代码**：
```python
from services.file_service import FileService
from services.data_service import DataService

file_service = FileService()
data_service = DataService()

df = data_service.load_excel(file_path)
df = data_service.clean_column_names(df)
```

### 示例 2：数据聚合

**原代码**（events.py）：
```python
# 手动计算 KPI
total_records = len(df)
total_amount = df['偏差金额'].sum()
avg_dev_rate = df['偏差率'].mean()
```

**新代码**：
```python
from services.data_service import DataService

data_service = DataService()
kpis = data_service.calculate_kpis(df)

total_records = kpis['total_records']
total_amount = kpis['total_amount']
avg_dev_rate = kpis['avg_dev_rate']
```

### 示例 3：筛选功能

**原代码**（events.py）：
```python
# 手动筛选
filters = {'工厂': '1101', '车间': '车间 1'}
filtered_df = df[
    (df['工厂'] == filters['工厂']) & 
    (df['车间'] == filters['车间'])
]
```

**新代码**：
```python
from services.filter_service import FilterService

filter_service = FilterService()
filtered_df = filter_service.apply_filters(df, filters)
```

### 示例 4：自动结案

**原代码**（events.py）：
```python
# 手动遍历
for idx, row in df.iterrows():
    if abs(row['偏差率']) <= 10 and not row.get('备注原因'):
        df.at[idx, '备注原因'] = '自动结案'
```

**新代码**：
```python
from services.audit_service import AuditService
from services.data_service import DataService
from services.filter_service import FilterService

data_service = DataService()
filter_service = FilterService()
audit_service = AuditService(data_service, filter_service)

df = audit_service.auto_close_cases(df, threshold=10.0)
```

### 示例 5：PPT 生成

**原代码**（events.py）：
```python
from ppt_generator import run_ppt_generation

run_ppt_generation(excel_path, output_path)
```

**新代码**：
```python
from services.export_service import ExportService
from services.data_service import DataService
from services.file_service import FileService

data_service = DataService()
file_service = FileService()
export_service = ExportService(data_service, file_service)

df = data_service.load_excel(excel_path, sheet_name='完整偏差明细')
export_service.generate_ppt(df, output_path, progress_callback=callback)
```

### 示例 6：审计记录存储

**原代码**（events.py）：
```python
from storage.storage import storage

storage.save_audit_records(df)
```

**新代码**：
```python
from services.storage_service import StorageService

storage_service = StorageService()
storage_service.save_audit_records(df)
```

---

## 三、迁移优先级

| 优先级 | 模块 | 影响范围 | 建议时间 |
|--------|------|----------|----------|
| **P0** | `events.py` | 核心业务逻辑 | 立即 |
| **P1** | `audit_presenter.py` | PPT 生成 | 24 小时内 |
| **P2** | `gui/app.py` | GUI 界面 | 48 小时内 |
| **P3** | `tests/*.py` | 单元测试 | 72 小时内 |

---

## 四、迁移检查清单

### 4.1 代码检查

- [ ] 搜索 `from utils import` → 结果为 0
- [ ] 搜索 `import utils` → 结果为 0（除 `utils.helpers` 外）
- [ ] 所有 Service 使用依赖注入（构造函数传参）
- [ ] 无循环导入（`python -c "import services"` 无报错）

### 4.2 功能检查

- [ ] 数据加载正常
- [ ] 筛选功能正常
- [ ] AI 审核正常
- [ ] 自动结案正常
- [ ] PPT 生成正常
- [ ] Excel 导出正常
- [ ] 审计记录存储正常

### 4.3 测试检查

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 回归测试通过

---

## 五、迁移脚本（可选）

提供自动化迁移脚本（谨慎使用）：

```bash
# 1. 备份原文件
python scripts/backup_before_migrate.py

# 2. 自动替换导入语句
python scripts/migrate_imports.py

# 3. 验证无循环导入
python -c "import services"

# 4. 运行测试
python -m pytest tests/ -v
```

---

## 六、常见问题

### Q1: 为什么要用依赖注入？

**A**: 依赖注入（Dependency Injection）可以避免循环依赖，提高代码可测试性。

**错误示例**（循环依赖）：
```python
# audit_service.py
from services.export_service import ExportService  # ❌ 循环依赖

# export_service.py
from services.audit_service import AuditService  # ❌ 循环依赖
```

**正确示例**（依赖注入）：
```python
# audit_service.py
class AuditService:
    def __init__(self, data_service: DataService, filter_service: FilterService):
        self.data_service = data_service
        self.filter_service = filter_service
```

### Q2: 如何测试 Service？

**A**: 使用 Mock 对象隔离依赖：

```python
from unittest.mock import Mock
from services.audit_service import AuditService

# 创建 Mock 依赖
mock_data_service = Mock()
mock_filter_service = Mock()

# 注入依赖
audit_service = AuditService(mock_data_service, mock_filter_service)

# 测试
result = audit_service.auto_close_cases(test_df)
assert len(result) > 0
```

### Q3: 旧代码还能用吗？

**A**: 可以。`utils/` 中的纯工具函数（如 `standardize_remark`）仍可继续使用：

```python
from utils.helpers import standardize_remark

# ✅ 正确：纯工具函数
reason = standardize_remark('堵料')
```

---

## 七、联系方式

如有迁移问题，请联系：
- **架构师**：元宝
- **实施人**：Qclaw
- **文档**：`docs/S01_implementation_report.md`

---

**文档版本**：v1.0  
**最后更新**：2026-05-22 19:30
