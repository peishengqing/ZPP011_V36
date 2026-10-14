# Critical flows

Describe flows whose failure would materially harm users, data, money, privacy, or operations.

## Flow cf1-import-analyze-export: SAP 导入 → 分析 → Excel 导出

- Trigger: 用户选择 SAP 导出文件并启动分析/导出完整报告。
- Actor: 材料审核员（单座位）。
- Preconditions: SAP 导出文件可读；output 目录可写。
- Control/data path: core/import_handlers.py（导入+备份）→ gui_pyside6/services/data_service.py（data_id 构造，四段格式 工厂|订单日期|流程订单|物料编码）→ analysis/analyzer.py do_analysis_v2（冻结区）→ analysis/excel_builder/sheet1-10 + post_process.py + net_offset.py → gui_pyside6/workers/report_workers.py（_FullReportWorker QThread 后台执行）→ save_guard.precheck_save_path。
- Authoritative owner: analysis/analyzer.py（计算口径）；gui_pyside6/services/data_service.py（data_id 业务键）。
- Side effects: 写 output 目录 Excel；可选写审计库。
- Failure and recovery behavior: 目标文件被占用时 save_guard 拦截并提示「存为副本」；后台线程异常经 log() 提示。
- Idempotency boundary: 重复导出生成新文件，无覆盖破坏（save_guard 副本机制）。
- Security/privacy boundary: 文件均在本地；无外发。
- Observability evidence: main_window.log() + core/logger.py。
- Acceptance tests: tests/test_analyzer_e2e.py、tests/test_data_service.py、tests/test_net_offset.py（注意：不在 CI 的 tests/unit/ 覆盖内）。

## Flow cf2-audit-persist: 审计数据持久化

- Trigger: 分析完成/偏差变更/已读状态变更/隔离规则触发。
- Actor: 系统（自动）。
- Preconditions: ~/.zpp011_audit/ 目录可写。
- Control/data path: core/read_status.py（DB_PATH=~/.zpp011_audit/audit.db，主线程单例连接）→ deviation_history / read_status 表；core/quarantine_manager.py → quarantine_records 表；core/history_freq.py、core/audit_logger.py、gui_pyside6/dialogs/{data_stability,material_profile,quarantine_review}_dialog.py 亦直连同一库。
- Authoritative owner: 争议点——见审计候选 ZPP011-ARC-001：audit.db / audit_log.db / history.db 三个路径定义并存，磁盘仅 audit.db 存在。
- Side effects: SQLite 写入（WAL）。
- Failure and recovery behavior: 未显式验证；_recovery_needed.flag（2026-09-06 残留）表明曾有崩溃恢复设计。
- Idempotency boundary: 未验证（data_id 去重依赖 drop_duplicates，见 quarantine_manager.py:210）。
- Security/privacy boundary: 本地库；.gitignore 挡 *.db。
- Observability evidence: audit_logger 队列写库。
- Acceptance tests: tests/unit/test_audit_logger.py、tests/unit/test_history_db.py、tests/test_history_db.py（注意 test_history_db 指向 history.db，与线上 audit.db 不一致）。

## Flow cf3-dashboard-render: 看板渲染

- Trigger: 用户打开负损/正损/半成品/综合看板。
- Actor: 材料审核员。
- Preconditions: 已分析数据在内存 df。
- Control/data path: gui_pyside6/dialogs/{neg_loss,pos_loss,semi}_dashboard_dialog.py 与 dashboard_dialog.py → analysis/dashboard_html.py compute_metrics → WebEngine 渲染（延迟 import 防启动 hang）；matplotlib 仅在后台线程 Agg 绘制。
- Authoritative owner: analysis/dashboard_html.py（指标口径）。
- Side effects: 无持久化。
- Failure and recovery behavior: WebEngine 缺失时 try/except 降级（dashboard_dialog.py 注释记录）。
- Idempotency boundary: 纯读。
- Security/privacy boundary: 本地渲染；HTML 内嵌数据。
- Observability evidence: 无专门遥测。
- Acceptance tests: tests/unit/test_dashboard_upgrades.py。

## Flow cf4-ai-audit: Agnes AI 偏差审核

- Trigger: 用户对选中偏差发起 AI 审核。
- Actor: 材料审核员 + Agnes AI（apihub.agnes-ai.cn）。
- Preconditions: API key 经三级加载可用（models.json → 配置 → 环境变量）。
- Control/data path: gui_pyside6/models/workers.py AIAuditWorker（QThread）→ core/ai_client.py（requests.post，超时 5s/20s/45s 分档）→ 结果持久化至 audit.db。
- Authoritative owner: core/ai_client.py。
- Side effects: 外发偏差上下文至外部 API；写审核结果。
- Failure and recovery behavior: 超时即失败；未观察到重试/退避；fallback 仅配置级。
- Idempotency boundary: 审核结果按 data_id 更新。
- Security/privacy boundary: 外发面——见 C-SE-03；密钥不硬编码（已实证）。
- Observability evidence: mock_fallbacks 计数；日志经 core/logger。
- Acceptance tests: 未发现 AI 审核的离线回归测试（mock 级亦未确认）。

## Flow cf5-backup-recovery: 备份与崩溃恢复

- Trigger: 分析前自动备份 / 导出审核备份 ZIP / 崩溃后恢复检查。
- Actor: 系统（自动）。
- Preconditions: ~/.zpp011_audit/ 可写、磁盘空间充足（MIN_FREE_MB）。
- Control/data path: core/backup_manager.py（BackupManager，shutil.copy2）与 storage/storage.py（export_audit_backup）；恢复检查写 _recovery_needed.flag。
- Authoritative owner: 争议点——见 ZPP011-ARC-001：backup_manager 与 storage 指向 audit_log.db（磁盘不存在），而活库为 audit.db。
- Side effects: 复制数据库与输入 Excel。
- Failure and recovery behavior: 磁盘不足抛异常；目标不存在时 export 抛 FileNotFoundError。
- Idempotency boundary: 备份按时间戳命名。
- Security/privacy boundary: 本地文件。
- Observability evidence: 磁盘实证存在 audit.db.bak_20260919_112219 与 audit.db.bak_20261012_0839（命名格式与当前代码的 audit_log_{ts}.db 不一致，来源待查）。
- Acceptance tests: tests/unit/test_backup_manager.py。
