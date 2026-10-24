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
        "version": "v43.258",
        "date": "2026-10-24",
        "fixes": "① **修复 AI 偏差审核静默跑 Mock 的真缺陷**：`core/ai_client.py::_resolve_agnes_config()` 一直在 models.json 里找 `agnes-2.5-flash`，而 models.json 里的条目早已换成 `agnes-3.0-flash` → 找不到 → api_key 解析为空 → `_get_api_key()` 返回空串 → 真实调用必然 401 → 被 except 捕获后**静默降级 Mock**。也就是说「接入 Agnes AI 智能审核」这个功能实际上一直在跑本地规则，没有任何提示。改为优先级 `agnes-3.0-flash > 任意 agnes-* > 模块常量`，以后再换型号也不会再次静默丢 key；模块常量 AGNES_MODEL 同步更新为 agnes-3.0-flash。实测：key 正常解析（51 字符），一次真实审核调用 2.1 秒返回，`get_stats()` 显示 `real_calls:1 / mock_fallbacks:0`。② 新增 `AIClient.generate_text()`：通用文本生成入口（不强制 JSON、max_tokens/timeout 按长输出给、**没有 key 时直接抛异常而不走 Mock**——Mock 对「生成设计」毫无意义，静默降级只会让用户以为拿到的是 AI 设计）；服务端 5xx 瞬时错误（实测 agnes 偶发 520）退避 15 秒重试一次，不再让一次端到端白丢 4 分钟。③ **修复数字护栏误报「U+2212」**：AI 在口径说明里写「负号用 U+2212 表示」，数字正则会从 `U+2212` 里切出 `2212`（前一个字符是 `+` 不是字母，`(?<![A-Za-z])` 拦不住）→ 误判越界。与完整日期同理，把 `U+XXXX` 码位说明整段剥掉再抽数字。同时重试提示带上违规数字的上下文片段（光给数字，AI 在 3000 行 HTML 里找不到在哪）。",
        "features": "**归藏报告支持「AI 每期重新设计」**（`core/guizang_ai.py` 新模块，GUI 对话框加「AI 重新设计」按钮）：由 Agnes AI 现场设计版式并写出完整单文件 HTML，取代固定 template.html 外壳；设计方向每期从 8 套视觉方向池里随机挑（瑞士国际主义/暗色数据大屏/报纸风/包豪斯/日式简约/终端极客/年报图表/杂志专题），数字仍全部来自 `build_report_data()` 的数据字典。**配套硬门「数字护栏」**：白名单 = 数据字典 JSON 里出现过的每个数字 + 页码年份常量；校验只扫 HTML 可见文本（去 script/style、连标签属性一起剥掉，CSS 里的 1.2fr/11.6vw 不会误判）；HTML 里任何字典里不存在的数字都记为违规并附上下文 —— **AI 抄错数（−593.3→−529.3）、自己算数（字典里没有的 33.1%）、符号写反（−593.3→+593.3）三类都能当场抓住**（千分位写法等价、.0 尾零归一化后放行）。有违规即不通过：可把越界数字回喂 AI 自动改（最多 2 次尝试），也可回退到原 Python 渲染版，绝不让错数字进报告。prompt 内硬性约束零外链（公司网络 DNS 劫持，Google Fonts/unpkg/jsdelivr 全打不开）、金额万元、负号用 −（U+2212）、正=多耗/负=节约、必须写清明细逐行加总口径。",
    },
    {
        "version": "v43.257",
        "date": "2026-10-24",
        "fixes": "**收口 GUI-001 / GUI-001b「os.startfile 跨平台」**：审计提出 os.startfile 只有 Windows 能用。实际代码里三处早就写了平台分发（d676c1b 起：Windows=os.startfile / macOS=open / Linux=xdg-open），但留下四个真问题：① 同一段分发在 **5 处重复**（export_controller.open_file、ppt_controller._open_file、main_window._open_file、main_window 打开源码备份目录内联一份、main_window 变动提醒导出内联一份）；② 只有 main_window 那份有 try/except，另四处打开失败会**把异常直接抛给调用方**——于是「导出成功了但系统打不开」会演变成一个写着「导出失败」的误导性弹窗（GUI-001b 的实质）；③ macOS/Linux 用 subprocess.run 不带 check，打不开时静默无感；④ 没有 xdg-open 的精简 Linux 环境没有任何回退。修法：新建**唯一实现** `gui_pyside6/utils/file_launcher.py::open_path(path, log_cb=None) -> bool` —— 平台分发保持与原 Windows 路径完全一致（os.startfile 仍是首选，零行为变化），补上：异常永不外抛（失败只打 traceback + 记日志 + 返回 False，由调用方决定提示文案）、日志回调三层兜底（(msg,level) → (msg) → 静默，防 TypeError 顶掉原始异常）、无 xdg-open 时回退 Qt QDesktopServices；5 处全部收敛为一行委托，main_window 里随之清掉不再使用的 sys/subprocess import。",
        "features": "「用系统默认程序打开文件/文件夹」从此只有一个入口：任何地方要打开文件都调 file_launcher.open_path()，不要再各自写平台判断；打开失败不再被误报成「导出失败」。",
    },
    {
        "version": "v43.256",
        "date": "2026-10-24",
        "fixes": "**修复归藏报告读取「趋势分析（自然日分组）」直接崩溃（v43.243 版式变更引发的回归，两个风格入口全中）**：sheet10_trend.py 在 v43.243 把该 sheet 版式改为「row1=期间说明行（跨列合并）、row2=表头、row3=空行、row4+=数据」，旧版式是「row1=表头、row2=说明行」。而 core/guizang_report.py:338 一直用 pandas 默认 header=0 读这张表，于是把 row1 的说明行当成了表头 → `trend[\"趋势\"]` 抛 KeyError → build_report_data 整个失败。**影响面：v43.243（10-23 13:59）之后生成的任何分析结果，点「归藏-Magazine / 归藏-Swiss」两个菜单入口都会弹「生成失败」**（10-21 那份预览之所以正常，是因为它用的是 v43.243 之前的旧分析结果文件）。该回归此前未被发现，是因为 v43.243 之后没有人从新分析结果走过一遍归藏流程。修法：新增 `_read_trend_sheet()` —— 先以 header=None 无表头读入，在前 10 行内定位含「趋势」单元格的那一行作表头（新旧两种版式均能正确识别），再丢掉全空行（新版式的 row3）；表头行按原文去空格后作为列名。不改变任何趋势数值与五分类统计逻辑。",
        "features": "归藏报告对 v43.243+ 新版式分析结果的兼容性恢复：两种表头版式自动识别，后续 sheet10 再调整行序也不会再打断归藏链路。",
    },
    {
        "version": "v43.255",
        "date": "2026-10-24",
        "fixes": "修复 CORE-10「审计日志 N+1 连接」（core/audit_logger.py，零业务影响）：`AuditLogger._worker()` 原在循环体内 `with sqlite3.connect(...)`，**每写一条日志就新建一个连接**（开文件 + 读 WAL + 关文件），实测写 50 条 = 50 次 connect；日志是高频路径（每次改备注/改状态都写一条），该开销纯属浪费。连带发现第二个隐患：**`with sqlite3.connect(...)` 并不关闭连接**（with 块只管事务提交/回滚，连接对象要等 GC 才真正 close），原实现在高频写日志时持续泄漏连接对象。修法：① `_worker()` 改为**整个 worker 生命周期只开一个连接**、逐条复用，退出时在 `finally` 里显式 close；② 单条写失败时**丢弃损坏连接并重建**（自愈），不中断 worker，降级 fallback 文件的行为不变；③ `_init_db`/`_cleanup_old_logs`/`export_csv_async` 统一走新的 `_connect()` + 显式 `try/finally: close()`，并统一设 `PRAGMA busy_timeout`（写线程与导出线程并发时不立刻报「库被锁」）；④ `export_csv_async` **补上异常回调** —— 原实现在导出失败时静默 return、**永远不回调**，调用方会一直等结果（第二个真缺陷）。实测：写 100 条日志 connect 仅 1 次（修前 100 次）、再写 300 条 0 次、5 线程并发 200 条零丢失、shutdown 后全程仅 4 次 connect（无句柄泄漏）、数据逐字段正确；tests/unit/test_audit_logger.py 6 passed。另清掉该文件既有的未使用 import（time）告警。",
        "features": "审计日志写入的建连开销由 O(条数) 降为 O(1) 次（实测 50 条日志 50 次 connect → 1 次），高频改备注/改状态场景不再反复开关 SQLite 文件；日志导出失败会正确回调错误，不再让调用方无限等待。",
    },
    {
        "version": "v43.254",
        "date": "2026-10-24",
        "fixes": "① **修正「完整偏差明细」金额口径（真缺陷，零红线）**：sheet5_full 原用「实际单价反算」= 金额-实际(含税) ÷ 数量-实际，对**未投料行**（数量-实际=0）除零 → fillna(0) → 金额被整列清零。于是「整单完全没投料」的订单在明细里看不到任何金额损失（实测 35 单 / -332.40 万，占全期总偏差 56.1% 全被抹掉），这也是「完整偏差明细金额合计 8.68万 vs 汇总统计 -592.91万」差 601.59 万的根源。现改为**行金额直接相减**（金额-实际(含税) − 金额-定额(含税)），与 analyzer.py:512 的 df['偏差金额(含税)'] 同口径：明细金额合计 8.68万 → **-592.91万，与汇总统计完全闭合**；**汇总统计与驾驶舱头条数字零变化**。② **「完全未投料订单」独立表改为合并**（按需求）：撤销该独立 sheet，信息并入两处 —— 「完整偏差明细」新增**「未投料订单」列**（是/否，82 行命中 / -332.40 万，主表可直接筛），「订单级汇总」带**「投料状态」**列（完全未投料/部分未投料/正常）。③ 新增 5 张偏差分析扩展表（见 features）。④ 「系统问题与真实超耗」的占比分母由**净额**改为**行级绝对值之和**：净额是多耗与少耗抵消后的残差（本期仅几百万），单类占比会算出 392% / -394% 这种没法读的数；改后四类占比恒在 0~100% 且**加和精确 = 1**（按行级绝对值分摊，类内正负相抵不再漏算）。",
        "features": "导出报告新增 5 张偏差分析扩展表（post_process 表现层生成，零红线、不改任何业务数值，均自动获得数字格式/冻结/自动筛选并被「📋 分析说明」事实卡收录）：**①订单级汇总**（1398 单，补上报表缺失的「一单怎么看」视角，含投料状态/缺料数量/无备注条数）、**②车间维度**（14 个「工厂·车间」组合，跨厂同名的「综合组」已标出，车间类型自动分车间/产线/班组）、**③备注归类映射**（164 种原始写法 → 标准原因对照 + 条数占比，用于统一填报口径、从源头降空备注率）、**④系统问题与真实超耗**（把「系统无定额 1115 行 / 完全未投料 158 行」这两类**系统问题**与「真实超耗 65 行」分开，明确该谁负责）、**⑤物料画像**（1081 个组件物料的涉及订单数/偏差金额/最大偏差率/备注覆盖率/含替代料，定位最烧钱与最没人写备注的料）。另：「完整偏差明细」新增「未投料订单」标记列。",
    },
    {
        "version": "v43.253",
        "date": "2026-10-24",
        "fixes": "新增「完全未投料订单」表（导出工作簿第 13 张，post_process 表现层实现，**零红线**、不改任何业务数值）：列出「所有组件实际用量均为 0」的流程订单，即整单没投任何料。实测（2026-10-01~10-23，9268 行）：**35 单** / 82 行明细 / 缺料数量合计 **-5,207,591**（定额 5,207,591 全部未投）。这批单此前在报表里**完全隐形**，原因链已查清：① 未投料 → 偏差率恒为 -100% → 被「无备注预警」的「≠100%」规则排除；② 这 35 单的**原始备注原因是空的**（本该要求补备注）；③ 「完整偏差明细」的金额用「实际单价反算法」（sheet5_full.py：金额-实际(含税) ÷ 数量-实际），未投料行数量-实际=0 → 单价反算失败 → 金额被整列清零 → 连金额都看不到。这也解释了「完整偏差明细金额合计 8.68万 vs 汇总统计 -592.91万」差 601.59 万的根源。判定口径：某订单在「完整偏差明细」里所有行实际用量都是 0；误判/漏判实测均为 0（这 35 单既不含「实际>0 且材料偏差=0」的正常行，也不含被剔除的替代料行）。⚠️ 本表**不含偏差金额列**：工作簿内取不到订单粒度真实金额（见上面第③点），故只给「偏差数量合计/定额数量合计」等数量口径，并在此注明金额的取数限制与补法；本表也不含产量列（产量只在 SAP 源表），「是否报产」需回源表核对。",
        "features": "导出报告新增「完全未投料订单」表：可定位整单零投料的流程订单（含订单号/日期/工厂·车间/订单类型/产品物料/组件行数/定额与缺料数量/是否有备注），用于追查虚报产量。配套在桌面输出《完全未投料订单清单_20261023.csv》（含产量与偏差金额，来自 SAP 源表口径）。",
    },
    {
        "version": "v43.252",
        "date": "2026-10-24",
        "fixes": "补齐导出工作簿里最后两处数字格式缺失（纯表现层，不改任何数值）。① **「偏差原因分析」的多耗/少耗/占车间偏差比% 三列全是 General（显示裸值）**：多耗/少耗是数量口径（正/负偏差数量合计），按数量格式（整数给 #,##0、带小数给 #,##0.###，沿用 _count_fmt 的逐格判定，避免出现「294.」那种小数点尾巴）；「占车间偏差比%」是**百分点数值**（实测 0~97.84，14.57 表示 14.57%），新增「百分点数值列」这一独立类别，格式 `0.00\"%\"`（字面百分号）。⚠️ 这里有个必须避开的 100 倍坑：百分点列若套 0.00% 会显示成 1457.00%；而比率小数列若套 0.00\"%\" 会把 0.143 显示成 0.14%。**两者绝不能用「值是否 >1」来区分** —— 实测比率小数的值域是 (−∞,+∞)（真实超耗 240% 就是 2.4060、673% 就是 6.736），按值域判会把 240.60% 误判成百分点而显示成 2.41%。故判据只用**列名语义**：以 '%' 结尾 → 百分点数值列（当前工作簿仅「占车间偏差比%」一列）；并加安全阀（整列值都 ≤1 时说明它其实是比率小数形态，退回 0.00%）。该类别必须**先于**数量/比率判定，否则该列因列名不含「数量/率/占比」会被整列漏掉。② **「替代料明细」的偏差A/偏差B 两列是 General**：二者是 A/B 两料各自的偏差数量，按数量格式处理。③ 事实卡口径列的数字格式判据（_fact_numfmt）与数据表统一，避免同一列在「事实卡」与「数据表」显示成不同值。",
        "features": "导出工作簿的数字格式全面补齐：偏差原因分析（多耗/少耗/占车间偏差比%）、替代料明细（偏差A/偏差B）不再显示裸值；百分点数值列与比率小数列分开套格式，杜绝 100 倍显示误差。",
    },
    {
        "version": "v43.251",
        "date": "2026-10-24",
        "fixes": "修复「列头筛选」的搜索框**打不进汉字**（中文输入法唤不起来）。根因：列头筛选浮层用 `QWidget(..., Qt.Popup)` 构造，而 **Qt.Popup 默认 `WA_InputMethodEnabled=False`**，浮层自身不参与输入法；显示时焦点按 Qt.Popup 规则落在浮层（QWidget 默认 NoFocus 策略）而非里面的 QLineEdit → 子控件永远拿不到 IME 焦点 → 中文输入法候选窗弹不出来。offscreen 实测五方案对比坐实：现状 focusWidget=None；只加 `WA_InputMethodEnabled` 仍是 None（不够）；只 `edit.setFocus()` 有效；**加 IME 属性后 popup 在 show() 时会自动把焦点交给第一个可聚焦子控件**，再补一次 `QTimer.singleShot(0, search.setFocus)` 兜底最稳。同时实测 `QInputMethodEvent` 提交「透明胶带」能正常进 QLineEdit、匹配逻辑 `t in key.lower()` 对中文完全正常 → 问题纯在焦点/输入法激活，与文本处理无关。改动覆盖**全部 4 个列头筛选浮层**（`controllers/column_controller.py` 主表 2 处 + `utils/column_filter.py` 各看板 2 处）：4 处统一加 `WA_InputMethodEnabled`，其中**带搜索框的 2 处**（主表 + 各看板共用控制器）再加显式焦点。",
        "features": "列头筛选搜索框支持中文输入法直接打字筛选（主表 + 隔离区/预警/负损/正损/半成品等各看板同步生效）。",
    },
    {
        "version": "v43.250",
        "date": "2026-10-24",
        "fixes": "GUI 侧「偏差率预警」口径统一排除 |偏差率| 恰为 100% 的 SAP 除零钳位假值（定额=0 恒 +100.0%、实际=0 恒 -100.0%），与工作簿「无备注预警」sheet（!=100%）及业务规则「≥10% 且 ≠100% 需要备注原因」对齐。改动分两类：**① 三处同源实现**（`data_frame_model.py` 的 `classify_row_color_keys` 标量判定、`DataFrameModel.setDataFrame` 的 `_alert_rows` 向量化判定、`AuditProxyModel._build_plan` 的颜色筛选 plan）——后两处是标量版的**向量孪生**，源码注释明写「复现 classify_row_color_keys 的向量化判定」，只改标量版会让主表行着色/颜色筛选与看板判定分裂，故一并同步；**② 四处绕过 classify_row_color_keys 另算阈值的旁路**（`dashboard_manager.py` 与 `controllers/dashboard_controller.py` 的偏差率预警看板预筛、`main_window.py` 的「偏差率预警未读」统计、`widgets/stats_cards.py` 的统计卡条数）——这四处若不改，用户在界面看到的条数与看板内容仍会把 100% 钳位行算进去，口径裂缝不闭合。排除式统一写作 `abs(rv-100.0) >= 1e-6`（浮点容差）：只显式排除 +100.0%，-100.0% 由既有的 `not no_input`（实际≈0 且 定额>0）排除，两者合起来等价于「排除 |偏差率|=100%」。同步更新 `tests/unit/test_filter_plan_consistency.py` 的镜像参考实现 `ref_accepts`（该测试的作用就是逐行比对 plan 与镜像，镜像不同步必然分叉）；`tests/unit/test_filter_engine.py` 无需改动（其用例不依赖 100% 判为 alert，且走的是 `filter_engine.py` 独立的 stat 判定分支）。",
        "features": "主表橙色高亮、颜色筛选、偏差率预警看板、统计卡条数、变动提醒未读数、工作簿「无备注预警」六处口径首次完全一致：SAP 除零钳位出的 ±100.0% 不再被当成真实超耗预警。",
    },
    {
        "version": "v43.249",
        "date": "2026-10-24",
        "fixes": "收口「|偏差率|≥10% 且 ≠100% 需要备注原因」这条业务规则的 4 处落地不一致（红线零改动，analyzer.py 未碰）：① **「预警等级」列算了却从未落到 Excel** —— sheet3_no_note.build_sheet3 早已把等级算进 DataFrame，但 analyzer 写表时那张写死的列清单里没有它，v43.243 的严重度分级功能一直没上线；现改在 post_process（表现层）里补列，且**不用表内「偏差率」列判定**（它只保留 1 位小数，49.96→'50.0%' 会把 50 这条线判错一档），改用表内数量列重算 |偏差率|=|偏差数量|/定额×100（原始 float 无精度损失）；分档规则抽成 sheet3_no_note.severity_level 单一来源。② **「🔴 完全未投料」是永不出现的死标签** —— 其判定条件（定额>0 且 实际=0）必然使偏差率恒为 -100%，被 !=100 规则挡在表外，实测 158 行满足条件但实际进表 0 行，故删除该档（分档只剩 🟠 严重偏差 / 🟡 超阈值）。③ **10% 边界双定义** —— sheet3 用 >=、sheet4 用闭区间，恰好 10.0% 的行会同时进两张表（且归属取决于浮点表示，-9.999999999999998 与 10.000000000000002 会落到不同表）；现 sheet4 改开区间，两边精确互补、不重不漏，且「≥10% 归无备注预警」与业务规则一致。④ **分析说明文案与实现不符** —— 「无备注预警」旧文案写「超过 ±10%」（实为 ≥ 含边界）、「按偏差金额降序」（实为预警等级→金额绝对值降序），「中间地带明细」写「在 ±10% 区间内」（闭区间，与上一条边界重叠）；现按实际实现改写并**回写**到说明区原行，使说明区与事实卡口径列两处一致（阈值从「动态阈值数值」行读取，不写死）。⑤ **autofilter 范围系统性短列** —— builder 写死筛选范围后 post_process 又追加列（完整偏差明细→「异常标记」、无备注预警/中间地带明细→「重复行」、v43.249 再→「预警等级」），追加列落在筛选范围外、点漏斗选不到；现于流水线末尾把末列补到 max_column（「📋 分析说明」除外，它的筛选器是给 2 列说明块用的）。",
        "features": "「无备注预警」表新增「预警等级」列（🟠 严重偏差 = |偏差率|≥50%；🟡 超阈值 = 其余），按预警等级→偏差金额绝对值双键排序，首列即可看出轻重缓急。",
    },
    {
        "version": "v43.248",
        "date": "2026-10-23",
        "fixes": "修复「📊 驾驶舱」KPI 数字块从未生成的真 bug（pyflakes F821×3）：post_process.py 用了 Alignment(...) 却**从未 import**，KPI 写入在第一行就抛 NameError 并被外层 try/except 静默吞掉 —— 成品驾驶舱只剩一个孤零零的「总偏差记录」标签，无任何数字/单位，另 3 个 KPI 全无。同源三处附带缺陷一并修：① KPI 块（row4-6）与图1 锚点 B4 重叠（KPI 会被图表盖住）→ 图锚点整体下移 4 行（B8/B28/B54）；② KPI 列宽用 chr(ord('A')+col) 算出 C/F/I/L，**整体偏移一列**、等于没设到 KPI 上 → 改 get_column_letter 按真实列号取；③ KPI 原摆「正偏差金额/负偏差金额」两格，但二者相加 ≠ 总偏差金额（差额=价格差异行，属设计口径），并排摆出会被业务方直接相加、误判为数据错误 → 改为只摆**闭合口径**「总偏差金额(含税)」+ 条数加权备注覆盖率，并在 KPI 下补一行口径注（正负分解见图2）。注：该 F821 长期未被发现，是因为此前只对 main_window.py 跑过 pyflakes，未覆盖 post_process.py。",
        "features": "新增「各表事实卡」区块：导出后处理在「📋 分析说明」页追加各数据表的 数据行数/列数/关键度量(合计·最大·最小)/统计备注。口径文案直接复用「各Sheet说明」原文（两处不打架）；数字全部取自各表**已渲染单元格**，可与表内数字逐格对账；导出时写成 '-' 的占位行不计入统计并逐表标注跳过行数；幂等（重跑先删旧区块）；不新增 sheet，下游按 sheet 名取数的报表（归藏报告/PPT）零影响。",
    },
    {
        "version": "v43.247",
        "date": "2026-10-23",
        "fixes": "半成品分类「添加」按钮点击报 AttributeError：QDialog.__init__(SemiCategoryController)。根因：SemiCategoryController._add_semi_category（semi_category_controller.py:217）写 dlg = QDialog(self)，self 是控制器实例（非 QWidget），作父窗口传入 QDialog 构造即崩。column_controller:83 / dashboard_controller:345 / interaction_controller:267 均用 QDialog(self.mw)（self.mw 即 MainWindow，QWidget）。修法：该行改为 dlg = QDialog(self.mw)，与其他控制器一致。",
        "features": "",
    },
    {
        "version": "v43.246",
        "date": "2026-10-23",
        "fixes": "半成品分类卡片「放大」按钮点击报 AttributeError：'AltController' object has no attribute 'zoom_semi_table'。根因：v43.222 ARC-003 重构把 _zoom_semi_table 的方法体从 MainWindow 迁出时漏了这条（薄壳 self.alt_controller.zoom_semi_table(self) 指向不存在的方法），left_panel.py:302 的放大按钮一按就崩。修法：把放大窗口实现直接恢复在 MainWindow._zoom_semi_table（用 _get_semi_category_list 与左侧 semi_tree 同源），不再转发。",
        "features": "半成品分类放大窗口：显示 工厂·分类 / 物料数 / 示例物料 三列，双击任意行筛选该分类到主表。",
    },
    {
        "version": "v43.245",
        "date": "2026-10-23",
        "fixes": "无备注预警口径再次对齐业务方（裴哥 15:34 明确 B 选项）：从 v43.244 的「10%<=|偏差率|<100%」放宽为「|偏差率|>=10% 且 !=100.0%」（浮点容差 1e-6）。含义：>100% 的严重超耗行回归无备注预警（此前 v43.244 一并排除），仅排除恰好=100% 一条线（未投料-100% + 恰好翻倍+100%）。理由：>100% 属可预警的严重超耗模式，业务价值明显；仅 100.0% 精确值属巧合/边界，剔除即可。",
        "features": "无备注预警恢复对 >100% 严重超耗行的覆盖，同时精确剔除恰好 100% 边界。",
    },
    {
        "version": "v43.244",
        "date": "2026-10-23",
        "fixes": "无备注预警口径按业务方（裴哥）确认修正：纳入条件由 |偏差率| > 阈值 改为 |偏差率| >= 阈值（含 10.0% 边界），并新增排除 |偏差率| = 100% 的行（完全未投料和恰好翻倍属明确业务模式，不属「模糊无备注预警」范畴）。仅动 sheet3_no_note.py 过滤条件一行 + 严重度标签注释同步更新。",
        "features": "无备注预警严格对齐业务口径 10% <= |偏差率| < 100%。",
    },
    {
        "version": "v43.243",
        "date": "2026-10-23",
        "fixes": "报表层四项优化（不动 analyzer.py/sheet2_alt.py 红线）：① 中间地带明细排除 0 偏差死行（1,553/5,448=28.5% 零信息行）；② 无备注预警加严重度标签列（🔴完全未投料/🟠严重偏差/🟡超阈值）+ 双键排序（等级优先、金额次之）；③ 汇总统计新增「数量偏差合计金额(含税)」「价格差异金额(含税)」两列，让「正+负 ≠ 总」可勾稽追溯；④ 趋势分析表头错位修正（period_desc 挪到 A1 独立行、冻结格同步 A3，加最早/最新订单日期两列可回溯订单窗口）。",
        "features": "P0 中间地带 1 行改代码去掉 28.5% 死行；P1 无备注按严重度自动分级；P1 汇总口径可勾稽；P2 趋势表可追溯到订单日期。偏差原因分析 sheet 新增脚注说明「替代料类别已由替代料明细 sheet 独立分析」。",
    },
    {
        "version": "v43.242",
        "date": "2026-10-23",
        "fixes": "替代料明细「偏差率A/B/净偏差率」数值已折算为比率小数（v43.241）但 post_process._apply_number_formats 漏了按列名识别比率列套 0.00% 格式，导致 Excel 里 0.08171 原样显示而非 8.17%（用户截图反馈）。修法：_apply_number_formats 增加 ratio_cols 识别（按 _RATIO_KEYS 列名匹配），统一套 _FMT_RATIO；与 _normalize_ratio_columns（处理 % 结尾文本）互补，覆盖真数值比率列。",
        "features": "替代料明细偏差率列在 Excel 中显示为百分比；汇总表备注覆盖率同步套 0.00% 格式。",
    },
    {
        "version": "v43.241",
        "date": "2026-10-23",
        "features": "Excel 导出报表优化：① 分析说明新增「导出时间/软件版本」行（便于追溯）；② 异常预警首列表头 订单开始日期→订单日期（与其余明细表列名统一）；③ 替代料明细「偏差率A/B/净偏差率」统一为比率小数口径（与完整明细/无备注预警一致，修浮点长尾 -0.009000000000000001）；④ 驾驶舱新增 4 个 KPI 数字块（总记录/正负金额/无备注预警条数）；⑤ 汇总表条目补口径说明（总偏差金额含价格差异行，正+负≠总属设计口径非 bug）。",
        "fixes": "替代料明细「净偏差率」列浮点长尾 -0.009000000000000001 等 16 位小数：round(x,6) 修复；「偏差率A/B」量纲混用（-100/13.429/-0.027 并存）：统一折算为比率小数。",
    },
    {
        "version": "v43.240",
        "date": "2026-10-23",
        "fixes": "修复'变动提醒全设为已读后，清空替代料看板又变未读'的 bug。根因：_recalculate_net_offset 读的是 view_model.df，其 _read 副本未被'全设为已读'更新（只写了 source_model+DB，仍是 0）；重算净偏差后 apply_net_offset 保留该 _read=0 列，setDataFrame 写回 source_model 时把刚标好的 _read=1 覆盖回 0，导致变动提醒又被判定为未读。修法：净偏差重算后（空配对/有配对两条分支）统一调用 data_service._restore_read_status 从 DB 重新派生 _read/_post_audit_changed，已读状态跨净偏差重算存活（净偏差重算不改变被变更检测比对的'实际数量/备注原因/产量'，故不会误触发新变动）。",
        "features": "变动提醒已读状态跨'清空/重置替代料配对'存活：清空替代料看板不再把已读记录翻回未读。",
    },
    {
        "version": "v43.239",
        "date": "2026-10-23",
        "fixes": "修复隔离区'仍负损却显示自动已读'的陈旧状态问题：在隔离区对话框 set_data 开头对主表跑一次'隔离区已读对账'，把'之前已解决被自动已读、现数据变动成仍负损'的记录翻回未读并弹变动提醒。根因：对账原函数只在'重新分析'时触发，打开隔离区对话框不触发，导致陈旧 auto 标记残留、隔离区里'仍负损'记录却显示'自动已读'。",
        "features": "隔离区打开即自愈：已读对账下沉到对话框打开时执行，不再依赖重新分析；'自动已读→负损'的变动会自动翻未读并提示。",
    },
    {
        "version": "v43.238",
        "date": "2026-10-22",
        "fixes": "修复标记为已豁免自动移出隔离区 - 移除隔离行为并更新主表、对话框内存，使豁免记录立即消失。",
        "features": "标记为已豁免时自动移出隔离区：右键菜单选择'标记为已豁免'后，记录会立即被移出隔离区并从隔离区列表中消失。",
    },
    {
        "version": "v43.236",
        "date": "2026-10-22",
        "fixes": "修复隔离区豁免功能三个 bug：1) 右键菜单文本方向错误（未豁免显示取消豁免->标记为已豁免）；2) 失效复核仍显示豁免记录（is_exempted 查询逻辑已验证正确，但注入数据库；3) 隔离区列表增加豁免状态列显示'是'或空。",
        "features": "在隔离区列表中添加'豁免'状态列，显示'是'表示已标记为豁免。",
    },
    {
        "version": "v43.231",
        "date": "2026-10-21",
        "features": "为右键菜单添加复制为微信草稿功能：将选中行的订单、物料、偏差数量/金额、备注等整理成微信友好的文本，复制到剪贴板便于快速沟通。",
        "fixes": "**根因**：缺少快速沟通整理功能，需要手动复制多列信息。**病根**：右键菜单只有基础复制项，没有结构化摘要。**修法**：在 _show_context_menu 中添加[复制为微信草稿] 菜单项，并实现 _copy_wechat_draft 方法，格式化文本到剪贴板。**验收**：py_compile 无语法错误；右键选中行点击复制为微信草稿，可计算出生效结果。**反证**：回退菜单项添加 → 无法快速生成结构化沟通文本。",
    },
    {
        "version": "v43.230",
        "date": "2026-10-21",
        "features": "为明细弹窗添加复制图片功能：点击按钮将弹窗界面复制为图片到剪贴板",
        "fixes": "**根因**：缺少截图保存功能。**病根**：弹窗界面无法直接保存为图片格式。**修法**：在 _show_row_detail() 对话框中添加[复制图片] 按钮，使用 QPixmap.grabWindow() 捕获整个对话框并复制到剪贴板。**验收**：py_compile 无语法错误；双击主表行打开详情后点击按钮可将弹窗图片复制到剪贴板。**反证**：回退按钮添加 → 无法一键复制弹窗图片。",
    },
    {
        "version": "v43.229",
        "date": "2026-10-21",
        "features": "修复 QDialog 创建时父容器传递错误：将 QDialog(self) 改为 QDialog(self.mw)",
        "fixes": "**根因**：ColumnController 和 DashboardController 中创建的 QDialog 使用 self 作为父容器，但控制器不是 QWidget，导致错误。**病根**：控制器类是纯 Python 类，不是 QWidget 子类，不能作为 QDialog 的父容器。**修法**：将所有 QDialog(self) 改为 QDialog(self.mw)。**验收**：py_compile 无语法错误；程序启动正常，弹窗工作正常。**反证**：回退 → 程序崩溃报 'PySide6.QtWidgets.QWidget.__init__' called with wrong argument types'。",
    },
    {
        "version": "v43.228",
        "date": "2026-10-21",
        "features": "恢复看板与导出的下拉菜单选项，替代料看板等不再单独按钮，而是通过工具栏按钮显示菜单",
        "fixes": "**根因**：重构后工具栏按钮缺少下拉菜单，导致所有看板选项和导出选项无法选择。**病根**：LayoutComposer 移除了 QMenu 的创建。**修法**：为 action_btn_boards 和 action_btn_export 按钮添加 QMenu，菜单项包括所有看板（替代料、偏差率预警、负损、正损、隔离区复盘、数据稳定性、替代料长链、物料画像、半成品）和导出选项。**验收**：py_compile 无语法错误；点击工具栏按钮显示下拉菜单，所有选项可点击并打开相应对话框。**反证**：回退菜单添加 → 工具栏按钮点击后无任何菜单出现，功能无法使用。",
    },
    {
        "version": "v43.227",
        "date": "2026-10-21",
        "features": "修复 body_splitter 属性缺失错误：将 body_splitter 引用保存到 MainWindow",
        "fixes": "**根因**：body_splitter 在 LayoutComposer 内部创建后未保存到 MainWindow，导致 _toggle_left_panel() 和 _toggle_filter_panel() 访问时属性缺失。**病根**：UI 组装器创建局部变量未外泄，导致 MainWindow 自身方法无法访问。**修法**：在 assemble() 方法末尾添加 mw.body_splitter = body_area，将 body_splitter 引用保存到主窗口。**验收**：py_compile 无语法错误；程序启动正常，左侧/筛选面板切换功能正常。**反证**：回退 → 程序报 'MainWindow' object has no attribute 'body_splitter'。",
    },
    {
        "version": "v43.226",
        "date": "2026-10-21",
        "features": "修复 top_panel 属性缺失错误：将 top_panel 引用保存到 MainWindow",
        "fixes": "**根因**：LayoutComposer 创建 top_panel 后未保存到主窗口，控制器访问时属性缺失。**病根**：UI 组装器创建局部变量未外泄，导致 UISettingsController 无法访问。**修法**：在 _make_body_area() 中创建 top_panel 后，添加 mw.top_panel = top_panel，将引用保存到 MainWindow 对象。**验收**：py_compile 无语法错误；程序启动正常，top_panel 可见性控制功能正常。**反证**：回退 → 程序报 'MainWindow' object has no attribute 'top_panel'。",
    },
    {
        "version": "v43.225",
        "date": "2026-10-21",
        "features": "修复按钮属性不存在错误：调整 UI 初始化顺序",
        "fixes": "**根因**：_setup_connections() 在 _assemble_layout() 之前调用，导致按钮属性不存在。**病根**：顺序错误导致 signal slot 连接失败。**修法**：调整调用顺序，先 _assemble_layout() 创建按钮，再 _setup_connections() 连接信号。**验收**：py_compile 无语法错误；程序启动正常，工具栏按钮点击有效。**反证**：回退顺序 → 程序崩溃报 'MainWindow' object has no attribute 'action_btn_analyze'。",
    },
    {
        "version": "v43.224",
        "date": "2026-10-21",
        "features": "工具栏按钮信号连接修复；pandas 导入缺失修复；启动错误修复。",
        "fixes": "**根因**：工具栏按钮点击事件未连接；UISettingsController 缺少 pandas 导入；run_pyside6.py 使用已废弃 get_current_version。**病根**：重构后遗漏按钮信号连接；__init__.py 引入新文件但未检查依赖；版本历史管理 refactor 后遗留未清理。**修法**：在 _setup_connections() 中添加 12 个工具栏按钮点击连接；uisettings_controller.py 添加 import pandas as pd；run_pyside6.py 使用 VERSION_HISTORY[0]['version']。**验收**：py_compile 无语法错误；工具栏按钮恢复正常功能；程序启动无 ImportError。**反证**：回退 → 工具栏按钮点击无响应；运行程序报 ImportError。",
    },
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
