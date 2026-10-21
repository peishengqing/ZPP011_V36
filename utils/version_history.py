# -*- coding: utf-8 -*-
"""
ZPP011 生产偏差分析器 — 版本历史集中管理

所有版本号、版本日志均由此文件统一管理，其他模块（GUI、打包脚本等）
通过 import 动态读取，避免硬编码分散。

⚠️ 修改版本号时只需更新本文件，无需改动其他代码。
"""

APP_NAME = "云南达利ZPP011生产偏差分析器"
AUTHOR = "裴盛清"

# 版本列表：最新版本在索引 0
VERSION_HISTORY = [
    {
        "version": "v43.223",
        "date": "2026-10-21",
        "features": "ARC-003 第十刀：创建 FileMonitorController 并迁移文件监控方法，主窗口代码精简完毕。",
        "fixes": "**根因**：MainWindow 仍有文件监控、自动加载等逻辑，职责分散。**病根**：文件夹监控、占用检测、自动加载等文件监控相关逻辑散落在主窗口，耦合严重。**修法**：新建 FileMonitorController，迁移 8 个文件监控相关方法。**验收**：py_compile + pyflakes 零新增；主窗口代码从 3,739 行降至 3,284 行，减少 455 行。**反证**：回退迁移 → 主窗口再次变回 God Object，监控逻辑散乱。",
    },
    {
        "version": "v43.222",
        "date": "2026-10-20",
        "features": "MainWindow 重构继续：迁移 UI 状态更新控制器，料对管理全到 AltController。",
        "fixes": "**根因**：MainWindow 仍有大量料对和 UI 状态更新逻辑，职责不清。**病根**：代码散落在主窗口，难以维护和测试。**修法**：创建 UISettingsController 接管所有 UI 状态更新；将 12 个料对管理方法完全迁移到 AltController。**验收**：py_compile 无语法错误；主窗口代码减少约 400 行。**反证**：回退迁移 → 主窗口再次变回 God Object。",
    },
    {
        "version": "v43.221",
        "date": "2026-10-20",
        "features": "跨平台文件打开异常处理；P1 缺陷修复；代码质量提升。",
        "fixes": "**根因**：_open_file() 函数缺少异常处理，文件打开失败时可能静默失败或崩溃。**病根**：原始实现没有 try/except，导致跨平台文件打开时错误无法捕获。**修法**：为 _open_file() 添加 try/except 块，捕获异常并打印错误信息和堆栈跟踪。**验收**：py_compile 无语法错误；文件打开失败时输出错误日志。**反证**：回退异常处理 → 文件打开失败时不输出任何错误信息。",
    },
    {
        "version": "v43.220",
        "date": "2026-10-20",
        "features": "修复基线缺失导致 old_value=NaN 的异常变动提醒；隔离区对话框列头筛选接入。",
        "fixes": "**根因**：data_service.py 基线缺失时仍标记变更，导致 get_audit_changes() 返回旧值为None的记录。**病根**：_restore_read_status 第4步只检查 has_baseline，未验证完整基线，导致基线部分缺失的行也被标记为 changed。**修法**：引入 has_complete_baseline = has_baseline & hist_snap.notna() & hist_note.notna() & hist_yield.notna()，仅对三基线齐全的记录进行变更比对。**验收**：py_compile 无语法错误；测试覆盖；导出Excel中 old_value 不为 NaN，基线缺失记录不再触发变动提醒。**反证**：回退 has_complete_baseline → 大量 old_value=NaN 的记录仍存在；回退后数据正常。",
    },
    {
        "version": "v43.218",
        "date": "2026-10-19",
        "features": "为 MainWindow 操作栏所有按钮创建实例（修复 LayoutComposer 依赖），包括分析按钮、视图开关、收纳菜单、面板开关和自动隔离按钮。",
        "fixes": "**根因**：LayoutComposer._make_action_bar() 中访问 mw.action_btn_analyze 等按钮属性，但 MainWindow 未定义这些属性，导致 AttributeError。**病根**：在 MainWindow 重构阶段（创建 AnalysisControllerV2、DashboardManager、LayoutComposer），遗漏了 UI 元素的创建代码。**修法**：在 LayoutComposer._make_action_bar() 内部直接创建所有操作栏按钮，并赋值给 mw 对象，保持接口一致。创建分析按钮（QPushButton）和工具按钮（QToolButton）、设置样式和提示。**验收**：py_compile+pyflakes 零新增；单元测试通过；应用启动无异常。**反证**：回退创建逻辑 → 应用启动时报 AttributeError。",
    },
    {
        "version": "v43.217",
        "date": "2026-10-19",
        "features": "修复 main_window.py 导入错误，移除不存在的 get_current_version",
        "fixes": "**根因**：main_window.py 中尝试从 utils.version_history 导入 get_current_version()，但该校验函数不存在。**病根**：版本历史管理 refactor 中遗漏了方法移除后对调用处的清理。**修法**：移除导入中的 get_current_version，改为使用 VERSION_HISTORY[0]['version'] 访问当前版本号。**验收**：py_compile+pyflakes 零新增；主窗口标题正确显示；测试通过。**反证**：保留错误导入 → 启动时报 ImportError。",
    },
    {
        "version": "v43.216",
        "date": "2026-10-19",
        "features": "为替代料看板添加级联筛选机制，重构 _build_semi_checkboxes 和 _semi_class_visible_options，确保半成品分类选项随其他筛选条件动态调整，移除结构性死选项。",
        "fixes": "**根因**：替代料看板（alert_dialog.py）完全缺少级联刷新逻辑，半成品分类复选框只在 set_data() 时构建一次，后续不复显式需要动态调整。用户先选择车间/工厂后，半成品分类下拉/复选框会出现死选项（0 行的结构性选项）。**病根**：与半成品看板/偏差率预警看板相比，缺少 exclude-self 双向级联机制，无法实现选项的动态收窄。**修法**：重构 _build_semi_checkboxes 实现级联刷新，借鉴半成品看板 v43.174 模式，在 _apply_filter() 开头和 set_data() 末尾调用 _refresh_cascade_combos()，使用 cascade_options 和 replace_combo_items 确保双向级联和空结果回退。**验收**：py_compile+pyflakes 零新增；级联刷新测试覆盖；重构前后功能一致。**反证**：回退级联逻辑 → 死选项仍然存在，用户操作体验下降。",
    },
    {
        "version": "v43.214",
        "date": "2026-10-19",
        "features": "继续 MainWindow 重构：创建 DashboardManager 统一看板管理，将 MainWindow 含逻辑进一步解耦。",
        "fixes": "**根因**：MainWindow 3967 行 God Object，看板创建和显示逻辑分散在各处，维护困难。**病根**：11+ 个看板都是独立创建、各自有数据筛选和列裁剪逻辑，耦合严重。**修法**：创建 gui_pyside6/dashboard_manager.py，将所有看板打开逻辑统一封装，让 MainWindow 只保留薄壳转发。**验收**：py_compile+pyflakes 零新增；逻辑与旧版 DashboardController 完全一致（逐行搬迁）。**反证**：原位不动 → 重构继续推迟，代码复杂度持续累积。",
    },
    {
        "version": "v43.213",
        "date": "2026-10-19",
        "features": "启动 MainWindow 重构试点：将分析流程解耦到独立控制器 gui_pyside6/controllers/analysis_controller_v2.py，作为 God Object 重构的第一步。",
        "fixes": "**根因**：MainWindow 3967 行 God Object（约 3900+ 行），包含 UI 组装、分析流程、看板管理等诸多职责，维护困难。**病根**：大模块耦合严重，单点故障风险高，测试困难。**修法**：拆分出独立分析控制器，包裹 _start_analysis 和 _on_analysis_finished_ui 逻辑，作为重构试点。后续继续拆分 DashboardManager、LayoutComposer 等模块。**验收**：py_compile+pyflakes 零新增；构建单元测试覆盖关键路径。**反证**：原地不动 → 重构继续推迟，代码复杂度持续累积。",
    },
    {
        "version": "v43.212",
        "date": "2026-10-19",
        "features": "修复自动隔离「脱氧剂负损」规则（#5）类别匹配在真实主表下不命中：category_value 由单值「原辅料」改为「原材料,原辅料」（逗号 OR，代码 _match_single_rule 支持多值包含匹配，覆盖两条数据路径）。",
        "fixes": "**根因**：v43.211 的 NaN 回退修复只治了「非主表子集路径」（导出 xlsx 无「物料分类」列时回退到组件物料类型描述=原辅料→命中）；真实主表有「物料分类」列、_first_col 优先级 [物料分类,物料大类,物料类型,组件物料类型描述] 选中它，而该列由 analyzer.py:412 np.select 生成——组件物料类型 Z004（脱氧剂属原料）→归为「原材料」，不含「原辅料」二字，故 `cat_str.str.contains('原辅料')` 对「原材料」返回 False、规则 #5 整条不命中，脱氧剂仍不进隔离区（用户 11:34 重启重跑仍没隔离的真因）。**病根**：规则按 SAP 描述口径写「原辅料」，分析器却把原料统一重分类成「原材料」，列优先又选了重分类列，二者命名不一致导致包含匹配失败（与 NaN 无关，是二阶坑）。**修法**：仅改配置 config/auto_quarantine_config.json 规则 #5 的 category_value = '原材料,原辅料'（不改代码、不碰冻结区 analyzer.py）；逗号分隔被 re.split(r'[，,]') 拆成 ['原材料','原辅料'] 做 OR 包含匹配——主表走「物料分类=原材料」命中、描述路径（缺物料分类列时）走「原辅料」也命中，两条路径都兜住。其余条件（名称含脱氧剂+负损+单位片+排除替代料）不变，仍精确。**验收**：JSON 合法（python -m json.tool 通过）；py_compile+pyflakes 对改动文件零新增（本版仅改 JSON，version_history.py 仅加注释型条目）；用真实 compute_auto_quarantine_ids 对「物料分类=原材料」的脱氧剂行复算应 1/1 命中（原因=自动规则[第5条:脱氧剂负损]）；pytest 全量零新增失败。**反证**：回退成单值 '原辅料' → 主表「物料分类=原材料」路径 0 命中，印证命名不一致是二阶根因；改回 '原材料,原辅料' 后命中。",
    },
    {
        "version": "v43.211",
        "date": "2026-10-19",
        "features": "修复自动隔离类别回退缺陷：半成品重分类 为空（NaN 形态）时，原料/包材类规则（如「脱氧剂负损」category=原辅料）静默漏隔离。",
        "fixes": "**根因**：core/auto_quarantine.py:_match_single_rule 的类别匹配 `m_cat = m_semi.where(semi_str.ne(''), m_cat_fallback)` 只认空串 ''、不认 NaN；半成品重分类 缺值经 pandas astype(str) 变 'nan' 字符串，被当「有值」做精确匹配 'nan'==vals 失败、且**不回退**到物料分类包含匹配，类别条件整条失败→原料/包材行不进隔离区。**病根**：原料/包材本就不属半成品（用户确认：半成品重分类 前提是属半成品，脱氧剂这类原料该列本就空），但该列在部分数据路径下是 NaN 而非空串，旧回退逻辑容错不足。**修法**：semi_str 构造处改为 `df[semi_class_col].fillna('').astype(str).str.strip()`（astype 之前先 fillna('')，让 NaN 与空串统一为空串）。注意 pandas 2.x 下 `astype(str)` 对 NaN 仍保留为 NaN（非 'nan' 字符串），故 `.replace({'nan':''})` 无效，必须用 fillna 前置。统一后 '' 与 NaN 都走 `semi_str.ne('')` 回退分支→回退到组件物料类型描述包含匹配（含'原辅料'/'包材'即通过）。半成品规则(#3/#4)走 mat_code_prefix 不依赖此列、不受影响；包材规则(#1/#2)反而被顺带修好。仅改 1 行，config 不动。**验收**：py_compile+pyflakes 双关零新增；实证脚本 diag_deoxy_rule.py 对导出 xlsx 的 7 条脱氧剂行（半成品重分类=NaN 形态）跑 compute_auto_quarantine_ids——修复前 0/7 命中、修复后 7/7 命中（原因=自动规则[第5条:脱氧剂负损]）；pytest 全量回归零新增失败。**反证**：保留原代码（NaN 不 fillna）→ 7 条 NaN 行 0 命中，印证 NaN 不回退是漏隔离根因；加回 fillna 后 7/7 命中。",
    },
    {
        "version": "v43.210",
        "date": "2026-10-19",
        "features": "负损/正损/偏差率预警/替代料 4 个看板统一 ensure「半成品重分类」列并定位到「组件物料类型描述」之后（照搬半成品看板 v43.155 手法）：主表经筛选/列过滤丢列后，这 4 个看板表格也能看到「半成品重分类」列，与顶部半成品分类筛选器对齐，避免「筛了却看不到列」。",
        "fixes": "**根因**：v43.155 只修了半成品看板，负损/正损/偏差率/替代料看板只 `if '半成品重分类' in df.columns` 探测、不补列不定位；主表子集 df 常缺该列（v43.155 注释明确会丢），于是表格看不到列、筛选器却仍能筛（走 400/410 兜底），用户不知在筛哪类。**修法**：4 个 dialog 的 set_data 里 `df=df.copy()` 后补 `if '半成品重分类' not in df.columns: ensure_semi_class_column(df)`（try/except 兜底填空串），并在建表模型前把列定位到「组件物料类型描述」之后；均 import ensure_semi_class_column。半成品看板不动（已有）。**验收**：py_compile+pyflakes 双关零新增；pytest 全量零新增失败；人工核对 4 个 set_data 落点不与现有列重排冲突（负损/正损在「隔离区」列移动后、original_df 前；偏差率在「备注」移动后、建模型前；替代料在 original_df 后、建模型前）。**反证**：临时把某看板 ensure 块注释掉→该看板在缺列子集下表格无「半成品重分类」列，印证补列是修复点。",
    },
    {
        "version": "v43.209",
        "date": "2026-10-19",
        "features": "回退「投料为负」整套机制（裴哥确认实际为负概率极小、且该机制带来误隔离与视觉干扰）：撤掉自动隔离第6条规则、主表 _neg_feed_rows 整行红标+悬停提示、分析完成 warning toast 强提醒，以及 core/auto_quarantine.py 的 neg_actual_required 字段与 4.5 匹配逻辑（改为恒放行，其余规则的 false 经白名单自动失效）；同步删除两条相关回归测试。隔离区 7947 条历史失效记录已清（回到加之前状态）。",
        "fixes": "**根因**：v43.207 引入的「投料为负（实际<0）」三重提醒（主表红标+toast+自动隔离）在真实清洗数据中实际列恒 >=0、命中 0 条，却因旧时点数据误写入 7947 条历史隔离记录、且用户用旧版 exe 看到旧文案，造成「明明没负的却进了隔离区」的困惑。**修法**：按裴哥「实际为负概率小、不用那么麻烦」的定论整套回退（选项A 全套撤），仅保留既有未投料/偏差率预警/替代料组色等原有标记；core/auto_quarantine.py 删 DEFAULT_RULE 的 neg_actual_required、_RULE_FIELDS 去登记、build_rule_summary 删「实际<0（投料为负）」预览、_match_single_rule 的 4.5 节改为 `m_neg = pd.Series(True,...)` 恒放行。**验收**：py_compile+pyflakes 双关零新增；pytest 全量零新增失败（已删的两条 neg_feed 测试移除，不再参与）；audit.db 备份后 DELETE 7947 条 reason LIKE '%第6条%' 记录，隔离区回到干净。**反证**：旧逻辑在真实数据命中 0 条已证明机制无实际收益，回退不影响任何有效隔离。",
    },
    {
        "version": "v43.208",
        "date": "2026-10-17",
        "features": "投料为负标红覆盖替代料行：裴哥确认「替代料的实际也不能是负数」，故「替代料+实际<0」行同样要整行标红+隔离。",
        "fixes": "**根因**：v43.207 的 data() BackgroundRole 先查替代料组色再查 neg_feed 红标，导致「替代料+实际<0」的行被组色盖掉、不显示红标（正常料反而红了），与「替代料也不能为负」的诉求矛盾。**修法**：把 neg_feed 红标提到 BackgroundRole 最高优先级（仅 _read/_read_source 两列在前），任何实际<0 的行（无论是否替代料）一律红，连替代料组色也压过；ToolTipRole 的 neg_feed 提示本就在替代料提示之前、不受影响。自动隔离(D)与强提醒(C)自 v43.207 起已是 exclude_alt=false / 全量统计，本就覆盖替代料，无需改。**验收**：py_compile+pyflakes 零新增；新增 tests/unit/test_data_frame_model_neg_feed.py（_neg_feed_rows 含替代料行 + BackgroundRole 红标压过替代料组色，红(255,150,150) 经 offscreen Qt 实测）、test_auto_quarantine_neg_feed.py 补 test_neg_feed_includes_alt_material（替代料实际<0 必被命中）；pytest 全量零新增失败。**反证**：把 BackgroundRole 的 neg_feed 检查移回替代料组色之后 → test_neg_feed_red_priority_over_alt_group_color 精确失败（替代料行变回组色而非红），印证优先级是修复点。",
    },
    {
        "version": "v43.207",
        "date": "2026-10-17",
        "features": "投料为负数（数量-实际<0，疑似录错/冲销方向错）三重提醒：B 主表整行醒目红标(255,150,150)+悬停提示；C 分析完成弹强提醒 warning toast+状态栏；D 自动隔离规则新增「投料为负(实际<0)」条件(neg_actual_required)，分析完自动移入隔离区（复用既有自动隔离通道）。",
        "fixes": "**根因**：此前系统对「投料录成负数」无任何拦截/提醒，只有事后 sheet6_anomaly 弱检测。负数投料本质是录入错误（偏差口径下实际<0 不代表合理负向流动），需即时可视化+强提醒+自动隔离三联动。**修法**：① core/auto_quarantine.py 新增条件字段 neg_actual_required（DEFAULT_RULE 默认 False、_RULE_FIELDS 登记以免被 _normalize_rule 吞掉），_match_single_rule 加 4.5 节（实际<0 且 非空 → 命中）并并入最终掩码，build_rule_summary 加「实际<0（投料为负）」预览；② config/auto_quarantine_config.json 末尾追加「投料为负(实际<0)」规则（neg_actual_required=true、negative_loss_required=false、排除替代料=false 以全量捕获）；③ gui_pyside6/models/data_frame_model.py 新增 _neg_feed_rows 集合（_build_cache 内 数量-实际<0 标记，含空表重置），data() 的 BackgroundRole 在最优先位（仅让位于替代料组色）染红、ToolTipRole 返回核查提示；④ gui_pyside6/main_window.py:_on_analysis_finished_ui 分析完成后扫一遍实际<0 行数，>0 则弹 warning toast + 状态栏提示。自动隔离复用 _auto_move_to_quarantine(manual=False)（main_window.py:1365 已在分析完调用 compute_auto_quarantine_ids），无需新机制。**验收**：py_compile+pyflakes 双关全绿；新增 tests/unit/test_auto_quarantine_neg_feed.py——负实际命中、正/零/空均不命中、_normalize_rule 保留 neg_actual_required（防回退）、反证 neg_actual_required=false 且 negative_loss_required=true 时负实际不命中；pytest 全量回归零新增失败。**反证**：临时把配置规则 neg_actual_required 改 false → 负实际行不再被隔离、C 的 toast 也不再触发，印证链路闭合。",
    },
]
