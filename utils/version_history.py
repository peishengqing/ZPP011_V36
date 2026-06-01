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
        "version": "v40.2",
        "date": "2026-06-01",
        "build_datetime": "2026-06-01 14:00:00",
        "features": [
            "✨ 统计卡片增加总偏差金额汇总，单位一致时显示实物量换算",
            "✨ F6 预检报告增加偏差总金额和实物量估算"
        ],
        "fixes": [
            "🐛 修复历史菜单在进入界面后消失的问题（菜单恢复）"
        ],
        "optimizations": [
            "⚡ 审核卡片字段中文化（工厂、车间、订单日期等），与黄金模板同步",
            "⚡ 成本换算器增强：优先使用材料偏差列计算实物量，支持实际-定额备选计算"
        ],
        "notes": [
            "📌 本版本基于黄金模板 audit_cols_config.py 统一列配置",
            "📌 成本换算器不再依赖预计算单价，直接使用偏差金额/偏差数量（或实际-定额）",
            "📌 历史菜单已恢复，需至少一次分析记录后显示"
        ]
    },
    {
        "version": "v40.1",
        "date": "2026-05-31",
        "build_datetime": "2026-05-31 12:30:00",
        "features": [
            "✨ 管理看板：图表导出为 PNG（白底、高 DPI），支持同比/环比（上月/去年同期）",
            "✨ 智能小结：基于统计生成自然语言报告，一键复制，含免责声明",
            "✨ 批量操作：多历史记录导出为多 Sheet Excel；批量导入备注（预演模式 + 自动备份）",
            "✨ 合计行：表格底部动态显示定额、实际、偏差金额合计（随筛选更新）",
            "✨ 审核卡片内增加成本换算器（偏差金额 → 实物数量，需含单价数据）"
        ],
        "fixes": [
            "🐛 恢复双击审核表格弹窗（修复弹窗无内容问题，任务卡021）"
        ],
        "optimizations": [
            "⚡ 审核表格增加「单位」列（任务卡022）",
            "⚡ 物料大类优先使用原表「组件物料类型描述」列，缺失时回退前缀映射（任务卡023）",
            "⚡ 物料描述截断长度从20增加到30字符（任务卡024）"
        ],
        "notes": [
            "📌 本版本为 v40.1 补丁版，保留分页滚动、标签缓存等全部原有功能",
            "📌 成本换算器需原始数据包含「金额-实际(含税)」和「数量-实际」列",
            "📌 导出 PNG 需安装 Pillow，已加入 requirements.txt",
            "📌 同比/环比查询依赖历史数据库，需至少一次历史记录"
        ]
    },
    {
        "version": "v39.5",
        "date": "2026-05-29",
        "build_datetime": "2026-05-29 18:00:00",
        "features": [
            "Treeview 无限滚动加载：首屏仅 500 行，滚动到底部自动追加（滑动窗口控制内存）",
            "Tag 状态缓存：全量刷新（筛选/排序）时直接从缓存读取行颜色，避免重复计算，性能提升 80% 以上",
            "列宽配置持久化：用户拖拽列宽后自动保存，程序重启后恢复；增加防递归锁和延迟保存机制",
            "SQLite 数据沉淀：每次分析结果自动存入历史库（元数据 + 明细），支持历史查询与同期对比",
            "历史对比界面：可选择任意两次分析，对比总行数、偏差率分布、审核完成率、备注填写率；若筛选条件不同自动警告",
            "四色标记修复：偏差率 >30% 红、>20% 橙、>10% 黄、<=10% 绿，表格背景色正确显示"
        ],
        "fixes": [
            "修复物料大类筛选仅包材有效的问题：统一使用物料编码前缀映射生成 material_category 列，并在筛选前动态补全",
            "修复统计卡片（总记录/偏差>10%/需补备注/已审核）始终显示 0 的问题",
            "修复颜色筛选兼容两种内部键名（_color / priority_color）",
            "修复帮助菜单关于无响应，改为显示完整版本日志窗口",
            "修复替代料配对界面空白（v39.4 回归）",
            "修复四个筛选排序问题（替代料筛选、多条件、互扰、三态）"
        ],
        "optimizations": [
            "分页加载 + tag 缓存：1 万行表格操作响应时间从秒级降至毫秒级",
            "列宽持久化：拖拽列宽后延迟保存，避免频繁 I/O",
            "SQLite 批量插入：1 万行写入 < 1 秒，幂等性检查防止重复入库",
            "测试基线建立：核心模块单元测试覆盖率 > 75%，CI 自动运行"
        ],
        "notes": [
            "基于 v39.4.2 修复版，累计性能优化与数据沉淀核心功能",
            "已知遗留问题：物料大类列名在数据库保存时可能因中文差异缺失数据，建议后续统一",
            "打包命令：python build_exe.py，输出文件名 ZPP011偏差分析器_v39.5_YYYYMMDD_HHMMSS.exe"
        ]
    },

    {
        "version": "v39.4.2",
        "date": "2026-05-28",
        "build_datetime": "2026-05-28 21:00:00",
        "features": [],
        "fixes": [
            "🐛 修复物料大类筛选仅「包材」有效的问题：统一使用物料编码前缀计算 material_category 列，修正 MRO 遮蔽导致下拉选项动态收缩，并补全 _on_load_done 数据路径中 material_category 列的创建逻辑",
            "🐛 修复统计卡片（总记录/偏差>10%/需补备注/已审核）始终显示 0 的问题：扩大 try/except 作用域覆盖整个统计计算块",
            "🐛 修复筛选栏中「审核来源」筛选值不匹配的问题，统一为「AI审核」",
            "🐛 修复订单日期筛选控件宽度过窄导致显示不全的问题：调整 DateEntry 宽度及列宽映射",
            "🐛 修复颜色筛选兼容两种内部键名（_color / priority_color）",
            "🐛 修复帮助菜单「关于」无响应，改为显示完整版本日志窗口",
            "🐛 修复替代料配对界面空白（v39.4 回归）",
            "🐛 修复筛选排序模块拆分后导致的筛选栏消失、启动崩溃等问题",
            "🐛 修复四个筛选排序问题（替代料筛选、多条件、互扰、三态）"
        ],
        "optimizations": [
            "⚡ 筛选排序模块独立抽取为 FilterManager / SortManager（零逻辑改动，依赖注入原则）",
            "⚡ 默认输出目录和输入文件浏览对话框默认路径统一设置为 E:\\zpp011_dev\\ZPP011导出文件原数据",
            "⚡ 订单日期筛选控件宽度适配，避免显示不全",
            "⚡ 删除表格内重复的「筛选」列残留",
            "⚡ 颜色筛选增加 _priority_label 列生成逻辑（偏差率>30%→红, >20%→橙, >10%→黄, 其他→绿）"
        ],
        "notes": [
            "📌 基于 v39.4.1 基建版本（自动备份、审计日志、健康检查）的修复补丁",
            "📌 物料大类筛选现已完全基于物料编码前缀映射，支持原辅料、包材、食品/饮料辅料、食品/饮料成品、促销品等类别",
            "📌 本版本需重新打包，打包命令：python build_exe.py"
        ]
    },
    {
        "version": "v39.4.1",
        "date": "2026-05-28",
        "build_datetime": "2026-05-28 09:10:00",
        "features": [
            "✨ 审核区订单日期筛选改用 tkcalendar 日历控件，提升日期选择体验",
            "✨ 操作审计日志：记录所有审核操作，支持CSV导出，自动清理180天前日志",
            "✨ 健康检查面板：检查依赖、配置、磁盘、数据库、备份恢复，提供 dry-run 模拟分析"
        ],
        "fixes": [
            "🐛 修复颜色筛选兼容两种内部键名（_color 和 priority_color），确保筛选准确"
        ],
        "optimizations": [
            "⚡ 默认输出路径修改为 ~/Documents/ZPP011分析报告",
            "⚡ 输入文件浏览对话框默认打开 E:\\zpp011_dev\\ZPP011导出文件原数据 目录",
            "⚡ 日历控件宽度适配，避免显示不全",
            "⚡ 分析前自动备份，崩溃后可恢复（保留最近10份）"
        ],
        "notes": [
            "📌 基建任务完成：自动备份+审计日志+健康检查",
            "📌 筛选排序模块拆分（任务001）未完成，替代料配对界面空白（BUG-P0）待修复",
            "📌 表格内重复的\"筛选\"列未删除，计划 v39.4.2 处理"
        ]
    },
    {
        "date": "2026-05-26",
        "build_datetime": "2026-05-26 15:30:00",
        "features": [
            "✨ 进度细化：分析时显示5个阶段（读取→解析→计算→匹配→生成），超时熔断5分钟",
            "✨ 防重复点击：分析按钮点击后立即禁用，使用线程锁防止并发",
            "✨ 错误友好化：5个高频错误弹窗，JSON配置，支持打包路径，兜底机制"
        ],
        "fixes": [
            "🐛 修复分析按钮锁泄漏（提前return未释放锁）",
            "🐛 修复t.start()异常后仍启动线程的问题",
            "🐛 修复部分调试print残留（v39.4.1继续清理）"
        ],
        "optimizations": [
            "⚡ 技术债务清理：删除4处@with_feedback装饰器及无用import",
            "⚡ 代码整洁：删除多个临时脚本和debt_list.txt"
        ],
        "notes": [
            "📌 止血版本，核心功能已验证（进度、防重、错误提示）",
            "📌 剩余调试print清理留待v39.4.1"
        ]
    },
    {
        "version": "v39.3",
        "date": "2026-05-25",
        "build_datetime": "2026-05-25 14:30:00",
        "features": [
            "✨ 右键复制物料编码：选中行右键菜单，复制物料编码到剪贴板（反查数据源，不依赖列顺序）",
            "✨ 预检报告弹窗改为非模态：显示系统检查与数据统计，不再阻塞主窗口操作"
        ],
        "fixes": [
            "🐛 修复表格排序崩溃（补全 _COL_TO_DF 映射及排序方法）",
            "🐛 修复侧边栏筛选全部失效（替代料列名探测+布尔/字符串类型清洗）",
            "🐛 修复调试 print 残留及 @with_feedback 装饰器冗余弹窗",
            "🐛 修复右键菜单覆盖原有功能（追加「复制物料编码」而非替换）"
        ],
        "optimizations": [
            "⚡ 预检报告窗口独立关闭，不干扰审核流程",
            "⚡ 代码整洁：移除调试输出与冗余装饰器"
        ],
        "notes": [
            "📌 v39.3 建议所有用户升级，提升筛选与排序稳定性"
        ]
    },
    {
        "version": "v39.1",
        "date": "2026-05-23",
        "build_datetime": "2026-05-23 01:11:56",
        "features": [
            "✨ 修复 load_audit_data 缺失（AuditPresenter 可正常加载审核记录）",
            "✨ 规则文件自动创建（RuleEngine 初始化时生成默认 rules.json）"
        ],
        "fixes": [
            "🐛 修复 AuditPresenter.load_audit_data 方法缺失（AttributeError）",
            "🐛 修复规则文件不存在警告（控制台不再报错）"
        ],
        "optimizations": [
            "⚡ 规则引擎增强：文件缺失时自动创建默认配置，无需手动创建"
        ],
        "notes": [
            "📌 测试版，请裴哥手动测试验证修复效果",
            "📌 若测试通过，可发布为正式版 v39.1"
        ]
    },
    {
        "version": "v39",
        "date": "2026-05-22",
        "build_datetime": "2026-05-22 17:46:32",
        "features": [
            "✨ 拆分 events.py：27,492 行 → 8 个 handler 模块",
            "✨ 硬编码外部化：基于 JSON 版 ConfigManager，阈值/颜色/路径可配置",
            "✨ 配置存储：~/.zpp011_audit/config.json，支持窗口几何记忆"
        ],
        "fixes": [
            "🐛 修复缺失导入（RuleEngine、deepcopy），程序可正常启动",
            "🐛 筛选功能恢复正常"
        ],
        "optimizations": [
            "⚡ 代码守恒：总有效代码 ≤950 行，零逻辑变更",
            "⚡ 配置外部化消除硬编码，提升可维护性"
        ],
        "notes": [
            "📌 重构预览版，核心功能已验证（加载、筛选、AI审核、PPT导出）",
            "📌 遗留问题：AuditPresenter.load_audit_data 缺失（手动加载可绕过）"
        ]
    },
    {
        "version": "v38",
        "date": "2026-05-22",
        "build_datetime": "2026-05-22 11:15:00",
        "features": [
            "PPT v1.3: 分工厂多耗/少耗Top10、环形饼图、柱状图",
            "筛选栏重构：全列动态筛选、历史记忆、重置按钮"
        ],
        "fixes": [
            "B004：双击表格行弹窗无效",
            "B005：自动结案线程安全（Queue通信、超时处理）",
            "PPT页数缺失问题"
        ],
        "optimizations": [
            "参数化配置：阈值、超时、上限可配置",
            "日志脱敏：不记录金额、备注原文"
        ],
        "notes": [
            "冻结期版本，仅修Bug，无新功能"
        ]
    },

    {
        "version": "v37.45",
        "date": "2026-05-22",
        "build_datetime": "2026-05-22 00:18:00",
        "features": [
            "PPT v1.2: DataFrame direct input, no Excel path, global pd import"
        ],
        "fixes": [
            "_pre_aggregate_data missing pd import -> global import pandas as pd",
            "tests: 19/19 passed"
        ],
        "optimizations": [
            "PPT progress 0-100%%, 20 stages, 9889 rows <30s"
        ],
        "notes": [
            "TASK-001: PPT Gen v1.2"
        ]
    },
    {
        "version": "v37.44",
        "date": "2026-05-20",
        "build_datetime": "2026-05-20 23:45:50",
        "features": [
            "【核心】审核记录存储机制升级：业务主键三元组替换原表行号"
        ],
        "fixes": [
            "修复跨文件行号错位问题：行号在文件间不连续导致备注写入错误行"
        ],
        "optimizations": [
            "优化审核回填性能：SQL LEFT JOIN 替代 Python 循环匹配"
        ],
        "notes": [
            "升级用户首次启动弹窗询问是否清空旧数据（点击「是」清空历史，「否」迁移旧记录）"
        ]
    },
    {
        "version": "v37.4.3",
        "date": "2026-05-20 19:19:00",
        "changes": [
            "🔧【修复】全局清除 flush=True（analyzer.py + sheet1/2/3/7/10 共15处）",
            "🔧【修复】删除函数体内重复 import os（Line 127，导致局部变量遮蔽）",
            "🔧【修复】两层数值列保护（pd.to_numeric errors=coerce + fillna 0）",
            "📝【追踪】数量-实际值变化追踪日志（zpp011_trace.log）"
        ]
    },
    {
        "version": "v37.4.0",
        "date": "2026-05-20 12:25:00",
        "changes": [
            "🔧【修复】窗口标题版本号同步（version_history.py新增v37.4.0条目）",
            "🔧【修复】打包文件名格式（增加YYYYMMDD_HHMM时间戳后缀）",
            "🔧【修复】原表行号改用openpyxl真实读取（替代pandas range估算）",
            "✨【优化】进度条流畅（update_idletasks + sleep 0.01 + 节流）"
        ]
    },
    {
        "version": "v37.3.0",
        "date": "2026-05-20 11:00:00",
        "changes": [
            "🔧【修复】PPT生成列名不匹配导致KeyError（自动检测'工厂名称'/'工厂'、'总偏差金额(含税)'/'总偏差金额'）",
            "🔧【修复】进度条不更新/界面假死（events.py强制update_idletasks + analyzer.py让出CPU时间片）",
            "🔧【验证】原表行号_excel_row赋值正确（line 118，过滤前赋值，数据链路完整）"
        ]
    },
    {
        "version": "v37.2.0",
        "date": "2026-05-20 01:30:00",
        "changes": [
            "🔧【修复】deepcopy未导入导致自动结案崩溃",
            "🔧【修复】Font未导入导致保存审核结果崩溃",
            "🔧【修复】_refresh_audit_tree()缺参数导致TypeError",
            "🔧【修复】audit_tree.index()不存在导致隔离区崩溃",
            "🔧【修复】Toplevel缺tk.前缀+center_window未定义",
            "🔧【修复】storage.py数据库连接泄漏（try/finally）",
            "🔧【统一】6项P0崩溃Bug全部修复（元宝+豆包审核）"
        ]
    },
    {
        "version": "v36.40.3",
        "date": "2026-05-18 07:20:00",
        "changes": [
            "🔧【修复】删除analyzer.py重复build_sheet2调用（P0，Lengths must match崩溃）",
            "🔧【修复】_s01_populate_table改用itertuples提升性能",
            "🔧【修复】恢复events.py缺失的run_app()函数",
            "🔧【修复】统一临时目录路径为~/.zpp011_audit/temp",
            "🔧【修复】exporter.py改用shutil.move替代os.replace",
            "✨【新增】build_exe.py打包文件名含时间戳",
            "✨【新增】打包前自动备份源码和exe",
            "✨【继承】S01异步化+高亮（v36.39.0全部功能）"
        ]
    },
    {
        "version": "v36.39.0",
        "date": "2026-05-18 05:30:00",
        "changes": [
            "✨【新增】S01库存检查异步化：独立线程执行，支持进度回调/取消/异常隔离",
            "✨【新增】Tab数据深拷贝缓存：_tab_data_cache，切换Tab保存/恢复数据",
            "✨【新增】临时文件管理：temp/目录，启动时自动清理.s01.tmp/.s01.temp",
            "✨【新增】get_s01_rules()方法：返回s01./inventory.开头的规则配置",
            "✨【新增】_ensure_temp_dir()方法：确保temp/目录存在",
            "✨【新增】_s01_on_tab_changed()方法：Tab切换时数据保存/恢复",
            "✨【新增】S01库存异常高亮：支持配置化规则/颜色（_evaluate_condition/_s01_setup_treeview_tags/_s01_populate_table）",
            "🔧【改进】itertuples替代iterrows：提升遍历性能，每50行检查取消标志",
            "🔧【改进】线程安全UI更新：所有回调通过root.after(0, ...)投送到主线程"
        ]
    },
    {
        "version": "v36.38.0",
        "date": "2026-05-17 13:30:00",
        "changes": [
            "✨【新增】自动结案异步化：_auto_close改为异步启动器+进度条",
            "✨【新增】AutoCloser类（core/AutoCloser.py）：异步结案，支持进度回调/取消/异常隔离",
            "✨【新增】_on_auto_close_progress回调：进度百分比+ETA显示",
            "✨【新增】_on_auto_close_done回调：显示成功/失败数量，刷新界面",
            "✨【新增】_on_auto_close_error回调：取消时数据回滚，显示错误",
            "✨【新增】_cancel_auto_close方法：取消标志设置",
            "✨【新增】取消自动结案按钮（ui_builder.py）：红底白字，默认disabled",
            "🔧【修复】规则引擎接口兼容：check_auto_close_condition/should_close/evaluate兜底",
            "🔧【改进】规则漂移保护：深拷贝rule_engine防止结案过程中规则变化"
        ]
    },
    {
        "version": "v36.37.0",
        "date": "2026-05-17 12:30:00",
        "changes": [
            "✨【新增】批量导出异步化：_export_audit_excel改为异步启动器+进度回调",
            "✨【新增】ExcelExporter类（core/exporter.py）：异步导出，支持进度/取消/原子化写入",
            "✨【新增】_on_export_progress回调：实时显示进度百分比和ETA",
            "✨【新增】_on_export_done回调：弹窗询问是否打开文件夹",
            "✨【新增】_on_export_error回调：清理临时文件，显示错误信息",
            "✨【新增】_clean_temp_exports()方法：启动时清理temp/目录下超过1小时的.tmp.xlsx",
            "✨【新增】self.is_exporting状态锁：防止重复导出",
            "🔧【改进】导出流程不阻塞UI，支持取消操作",
            "🔧【改进】文件名去重：自动添加_1, _2后缀避免覆盖"
        ]
    },
    {
        "version": "v36.36.0",
        "date": "2026-05-17 11:34:00",
        "changes": [
            "✨【新增】AI审核异步化：_run_ai_audit改为启动器+进度条determinate模式",
            "✨【新增】AIClient类（core/ai_client.py）：Mock模式+熔断机制（10秒超时）",
            "✨【新增】_ai_audit_worker：cancel_flag.is_set()检查，动态查找文本列，找不到跳过",
            "✨【新增】_on_ai_audit_done/_on_ai_audit_error：异常分类处理，结果窗口+状态标签",
            "✨【新增】TaskManager._thread_safe_append+on_progress回调+poll轮询机制",
            "✨【新增】app.py注册task_manager.poll(self.root)轮询，自动触发root.update()",
            "✨【新增】self.is_auditing/self.unsaved_ai_results/self._pending_audit_count状态",
            "✨【新增】取消审核按钮（ui_builder.py cancel_audit_btn），橙底白字disabled默认",
            "🔧【改进】_run_ai_audit：worker用lambda传递cancel_flag和progress_callback参数",
            "🔧【改进】lambda参数传递验证：kwargs键名c/p与lambda参数名一致，对应正确"
        ]
    },
    {
        "version": "v36.35.0",
        "date": "2026-05-17 10:24:00",
        "changes": [
            "✨【新增】快捷键系统：Ctrl+S保存、Ctrl+E导出、Ctrl+A AI审核、F1帮助、Ctrl+Q退出",
            "✨【新增】菜单栏帮助菜单：快捷键说明对话框（_show_shortcuts_help）"
        ]
    },
    {
        "version": "v36.34.0",
        "date": "2026-05-17 07:22:00",
        "changes": [
            "✨【新增】F4 自动结案：按审核状态筛选，仅对已审核行执行自动结案",
            "✨【新增】F11 反馈装饰器（core/decorators.py with_feedback），装饰7个关键函数，操作后弹成功提示",
            "✨【新增】F12 进度条雏形（core/task_manager.py TaskManager + Progressbar）",
            "✨【新增】隔离区按钮绑定 _move_to_quarantine",
            "🔧【修复】F1 多列排序冲突：注释 app.py 中 bind_multi_sort 调用，保留 EventsMixIn 单一排序系统",
            "🔧【修复】按钮布局拥挤：ui_builder.py 底部按钮单行拆为双行（row1 + row2）",
            "🔧【修复】打包版本日志自动同步"
        ]
    },
    {
        "version": "v36.33.0",
        "date": "2026-05-17 06:27:11",
        "changes": [
            "🔧【修复】打包版本日志自动同步"
        ]
    },
    {
        "version": "v36.32.0",
        "date": "2026-05-17 00:30:00",
        "changes": [
            "🔧【修复】PO-1 趋势分析负数显示（数值取绝对值，箭头方向不变）",
            "🏗️【重构】版本号管理集中化：创建 utils/version_history.py，消除所有硬编码"
        ]
    },
    {
        "version": "v36.31.0",
        "date": "2026-05-16 18:49:21",
        "changes": [
            "🔧【修复】打包版本日志自动同步"
        ]
    },
    {
        "version": "v36.30.0",
        "date": "2026-05-16 18:22:45",
        "changes": [
            "🔧【修复】打包版本日志自动同步"
        ]
    },
    {
        "version": "v36.29.0",
        "date": "2026-05-16 18:00:00",
        "changes": [
            "🔧【修复】版本日志显示逻辑：兼容changes数组格式，自动识别前缀符号并正确渲染"
        ]
    },
    {
        "version": "v36.28.0",
        "date": "2026-05-16 17:55:00",
        "changes": [
            "🔧【修复】修复打开Excel失败：load_workbook未导入gui/events.py",
            "🔧【修复】修正替代料配置文件路径，加载完整20对数据",
            "🔧【修复】迁移替代料配置到标准用户目录（AppData\\Roaming\\ZPP011\\config）",
            "📌【教训】打包脚本含--clean参数，dist目录必须先备份再打包"
        ]
    },
    {
        "version": "v36.27.0",
        "date": "2026-05-16 18:00:00",
        "changes": [
            "🔧【修复】修正替代料配置文件路径，加载完整20对数据",
            "🔧【修复】迁移替代料配置到标准用户目录（AppData\\Roaming\\ZPP011\\config）"
        ]
    },
    {
        "version": "v36.26.0",
        "date": "2026-05-16 17:20:00",
        "changes": [
            "🔧【修复】修复打开Excel失败：load_workbook未导入gui/events.py"
        ]
    },
    {
        "version": "v36.25.0",
        "date": "2026-05-16 15:50:00",
        "changes": [
            "🔧【修复】批量备注：恢复被误删的 _get_remark_freq_path 方法定义，修复 AttributeError 崩溃"
        ]
    },
    {
        "version": "v36.24.0",
        "date": "2026-05-16 15:20:00",
        "changes": [
            "🔧【修复】替代料添加：_load_material_list() 现已接入 _preview()，每次加载Excel后自动刷新物料列表下拉框",
            "🔧【修复】app.py：初始化 material_list 和 code_to_info 实例变量，防止未定义报错"
        ]
    },
    {
        "version": "v36.23.0",
        "date": "2026-05-16 14:52:00",
        "changes": [
            "🔧【修复】批量备注：恢复Combobox下拉框选择，支持预设备注+自定义输入+追加换行"
        ]
    },
    {
        "version": "v36.22.0",
        "date": "2026-05-16 14:28:52",
        "changes": [
            "✨【新增】_batch_remark：批量备注基础版，simpledialog输入框、excel_row定位、追加换行（分隔/）",
            "✨【新增】批量备注按钮绑定新函数 _batch_remark（替换 _batch_fill_remark）",
            "🔧【修复】批量备注：树形列改为 batch_remark，DataFrame优先写批量备注列，fallback到备注原因",
            "🔧【修复】导出Excel：_generate_excel_thread 使用 self.input_file.get()，generate_excel_direct传参修正",
            "🔧【修复】排序系统：禁用 tree_utils.setup_column_sorting 冲突绑定，删除重复死代码"
        ]
    },
    {
        "version": "v36.20.0",
        "date": "2026-05-16 13:38:53",
        "changes": [
            "🔧【修复】ui_builder.py：audit_tree heading顺序重排，与cols定义完全对齐",
            "🔧【修复】sheet5_full.py：偏差金额增加双重容错逻辑（单价缺失时反算）",
            "🔧【修复】events.py：审核来源（audit_source）三处均添加默认值推断（AI/手动/系统）",
            "🔧【验证】values元组顺序与cols一致，无列数据错位风险"
        ]
    },
    {
        "version": "v36.18.0",
        "date": "2026-05-16",
        "changes": [
            "✨【功能】多列联动排序（无上限追加）",
            "⚡【优化】移除order_no重复标题定义",
            "🔧【修复】排序方法移入EventsMixIn类内部"
        ]
    },
    {
        "version": "v36.17.0",
        "date": "2026-05-16",
        "changes": [
            "✨【功能】多列联动排序：点击列头排序，点击同列升降序切换，多列追加排序（无上限）",
            "⚡【优化】移除ui_builder.py中order_no列标题重复定义",
            "🔧【修复】排序方法移入EventsMixIn类内部（修复AttributeError）"
        ]
    },
    {
        "version": "v36.16",
        "date": "2026-05-16",
        "features": [
            "多列联动排序：无上限，点击列头切换升/降序，支持多级排序"
        ],
        "fixes": [],
        "optimizations": [],
        "lessons": []
    },
    {
        "version": "v36.15",
        "date": "2026-05-16",
        "features": [],
        "fixes": [
            "标题栏版本号从写死v36改为动态读取version.json",
            "审核状态改为基于audit_result列判断",
            "审核来源改为从审核来源列读取",
            "偏差金额从audit_df映射解决为0问题",
            "调整列顺序：生产管理员→订单日期→流程订单→物料号"
        ],
        "optimizations": [],
        "lessons": []
    },
    {
        "version": "v36.14",
        "date": "2026-05-16",
        "features": [],
        "fixes": [
            "分析完成后自动删除生成的Excel文件，用户需手动点击生成Excel按钮"
        ],
        "optimizations": [],
        "lessons": []
    },
    {
        "version": "v36.13",
        "date": "2026-05-16",
        "features": [],
        "fixes": [
            "修复预检报告重复订单检测不兼容组件物料号列名",
            "修复_fill_table方法不存在导致表格更新崩溃",
            "修复表格列顺序错位（缺少audit_status和audit_source）",
            "修复_get_quarantine_path中变量d未定义",
            "修复树形视图列名硬编码不兼容当前数据列名",
            "新增流程订单列到表格显示"
        ],
        "optimizations": [],
        "lessons": []
    },
    {
        "version": "v36.12",
        "date": "2026-05-16",
        "features": [],
        "fixes": [
            "修复加载审核数据时订单列查找失败的问题（增加更多候选列名，处理列名不存在的情况）",
            "修复AI审核按钮无法使用（重写 _run_ai_audit 方法，修正未定义变量和循环逻辑）",
            "修复隔离区相关功能（统一隔离区辅助方法，避免重复定义）",
            "修复列宽锁定无效（绑定正确的事件处理函数）",
            "修复自动结案按钮无效（增加异常捕获和日志）",
            "修复隔离区弹窗列名显示英文（改为中文表头）",
            "修复预检报告弹窗（完整实现 _run_pre_check 生成 results 并调用弹窗）",
            "修复偏差金额合计为0（读取分析结果中的偏差金额列，若无则从单价计算）",
            "修复成本换算器（在审核卡片中正确显示）"
        ],
        "optimizations": [],
        "lessons": []
    },
    {
        "version": "v36.11",
        "date": "2026-05-14",
        "features": [
            '替代料配对区域新增"📄 查看配置"按钮，可查看 alt_pairs.json 内容（只读，可复制）',
            '底部按钮栏新增"📝 批量操作"按钮（随机码确认 + 批量处理）',
        ],
        "fixes": [
            'AI审核弹窗改为内嵌实现（不再依赖外部 show_result_window），修复弹窗不显示问题',
            '列宽锁定逻辑重写：改用 <<TreeviewColumnResized>> 事件绑定替代定时器轮询',
            '列宽锁定不再重置所有列宽（只阻止拖动），解锁后调整实时保存',
            '所有列统一设置 stretch=False，解决调整列宽时挤压其他列的问题',
            '修复 widgets.py 未被 PyInstaller 打包导致 exe 崩溃（添加 --paths + --hidden-import）',
            '审核来源不再被备注来源覆盖（优先读取 Excel 原始审核来源列）',
            'AI审核仅对当前审核行设置审核来源，不影响其他行',
        ],
        "optimizations": [
            'build.py 添加 --paths 和 --hidden-import widgets，确保项目根目录模块被正确打包',
            '列宽事件驱动替代定时器轮询，减少 CPU 占用',
            'build_log 详细格式：按前缀自动归类（新增/改进/修复/优化），含打包人/Python版本/文件大小/耗时',
        ],
        "lessons": [
            'Tkinter Treeview stretch=False 必须在所有 column() 调用中设置，否则调整一列会挤压其他列',
            'PyInstaller 以子目录脚本为入口时，需 --paths 显式指定项目根目录',
        ]
    },
    {
        "version": "v36.6",
        "date": "2026-05-13",
        "features": [],
        "fixes": [
            '审核来源不再被备注来源覆盖（优先读取 Excel 原始审核来源列）',
            'AI审核仅对当前审核行设置审核来源，不影响其他行',
        ],
        "optimizations": [],
        "lessons": []
    },
    {
        "version": "v36.5",
        "date": "2026-05-13",
        "features": [],
        "fixes": [
            '状态列与审核状态列彻底分离：状态=已备注/未备注（基于备注原因），审核状态=已审核/未审核（基于audit_result）',
            '状态筛选下拉选项改为"已备注"/"未备注"，正确过滤',
            'AI审核弹窗改为调用独立 show_result_window 函数，支持复制到剪贴板',
            '加载数据时自动设置状态列和审核状态列',
            'show_result_window 独立函数添加，显示5列（物料、偏差率、原备注、AI建议、审核结果）',
        ],
        "optimizations": [],
        "lessons": []
    },
    {
        "version": "v36.4",
        "date": "2026-05-13",
        "features": [],
        "fixes": [
            "AI审核重写：进度条、智能建议（广宣/包装/备件分类）、不覆盖原始备注、弹窗5列",
            "偏差金额正确计算并显示（原为0）：自动从金额-实际(含税)/数量-实际推算单价",
            '审核表格新增"审核状态"列（已审核/未审核）和"审核来源"列',
            '修正状态术语：审核状态基于 audit_result 判断',
            "删除 app.py 中两段孤立死代码",
            "偏差金额列移至偏差率之后，表格列顺序优化",
        ],
        "optimizations": [],
        "lessons": []
    },
    {
        "version": "v36.3",
        "date": "2026-05-13",
        "features": [],
        "fixes": [
            "修复 pandas 3.0.2 环境下 Lengths of operands do not match: 4 != 3 错误",
            "sheet8_reason_summary.py: agg lambda 返回值强制 str()/float() 包裹，防止非标量返回",
            "analyzer.py: .loc 列赋值右侧加 .values，避免索引不对齐",
            "sheet2_alt.py: alt_pairs 安全解包 + 类型校验，防止 tuple 泄漏到字符串比较",
            "sheet4_middle.py: alt_pairs 列表推导改用安全列表构建",
            "新增3对替代料配对（乐虎500ml、复配XD2139-5A、南侨玛琪琳），总数 17→20 对",
            "版本日志硬编码，消除 EXE 打包路径依赖",
            "审核按钮启用逻辑独立于数据加载，确保分析完成后始终可用",
            "审核按钮回调添加 try-except 错误弹窗，避免静默失败",
        ],
        "optimizations": [],
        "lessons": []
    },
]


