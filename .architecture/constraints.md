# Architecture constraints

Record constraints that materially change architecture decisions. For each constraint include its source, owner, rationale, review date, and whether it is fixed or negotiable.

## Product and business

- C-PB-01 (fixed): 产品为云南达利食品有限公司内部生产偏差分析工具，服务 1101 食品/1102 饮料两厂 16 车间的材料审核；数据属公司内部生产数据 (internal classification)。来源：维护者声明，2026-10-14。
- C-PB-02 (fixed): 单人维护（peishengqing）+ AI 结对编程（WorkBuddy）；所有架构决策必须经维护者确认后实施。来源：维护者声明，2026-10-14。

## Platform and compatibility

- C-PL-01 (fixed): Windows 10 x64 单机桌面应用，PySide6 GUI；不得引入云端服务依赖。来源：部署形态实证（run_pyside6.py + build_pyside6_exe.py），2026-10-14。
- C-PL-02 (fixed): 冻结区零改动：analysis/analyzer.py 与 analysis/excel_builder/sheet2_alt.py 为核心计算模块，任何改动需维护者单独授权。来源：维护者红线，2026-10-14。
- C-PL-03 (fixed): 不新增第三方运行时依赖（requirements.txt 清单外不收）。来源：维护者红线，2026-10-14。

## Security, privacy, and compliance

- C-SE-01 (fixed): 生产凭证严禁入 git：tools/sap_pull_secret.json 已在 .gitignore；SAP 密码交互式输入（tools/sap_pull.py get_password）。来源：.gitignore + 源码实证，2026-10-14。
- C-SE-02 (fixed): API key 不硬编码：core/ai_client.py 按 models.json → 'ai.api_key' 配置项 → 环境变量 AGNES_API_KEY 三级加载。来源：源码实证，2026-10-14。
- C-SE-03 (negotiable): 外发 Agnes AI 的数据范围需维持当前字段集（偏差上下文），不得升级为全量生产数据外发。来源：维护者意图，待维护者确认边界。

## Operations, cost, and team

- C-OP-01 (fixed): 无 on-call、无 SLA；崩溃恢复依赖 _recovery_needed.flag + .bak 机制。来源：部署实证，2026-10-14。
- C-OP-02 (negotiable): 交付物为可双击运行的 exe（PyInstaller），发版走 push_log.sh 记录北京时间。来源：维护者工作流，2026-10-14。

## Explicit non-goals

- 不做云端功能、不做多用户/多租户、不做复杂预测模型。
- 不做大爆炸重构：MainWindow 拆分等结构性改动须以小步演进 + 测试保护推进。
- 不删除维护者的调试/一次性脚本（_dbg_*.py、probe*.py、work/gen_final*.py）：仅可提议归档至备份目录，删除须维护者明确授权。

## Change risk tiers (改动风险分级制, 2026-10-14 裴哥确认)

改动前先对号入座，决定走哪条门禁。核心原则：冻结区防的是「算错数哑崩」而非「软件崩」，故按「是否触及计算口径/数据流」而非「是否触及核心文件」分级。

- 🔴 红区 — 计算口径/冻结区（`analysis/analyzer.py` 偏差计算、`excel_builder/sheet2_alt.py` 净抵消、`net_offset.py` 替代料抵消）：**零改动**。任何口径变更须维护者单独授权 + 独立重算对账网验证。来源：维护者红线（C-PL-02）。
- 🟡 黄区 — 动计算逻辑/数据流（`analysis/excel_builder/*.py`、`core/` 领域服务、看板的金额/率取值）：改动前须跑 **独立重算对账网**（`tools/recompute_check.py`）确认数量/率/金额三维忠于源；计算类差异只报不拦 + 人工验证戳（机器不能证明存量对错）。
- 🟢 绿区 — 收拾垃圾 / 拼接类 / 纯 UI / 文档（data_id 构造收敛、GUI 组件、菜单、`.architecture/` 文档、死代码清理）：直接做，`py_compile`+`pyflakes` 全绿即可，无需对账网把关（拼接类只改「键怎么拼」，不改「数怎么算」）。

门禁区分（2026-10-14 定稿）：
- **拼接类（如 data_id 的 4段/3段拼接）= 硬门禁**：拼错键 → 隔离/已读匹配永久失败，必须 `build_data_id` 单一正版 + 单测锚定（真实 DB 样本），杜绝再散落成 23 处复制。
- **计算类（偏差金额/率）= 只报不拦 + 人工验证戳**：机器只能证伪「新改动算错没」，无法证明存量口径本身对，故计算类对账结果供人工逐条确认，不作自动阻断。
