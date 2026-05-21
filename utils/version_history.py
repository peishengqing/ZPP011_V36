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