# ── 公共函数 ──────────────────────────────────────────

def get_current_version():
    """返回当前版本号字符串，如 'v36.32.0'"""
    if VERSION_HISTORY:
        return VERSION_HISTORY[0]["version"]
    return "v0.0.0"


def get_version_display():
    """返回窗口标题用的完整显示名，如 '云南达利ZPP011生产偏差分析器_v36.32.0'"""
    return f"{APP_NAME}_{get_current_version()}"


def get_version_history_text():
    """
    返回格式化的版本日志文本，供"关于"窗口使用。
    每次调用都从 VERSION_HISTORY 实时生成，不缓存。
    """
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "📋 版本日志",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    for v in VERSION_HISTORY:
        lines.append(f"【{v['version']}】{v.get('date', '')}")

        # 新格式：features / fixes / optimizations / lessons
        for feat in v.get('features', []):
            lines.append(f"  ✦ {feat}")
        for fix in v.get('fixes', []):
            lines.append(f"  🔧 {fix}")
        for opt in v.get('optimizations', []):
            lines.append(f"  ⚡ {opt}")
        for les in v.get('lessons', []):
            lines.append(f"  📌 {les}")
        for note in v.get('notes', []):
            lines.append(f"  📌 {note}")

        # 旧格式兼容：changes 数组（根据前缀符号判断类型）
        for change in v.get('changes', []):
            if '【新增】' in change or '✨' in change or '✦' in change:
                content = change.replace('✨', '').replace('✦', '').replace('【新增】', '').strip()
                lines.append(f"  ✦ {content}")
            elif '【修复】' in change or '🔧' in change:
                content = change.replace('🔧', '').replace('【修复】', '').strip()
                lines.append(f"  🔧 {content}")
            elif '【优化】' in change or '⚡' in change:
                content = change.replace('⚡', '').replace('【优化】', '').strip()
                lines.append(f"  ⚡ {content}")
            elif '📌' in change or '【教训】' in change:
                content = change.replace('📌', '').replace('【教训】', '').strip()
                lines.append(f"  📌 {content}")
            else:
                lines.append(f"  🔧 {change}")

        lines.append("")

    return "\n".join(lines).strip()
