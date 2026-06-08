# 预警规则配置实施总结

## 目标
实现预警规则的运行时动态配置管理，将硬编码的阈值和替代料过滤条件改为用户可配置。

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `config/config.yaml` | 修改 | 新增 `alert.only_alt_materials: true` |
| `core/config_loader.py` | 修改 | 新增 `reload()` 方法；默认配置加 `only_alt_materials: True` |
| `core/alert_monitor.py` | 修改 | `__init__` 增加 `only_alt` 参数；新增 `update_config(threshold, only_alt)` 方法；`_check_alerts` 支持仅替代料过滤 |
| `gui_pyside6/dialogs/alert_rule_config_dialog.py` | **新建** | 预警规则配置对话框（偏差率阈值 + 仅替代料复选框 + 保存/取消） |
| `gui_pyside6/main_window.py` | 修改 | 工具菜单新增「预警规则配置」入口；实现 `_configure_alert_rules` 方法（写配置文件→reload→更新AlertMonitor→更新代理模型）；AlertMonitor 初始化传入 `only_alt` |
| `gui_pyside6/models/data_frame_model.py` | 修改 | AuditProxyModel 新增 `_alert_threshold` 属性和 `set_alert_threshold()` 方法；`_check_rate_range` 中绝对值过滤使用配置阈值 |
| `core/advanced_ppt_generator_v3.py` | 修改 | `load_data` 中预警记录生成使用 `alert.threshold_percent` 配置值，并支持 `only_alt_materials` 过滤 |

## 实现要点
- **配置流程闭环**：对话框→写 YAML→config.reload()→更新内存对象（AlertMonitor + ProxyModel）
- **AlertMonitor.update_config()**：只改参数，不重置已读记录，避免重复弹窗
- **three-way 联动**：对话框保存后同时更新文件、运行时对象、视图响应
- **集成测试全部通过**：6个模块的语法检查 + 功能断言验证

## 用户操作路径
1. 菜单「工具」→「预警规则配置」
2. 调整偏差率阈值、选择是否仅替代料
3. 点击确定 → 立即生效，无重启需
