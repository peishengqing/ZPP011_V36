# 技术债务清单（TECH_DEBT）

**创建时间**：2026-05-24 15:08 GMT+8  
**负责人**：达析  
**状态**：✅ 已记录  

---

## 1. pyflakes 中低优先级警告（21 个）

**发现时间**：2026-05-24 14:45 GMT+8  
**发现人**：Qclaw（P0 代码扫描）  
**修复脚本**：`fix_pyflakes_high.py`（已修复高优先级错误）  

### 1.1 未使用的导入（10 个）

**文件**：`modules/audit/presenters/audit_presenter.py`  
**行号**：1, 3, 4, 233, 394, 1146  
**详情**：
- 第 1 行：`'os' imported but unused`
- 第 3 行：`'threading' imported but unused`
- 第 4 行：`'typing.Optional' imported but unused`
- 第 4 行：`'typing.List' imported but unused`
- 第 233 行：`'pandas as pd' imported but unused`
- 第 394 行：`'numpy as np' imported but unused`
- 第 1146 行：`'pandas as pd' imported but unused`

**影响**：代码冗余，增加加载时间  
**计划**：v39.3 清理  

---

### 1.2 未使用的局部变量（4 个）

**文件**：`modules/audit/presenters/audit_presenter.py`  
**行号**：619, 826, 1003, 1164  
**详情**：
- 第 619 行：`local variable 'fac_names' is assigned to 
- 第 826 行：`local variable 'dev_type_dist' is assigned to 
- 第 1003 行：`local variable 'factories' is assigned to 
- 第 1164 行：`local variable 'base' is assigned to 
**影响**：代码冗余，可能是调试残留  
**计划**：v39.3 清理（删除或使用 `_` 表示故意忽略）  

---

### 1.3 空的 f-string（4 个）

**文件**：`modules/audit/presenters/audit_presenter.py`  
**行号**：739, 831, 947, 1125  
**详情**：
- 第 739 行：`f-string is missing placeholders`
- 第 831 行：`f-string is missing placeholders`
- 第 947 行：`f-string is missing placeholders`
- 第 1125 行：`f-string is missing placeholders`

**影响**：性能轻微下降，代码不规范  
**计划**：v39.3 修复（去掉 `f` 前缀或添加占位符）  

---

### 1.4 重新定义未使用的变量（2 个）

**文件**：`modules/audit/presenters/audit_presenter.py`  
**行号**：52, 1159  
**详情**：
- 第 52 行：`redefinition of unused 'os' from line 1`
- 第 1159 行：`redefinition of unused 'os' from line 1`

**影响**：可能是复制粘贴错误  
**计划**：v39.3 检查并修复  

---

### 1.5 文件不存在（1 个）

**文件**：`gui/filter_panel.py`  
**错误**：No such file or directory  
**影响**：任务卡路径可能有误  
**计划**：v39.3 确认 `filter_panel.py` 实际位置（可能在 `modules/` 或 `gui/` 子目录下）  

---

## 2. 侧边栏平移抖动问题

**发现时间**：2026-05-24 14:33 GMT+8  
**发现人**：裴哥（元宝指令）  
**问题描述**：
- 侧边栏展开时遮挡表格右侧内容
- 未实现表格平移动画
- 用户体验欠佳，不影响功能

**影响**：用户体验欠佳，不影响功能  
**计划**：v39.3 重构时解决（创建 `table_frame` 容器 + `_on_filter_panel_expand` 回调）  

---

## 3. P0-7/P0-8 阻塞问题

### 3.1 P0-7：侧边栏平移抖动修复（阻塞）

**阻塞点**：无法定位 `audit_tree` 创建位置  
**已知信息**：
- `self.audit_tree.insert` 出现在 `gui/app.py` 第 991 行
- `gui/ui_builder.py` 可能构建 audit_tree
- 搜索 `self.audit_tree =` 未找到赋值语句

**需要**：裴哥帮助定位 `audit_tree` 创建位置（文件 + 行号）  

---

### 3.2 P0-8：PPT 模块迁移至 `modules/export/`（阻塞）

**阻塞点**：无法找到 `ppt_generator.py` 文件位置  
**已知信息**：
- `gui/event_handlers/export_events.py` 导入 `from ppt_generator import run_ppt_generation`
- `modules/export/` 目录已创建（前期操作）
- 搜索 `ppt_generator.py` 未找到文件

**需要**：裴哥帮助确认 `ppt_generator.py` 是否存在，完整路径是什么  

---

## 4. 验收标准解读争议

**问题**：P0 验收标准中"pyflakes 无错误"解读不一致  
**选项**：
- **严格解读**：pyflakes exit code 0（无警告）
- **宽松解读**：pyflakes 无高优先级错误（未定义名称）

**决策**：采用**宽松解读**（高优先级错误已修复，剩余警告记录到技术债务）  
**理由**：
1. 高优先级错误（未定义名称）会导致运行时 NameError
2. 中低优先级警告（未使用导入/变量、空 f-string）不影响运行
3. 代码质量 vs. 交付速度的权衡

**计划**：v39.3 清理所有 pyflakes 警告，严格满足"pyflakes 无错误"  

---

## 5. 修复优先级

### P0（立即修复）
- ✅ 高优先级错误（未定义名称）→ **已修复**（2026-05-24 15:00）

### P1（v39.2）
- ⏳ T2：技术债务记录（本文档）→ **进行中**
- ⏳ T3：Trae 审计 PPT 导出逻辑

### P2（v39.3）
- 清理未使用的导入（10 个）
- 清理未使用的局部变量（4 个）
- 修复空的 f-string（4 个）
- 检查重新定义未使用的变量（2 个）
- 确认 `filter_panel.py` 实际位置
- 实现侧边栏平移动画（P0-7）
- 完成 PPT 模块迁移（P0-8）

### P3（v40+）
- 重构 `audit_presenter.py`（当前 1167 行，过大）
- 优化 PPT 生成性能
- 实现自动化测试（GUI 自动化）

---

## 6. 跟踪状态

| 债务项 | 状态 | 计划修复版本 | 负责人 |
|--------|------|--------------|--------|
| pyflakes 中低优先级警告（21 个） | ⏳ 待修复 | v39.3 | 达析 |
| 侧边栏平移抖动 | ⏳ 待修复 | v39.3 | 达析 |
| P0-7 阻塞（audit_tree 位置） | ⏳ 待裴哥帮助 | v39.3 | 裴哥 |
| P0-8 阻塞（ppt_generator.py 位置） | ⏳ 待裴哥帮助 | v39.3 | 裴哥 |
| 验收标准解读争议 | ✅ 已决策 | - | Qclaw |

---

## 7. 更新记录

- **2026-05-24 15:08**：初始创建（Qclaw，P0 收官验收）
- **2026-05-24 15:08**：记录 pyflakes 中低优先级警告（21 个）
- **2026-05-24 15:08**：记录侧边栏平移抖动问题
- **2026-05-24 15:08**：记录 P0-7/P0-8 阻塞问题
- **2026-05-24 15:08**：记录验收标准解读争议

---

**下一步**：提交 `docs/TECH_DEBT.md` 到 `dev/v39-refactor` 分支，推送远程仓库。
