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
        "version": "v43.22",
        "date": "2026-08-28",
        "fixes": "主界面默认最大化最终修复：Win32 API ShowWindow(SW_MAXIMIZE)硬兜底，绕过Qt层所有resize/setGeometry覆盖（v43.19~v43.21四连败后采用操作系统级调用）"
    },
    {
        "version": "v43.21",
        "date": "2026-08-28",
        "fixes": "修复主界面默认最大化(v42.x起showMaximized偶发失效；改showEvent用showMaximized完整调用+启动脚本QTimer.singleShot(50)双保险，删除误用setWindowState干扰)"
    },
    {
        "version": "v43.20",
        "date": "2026-08-27",
        "fixes": "修复主界面默认最大化不生效(showEvent加QTimer.singleShot延迟一帧，绕过Windows窗口管理器覆盖)"
    },
    {
        "version": "v43.19",
        "fixes": [
            "修复主界面默认最大化不生效：__init__ 中的 setWindowState(WindowMaximized) 在 show() 前不被部分 Qt/平台应用，改为重写 showEvent 在窗口首次显示时强制最大化（每次打开默认最大化）",
        ],
    },
    {
        "version": "v43.18",
        "date": "2026-08-27",
        "features": [
            "负损看板新增'已读/未读'筛选下拉框（全部/已读/未读），与现有'半成品分类'筛选并列，由 _read 列(0/1)驱动",
        ],
        "fixes": [
            "放宽半成品重分类推断闸门：属半成品类判定从 物料分类=='半成品' 放宽为 物料分类=='半成品' 或 组件物料类型描述含'半成品'/'成品'，使 SAP 描述为'XX成品'(不含'半成品')的记录也能按工厂推断为 食品成品半成品/饮料成品半成品，主表与负损看板下拉框可筛选",
        ],
    },
    {
        "version": "v43.17",
        "date": "2026-08-26",
        "fixes": [
            "修复负损看板'隔离区'列漏标：candidates 白名单补传 data_id 列，隔离区列匹配兼容历史3段uid(订单日期|流程订单|物料编码)与4段uid(工厂|订单日期|流程订单|物料编码)",
        ],
        "notes": [
            "根因：负损看板无工厂列/data_id列，data_id 生成为3段，仅能命中隔离区10条3段历史记录，643条4段记录全部漏标(占比98%)",
        ],
    },
    {
        "version": "v43.16",
        "date": "2026-08-25",
        "fixes": [
            "偏差率预警看板：将「备注」列（具体原因文字，合并自备注原因）从白名单第20位前移到「物料描述」之后（第8位），打开看板一眼可见具体原因；同时保留「备注来源」列。",
        ],
    },
    {
        "version": "v43.14",
        "date": "2026-08-24",
        "fixes": [
            "侧边栏半成品列表优先从当前数据提取分类，支持显示动态推断的「食品成品半成品」「饮料成品半成品」等分类。",
        ],
    },
    {
        "version": "v43.13",
        "date": "2026-08-24",
        "fixes": [
            "空白半成品重分类列按工厂推断：半成品重分类为空 且 物料分类=半成品 且 工厂含'食品'→'食品成品半成品'，含'饮料'→'饮料成品半成品'。",
        ],
    },
    {
        "version": "v43.12",
        "date": "2026-08-24",
        "fixes": [
            "自动隔离类别支持多值OR匹配（逗号分隔）：category_value可填「食品综合组半成品,饮料综合组半成品仓」同时匹配多个类别；优先使用「半成品重分类」列进行精确匹配，其次回退到「物料分类」等通用列。",
        ],
    },
    {
        "version": "v43.10",
        "date": "2026-08-24",
        "fixes": [
            "修复负损看板物料描述列缺失崩溃：_name_cols改用条件列表推导，只在列存在时加入搜索范围，避免KeyError('物料描述')。",
        ],
    },
    {
        "version": "v43.09",
        "date": "2026-08-24",
        "fixes": [
            "主界面启动时默认最大化显示，无需手动拖动窗口。",
        ],
    },
    {
        "version": "v43.08",
        "date": "2026-08-24",
        "fixes": [
            "负损看板关键词搜索范围扩大：从仅搜索[物料名称/物料描述/组件物料描述]扩展到同时搜索物料编码、车间、备注、备注原因，便于通过更多维度快速定位负损记录。",
        ],
    },
    {
        "version": "v43.07",
        "date": "2026-08-24",
        "fixes": [
            "负损看板新增「半成品分类」下拉筛选器。",
        ],
    },
    {
        "version": "v43.06",
        "date": "2026-08-24",
        "fixes": [
            "偏差率预警看板/替代料看板新增「半成品重分类」下拉筛选器（与主表筛选面板一致，按具体分类值过滤）。",
        ],
    },
    {
        "version": "v43.05",
        "date": "2026-08-24",
        "fixes": [
            "修复替代料看板标记已读失败：删除错误的预建 data_id 索引（原索引基于看板数据行号，误用于主表操作）。",
        ],
    },
    {
        "version": "v43.04",
        "date": "2026-08-24",
        "fixes": [
            "修复半成品重分类列缺失问题：build_sheet5 现在正确从原始 df 复制半成品重分类列到 dev_df（主表才能显示）。",
        ],
    },
    {
        "version": "v43.03",
        "date": "2026-08-22",
        "fixes": [
            "半成品列表从QTreeWidget改为QTableWidget，模仿替代料配对样式（2列：工厂/分类，可排序）；左侧面板新增「重置筛选」「添加分类」按钮；修复初始化时列表为空的问题。",
            "清理 _filter_semi_materials 中 else: return 之后无法到达的死代码块（原 food_finish/drink_finish 硬编码分支）。",
        ],
    },
    {
        "version": "v43.02",
        "date": "2026-08-22",
        "fixes": [
            "将『材料半成品』筛选从写死4个按钮改为动态列表，支持运行时新增自定义分类；新增分类时弹框选列/条件/值，持久化到 config/semi_user_categories.json，下次启动自动加载。",
            "去掉半成品重分类.xlsx 的桌面路径查找（E:/Users/Administrator/Desktop/...），避免用户删除桌面文件后分析报错；保留打包资源目录和工程 config/ 两条路径。",
            "半成品重分类列默认宽度120px，确保主表可看。",
        ],
    },
    {
        "version": "v43.01",
        "date": "2026-08-22",
        "fixes": [
            "修复『材料半成品』筛选按钮点击崩溃：main_window._filter_semi_materials 误用不存在的 QTableView.selectRows(rows)，改为用 QItemSelection + mapFromSource 将源 DataFrame 行号正确映射到 proxy 行后批量选中，避免排序/过滤后选错行。",
        ],
    },
    {
        "version": "v43.00",
        "date": "2026-08-21",
        "fixes": [
            "新增『材料半成品』分类功能：左侧面板新增筛选按钮（食品原料/成品、饮料成品半成品），根据半成品重分类表（组件物料类型描述含'半成品'）按工厂名称区分食品/饮料，按编码列表区分原料/成品；分析阶段新增_is_semi_raw/_is_semi_finish标志列并同步到主表。",
        ],
    },
    {
        "version": "v42.99",
        "date": "2026-08-21",
        "fixes": [
            "移除主表『物料大类』列，改用原始『组件物料类型』+『组件物料类型描述』两列直接展示（食品半成品子类不再被合并为原材料）；Sheet8(偏差原因分析)同步升级：groupby 改为按 工厂+车间+组件物料类型+组件物料类型描述+组件物料描述+备注原因 五维度拆分，明细更细，并移除『涉及物料数』/『涉及物料』冗余列，新增『占车间偏差比%』列。",
        ],
    },
    {
        "version": "v42.98",
        "date": "2026-08-21",
        "fixes": [
            "主表新增『组件物料类型』『组件物料类型描述』两列：原物料分类列由组件物料类型+描述经np.select推导得出（Z002/Z009→包材，Z004→原材料，含'半成品'→半成品），无法区分食品半成品子类；现保留原始两列并插入到物料大类之后，便于筛选和明细查看。",
        ],
    },
    {
        "version": "v42.97",
        "date": "2026-08-21",
        "fixes": [
            "修复标记已读功能失效+性能问题：alert_dialog 和 deviation_warning_dialog 的 set_data() 均优先使用含工厂的 4 段 data_id（与主表一致）；预建 data_id 索引字典，批量标记时从 O(N²) 优化到 O(N)，解决大数据量下界面卡死问题。",
        ],
    },
    {
        "version": "v42.96",
        "date": "2026-08-21",
        "fixes": [
            "修复替代料看板『标记已读/未读』功能失效：alert_dialog.set_data() 生成 data_id 时漏掉『工厂』前缀，导致与主表 4 段格式(工厂|订单日期|流程订单|物料编码)不匹配，_sync_main_df() 永久匹配失败，标记操作只更新 dialog 内部而主表状态永不变。改为优先检查『工厂』列存在性，有则生成 4 段 data_id，无则回退 3 段(向后兼容)。",
        ],
    },
    {
        "version": "v42.95",
        "date": "2026-08-18",
        "fixes": [
            "替代料看板新增『颜色标记筛选』(复用主表逻辑)：把 AuditProxyModel.filterAcceptsRow 的颜色分类判定抽成模块级函数 classify_row_color_keys(row_data, df, threshold)，主表与看板零分叉、结果完全一致。看板顶部新增与主表对齐的6色复选框(审核后变更/隔离区/替代料/未投料/偏差率预警/无标记)+『清空颜色』按钮；_show_alert_dashboard 透传 _post_audit_changed/_quarantined/是否替代料 三列辅助数据(表格内隐藏，导出时剔除)。颜色筛选与已读状态为 AND：先按全部/未读/已读筛，再按勾选颜色 OR 过滤，与主表行底色严格对应。",
        ],
    },
    {
        "version": "v42.94",
        "date": "2026-08-18",
        "fixes": [
            "主表新增『产量』『产量单位』两列：build_sheet5 原构建列表漏列，已补到『产品物料描述』之后；data_service._reorder_columns 兜底再保证顺序。变动提醒扩展至产量：read_status 表新增 snapshot_yield 产量基线列，_restore_read_status 在重新导入时比对已审核记录的『实际数量/备注原因/产量』三者，任一被改动即回退未读+红标+deviation_history 留痕+弹变动提醒；旧记录无产量基线时静默建基线不报警。mark_changes_as_read 快照升级为3元组(数量,备注,产量)；get_audit_changes 变动看板正确还原『产量』字段。",
        ],
    },
    {
        "version": "v42.93",
        "date": "2026-08-18",
        "fixes": [
            "修复 data_id 真回归(方案2)：_add_data_id_and_fingerprint 恢复『工厂』前缀，data_id 由3段(订单日期|流程订单|物料编码)升为4段(工厂|订单日期|流程订单|物料编码)，消除达利多工厂下『同订单+同物料跨厂』撞 key 导致已读/隔离标记串台的隐患。无『工厂』列的导出数据回退3段(向后兼容)。测试 test_preprocess_adds_data_id / test_preprocess_adds_data_id_no_factory 两 case 同步验证通过。趁隔离区库 audit.db 已重建(历史为空)窗口期落地，零历史 key 失效代价。",
        ],
    },
    {
        "version": "v42.92",
        "date": "2026-08-15",
        "fixes": [
            "失效复核扩展至手动隔离记录：scan_expired_quarantine 的『手动+非负损』分支原先不 append 结果（函数自然 return），导致手动移入隔离区的记录（如『似薯类未确』『不干胶』）永不进入失效复核列表。改为将该类记录主动列入失效复核，status=manual_needs_review、失效说明提示『手动隔离，无自动失效判据，请人工确认隔离理由是否仍成立』，标签页角标计数随之更新。负损类/自动规则类失效判定逻辑不变。",
        ],
    },
    {
        "version": "v42.91",
        "date": "2026-08-15",
        "fixes": [
            "修复隔离区『内存孤儿』：界面标记隔离(_quarantined==1)但 SQLite quarantine_records 库内缺失的行，重载数据后会因水合读不到库而消失、且永远进不了基于库的统计/失效复核。新增 _repair_quarantine_consistency() 扫描全表内存孤儿并补写库（原因标『自动修复:界面标记隔离但库内缺失』），隔离区对话框 Tab1 按钮栏新增『🔧 修复一致性』按钮一键修复并即时刷新列表，主表右键菜单新增『🔧 修复隔离区一致性』全局入口；MainWindow.closeEvent 关闭前 silent flush 自动补写，杜绝复发。",
        ],
    },
    {
        "version": "v42.90",
        "date": "2026-08-14",
        "fixes": [
            "消除控制台刷屏的 Qt 噪音警告『dataChanged() called with an invalid index range』：原 DataTableModel.setDataFrame() 末尾用 self.dataChanged.emit(QModelIndex(), QModelIndex())（无效索引）做全表刷新广播。改为新增自定义无参信号 dataRefreshed，setDataFrame 末尾改用 self.dataRefreshed.emit() 广播；mark_quarantine 的单行合法 dataChanged（self.index(pos,0)→last_col）保留用于隔离黄标刷新。main_window 的 _update_summary / _refresh_unread_popup / _update_mark_stats 与 enhanced_sort_proxy_model 的 _invalidate_alert_cache 均同时订阅 dataChanged 与 dataRefreshed（双订阅），确保全表刷新与单行隔离标记都能触发汇总重算与预警缓存失效，功能零退化；切换源模型时同步解绑 dataRefreshed。",
        ],
    },
    {
        "version": "v42.89",
        "date": "2026-08-14",
        "fixes": [
            "修复负损看板 / 偏差率看板双击表格崩溃（AttributeError: '...Dialog' object has no attribute 'on_double_click'）：与 v42.88 同一类缩进事故，neg_loss_dashboard_dialog.py 与 deviation_warning_dialog.py 的 _ask_quarantine_reason 同样被误写成 0 缩进模块级函数、插在类方法序列中间，导致类提前结束，其后方法（on_double_click / _set_quarantine / eventFilter / export_excel 等）被吸成嵌套函数。已将两处的 _ask_quarantine_reason 移到文件末尾恢复为模块级工具函数，NegLossDashboardDialog / DeviationWarningDialog 类方法全部回归，双击定位与隔离功能恢复正常",
        ],
    },
    {
        "version": "v42.88",
        "date": "2026-08-14",
        "fixes": [
            "修复 v42.87 启动即崩溃（AttributeError: 'MainWindow' object has no attribute '_open_rule_center'）：v42.87 新增的 _ask_quarantine_reason 被误写成 0 缩进模块级函数、插在 MainWindow 类方法序列中间，导致 Python 判定 MainWindow 类提前结束，其后 35 个方法（含规则中心入口 _open_rule_center、隔离区相关 _set_quarantine / _open_quarantine_dialog 等）被吸进 _ask_quarantine_reason 成为嵌套函数。已将 _ask_quarantine_reason 移到文件末尾恢复为模块级工具函数，MainWindow 类方法数从 103 恢复至 138，启动崩溃消失",
        ],
    },
    {
        "version": "v42.87",
        "date": "2026-08-14",
        "fixes": [
            "移入隔离区对话框（主表右键 / 偏差率看板 / 负损看板）改用自定义 QDialog，显式带【确定/取消】按钮，修复 QInputDialog 在本机渲染不出按钮导致无确认键的问题",
            "打包回退到单 exe（--onefile，输出 dist/），与 v42.80-85 一致，桌面不再出现 _internal 依赖文件夹",
            ".gitignore 补 dist_run/；build 脚本打包前清空 dist 加 try/except，防旧 exe 仍运行导致 rmtree 崩溃",
        ],
    },
    {
        "version": "v42.86",
        "date": "2026-08-13",
        "optimizations": [
            "打包方式由 --onefile 改为 --onedir：不再把 210MB 压缩成单文件，依赖平铺在文件夹内，双击 exe 几乎秒开",
            "根治 onefile 每次启动需解压 210MB 到临时目录 + Windows Defender 实时扫描上千 DLL/pyd 导致的「打不开（无窗口期）/ 启动极慢」问题",
        ],
        "notes": [
            "功能与 v42.85 完全一致，仅打包形态变化：交付物为文件夹（含 exe + _internal + config），整体复制到目标位置后双击内部 exe 即可",
        ],
    },
    {
        "version": "v42.85",
        "date": "2026-08-13",
        "features": [
            "替代料配对支持「从主表选中 2 行智能添加」：自动提取工厂/编码/名称，弹窗核对（可交换 A/B）后写入",
            "入口：左侧「替代料配对」卡片新增「📌 从主表选中2行添加」按钮 + 主表右键菜单「➕ 添加为替代料配对（选中2行）」",
        ],
        "fixes": [
            "智能添加校验：选中行数≠2 / 物料号为空 / 两行物料号相同 时给出明确提示，避免误加",
        ],
    },
    {
        "version": "v42.84",
        "date": "2026-08-13",
        "features": [],
        "fixes": [
            "v42.83 再修正：自动隔离/已读规则配置 exe 模式默认写 E:\\zpp011_v2\\config（本机固定目录，不与 exe 同目录），未设置 ZPP011_PROJECT_ROOT 时不再报错，直接双击 exe 即可持久化，无需 .bat / 手动环境变量",
        ],
        "optimizations": [],
        "notes": [
            "ZPP011_PROJECT_ROOT 仍可覆盖默认路径；源码模式仍用项目内 config/，与 exe 共享同一份配置。v42.83 的一键启动 .bat 已不再需要",
        ],
    },
    {
        "version": "v42.83",
        "date": "2026-08-13",
        "features": [],
        "fixes": [
            "v42.82 修正：自动隔离/已读规则配置在 exe 模式下【只】持久化到 ZPP011_PROJECT_ROOT 指向的 config 目录（如 E:\\zpp011_v2\\config），移除「回退 exe 同目录 config/」分支；未设置该环境变量时直接报明确错误，不再把规则写到 exe 旁边",
        ],
        "optimizations": [],
        "notes": [
            "用户要求规则配置不要和 exe 同目录。故 exe 模式运行前必须设置 ZPP011_PROJECT_ROOT=E:\\zpp011_v2\\config（建议用一键启动 .bat 或系统环境变量）；源码模式仍用项目内 config/，与 exe 共享同一份配置",
        ],
    },
    {
        "version": "v42.82",
        "date": "2026-08-13",
        "features": [],
        "fixes": [
            "修复自动隔离规则 / 自动已读规则删除后重启又恢复：旧版 exe 模式下 _resolve_config_path 把配置写进 PyInstaller 临时解压目录 _MEIPASS（退出即删），导致删除不持久",
        ],
        "optimizations": [],
        "notes": [
            "core/auto_quarantine.py 与 core/auto_read_rules.py 的 _resolve_config_path 改为 exe 模式持久化路径：优先 ZPP011_PROJECT_ROOT 直接指向的 config 目录（如 E:\\zpp011_v2\\config，与源码配置同处），其次 exe 同目录 config/；新增 _bundle_config_path 只读兜底，load 在持久化文件缺失时回退打包内置默认，保证首次启动仍有默认规则；_MEIPASS 不再作为写入目标",
            "要用 ZPP011_PROJECT_ROOT 持久化，启动 exe 前须设置环境变量 ZPP011_PROJECT_ROOT=E:\\zpp011_v2\\config（否则回退 exe 同目录 config/）；删除规则后仍需在规则中心点「保存全部」才落盘",
        ],
    },
    {
        "version": "v42.81",
        "date": "2026-08-13",
        "features": [
            "隔离区列表 Tab 右键菜单新增「✎ 修改隔离原因（选中行）」：弹框可编辑，仅写 quarantine_records.reason 字段（不动 reason_basis/时间戳），同步内存 full_df 后重渲染；避开全局只读模型，不触发已读变更基线",
        ],
        "fixes": [],
        "optimizations": [],
        "notes": [
            "修改隔离原因走 core.quarantine_manager.update_quarantine_reason（UPDATE reason WHERE uid），与 add_quarantine 的 INSERT OR REPLACE 解耦；多行批量修改时以首个非空原因为预填值",
        ],
    },
    {
        "version": "v42.80",
        "date": "2026-08-12",
        "features": [
            "新增「负损看板」（独立弹窗，主窗口工具栏 🟠 负损看板 按钮打开）：按「物料名称含 彩罐/托盘/手包袋（可编辑）」+「负损（实际<定额，含未投料实际=0）」筛选主表记录，优先展示「备注原因」列，支持右键/按钮手动加进隔离区",
        ],
        "fixes": [],
        "optimizations": [
            "P0-4 net_offset.py 净偏差写回由逐行 df.at 改为 df.loc 批量向量化（12K 行触发写循环 0.646s→0.259s，约 2.5×）",
        ],
        "notes": [
            "隔离区搜索框功能正常：搜索关键字用的子串模糊匹配，若隔离原因里写的是「第三条」则搜「第3」搜不到，属数据写法差异，非代码问题",
        ],
    },
    {
        "version": "v42.79",
        "date": "2026-08-12",
        "features": [
            "偏差率预警看板料别筛选新增「半成品」按钮（物料类型/物料分类含「半成品」即命中）",
            "偏差率预警看板、隔离区列表均新增「是否备注」筛选（全部/有/无），与各自既有筛选叠加生效",
            "自动读取规则「物料编码前缀」支持逗号分隔多选（OR 命中，如 400、410）",
            "自动隔离区规则条件扩充：偏差率范围、物料编码前缀、车间、是否备注、偏差数量范围、名称不含",
        ],
        "fixes": [],
        "optimizations": [],
        "notes": [
            "自动隔离区规则编辑器改为滚动区域承载 6 项新条件，便于后续扩展",
        ],
    },
    {
        "version": "v42.78",
        "date": "2026-08-11",
        "features": [
            "偏差率预警看板列表新增「单位」列（件/kg/个等），导出与跨列搜索自动带上",
        ],
        "fixes": [
            "修复偏差率看板「移入隔离区」整表重置导致的视图跳变：改用 mark_quarantine 就地更新 _quarantined 列（仅发单行 dataChanged），加完第1条后滚动位置/列排序/选中行/筛选全部保留，第2条仍在原处可见",
        ],
        "optimizations": [],
        "notes": [
            "data_frame_model 新增 mark_quarantine(ids, flag) 就地更新方法，供主表与偏差率看板共用，避免整表 setDataFrame 重置视图",
        ],
    },
    {
        "version": "v42.77",
        "date": "2026-08-11",
        "features": [],
        "fixes": [
            "修复偏差率预警看板右键「移入隔离区」未实时同步主表 source_model，导致隔离区对话框须重新分析才显示的延迟问题（现加完立即在主表/隔离区/统计卡实时反映）",
        ],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.76",
        "date": "2026-08-11",
        "features": [
            "主表「物料属性」组新增「隔离区」三态筛选（全部/是/否），与「替代料」并列",
            "隔离区列表新增跨列关键字搜索框（防抖 300ms），与「隔离原因」列筛选叠加生效",
            "偏差率预警看板新增跨列关键字搜索框（防抖 300ms），与现有分类筛选叠加生效",
            "流程订单筛选支持逗号分隔多选（OR）",
            "主表默认隐藏内部列 data_id / fingerprint / _quarantined，不再暴露给用户",
        ],
        "fixes": [
            "修复隔离区右键「设为已读并移出隔离区」未定义 main_df 导致 NameError 崩溃",
            "隔离区失效恢复通知由显示原始 data_id 改为显示物料编码+物料名称",
        ],
        "optimizations": [],
        "notes": [
            "顺手清理 quarantine_dialog 两个未使用 import（remove_quarantine / save_read_status）",
        ],
    },
    {
        "version": "v42.75",
        "date": "2026-08-11",
        "features": [
            "AI审核改用 WorkBuddy 配置的 agnes-2.5-flash（原写死的 agnes-2.0-flash + .com 域名已失效，key 与环境变量一致）",
        ],
        "fixes": [
            "管理看板点击「未响应」卡死：看板 HTML 生成由 GUI 主线程同步出图改为后台线程（_DashboardBuildWorker + Agg 后端），界面不再冻结",
        ],
        "optimizations": [],
        "notes": [
            "废弃并删除无效的可视化规则配置（UI/存储正常但渲染管道从未接通，配了无效）；同步移除菜单项、隐式导入与专属 rules.json",
        ],
    },
    {
        "version": "v42.74",
        "date": "2026-08-11",
        "features": [
            "偏差率预警看板新增跨看板提示列：隔离区（基于 get_quarantined_ids 实时查询）、替代料（复用主表现成「是否替代料」列）",
            "隔离区/替代料增加全部/是/否三态筛选按钮组（与料别筛选同级，可独立叠加）",
            "偏差率预警看板右键新增「移入隔离区 / 取消隔离区」，逻辑与主表完全一致（弹窗填原因、批量写库、同步主表与看板状态）",
        ],
        "fixes": [],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.73",
        "date": "2026-08-10",
        "features": [
            "偏差率预警看板新增「车间」筛选下拉框（与已读状态、料别三组筛选独立叠加，便于海量记录快速定位）",
            "偏差率预警看板新增「备注」列并直接显示在表格内（位于状态列之后、data_id 列之前），一眼可见替代/未用原因",
        ],
        "fixes": [
            "修复偏差率看板备注列被错误隐藏的问题，现正常可见",
        ],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.72",
        "date": "2026-08-10",
        "features": [],
        "fixes": [
            "修复 exe 启动崩溃：ssl/hmac 模块加载时 Windows DLL 未找到（0xc0000139）——build 脚本增加 --collect-all=cryptography 收集 OpenSSL DLL\n- scan_expired_quarantine 的 df_index.loc[uid] 加 KeyError 防护，防止主表 data_id 格式与隔离区 uid 不一致时崩退",
        ],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.71",
        "date": "2026-08-08",
        "features": [],
        "fixes": [
            "修复 exe 启动崩溃：_resolve_config_path 增加 sys._MEIPASS 路径探测（PyInstaller onefile 解压目录），兼容 config/ 打包进 exe 的情况，不再强制依赖 ZPP011_PROJECT_ROOT 环境变量\n- 打包改为默认打开控制台（--console），方便启动时查看报错和日志",
        ],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.70",
        "date": "2026-08-08",
        "features": [],
        "fixes": [
            "代码质量审查收尾（P1-3/P1-5）：\n- P1-3 硬编码路径：移除 r'E:\\zpp011_v2' 默认值，exe 模式下 ZPP011_PROJECT_ROOT 未设置时改为 raise RuntimeError 显式报错，避免静默使用错误路径\n- P1-5 CI 语法：.github/workflows/ci.yml 改用 shell: bash，消除 CMD 与 PowerShell 混用导致 CI pyflakes 检查失效",
        ],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.68",
        "date": "2026-08-08",
        "features": [],
        "fixes": [
            "修复 NameError: add_quarantine_batch 未定义——v42.66 将手动批量隔离改为 add_quarantine_batch() 时漏加顶层 import，仅 _auto_move_to_quarantine 内有局部 import，_set_quarantine 路径触发 NameError。已在模块顶部补回导入。",
        ],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.67",
        "date": "2026-08-08",
        "features": [],
        "fixes": [
            "代码质量审查修复（P1-1/P1-2/P1-4/P2-4）：\n- P1-1 静默异常处理：auto_read_rules.py / auto_quarantine.py / main_window.py 中 except Exception: pass 改为 logging.warning 输出失败原因，便于问题追溯\n- P1-2 原子配置写操作：save_auto_read_rules_config() 和 save_auto_quarantine_config() 改为写临时文件后 os.replace()，防止写入中途崩溃导致配置损坏\n- P1-4 批量 SQLite 写入：手动批量移入隔离区改走 add_quarantine_batch()，单事务 executemany，避免逐行 connect/commit/close 在大量记录时卡 UI",
            "代码质量审查续修（P2-3/P2-6）：\n- P2-3 性能优化：scan_expired_quarantine 改用 df.set_index() 建立 O(1) 索引，消除原 O(n*m) 全表扫描\n- P2-6 异常处理：save_read_status / save_read_status_batch / mark_read_batch 补充 try/except + logging.warning，与 save_snapshot 风格一致",
        ],
        "optimizations": [],
        "notes": [
            "core/auto_read_rules.py 删除未使用的 _RULE_FIELDS 常量（死代码清理）",
        ],
    },
    {
        "version": "v42.65",
        "date": "2026-08-08",
        "features": [],
        "fixes": [
            "失效复核搜索框漏配数字列：原代码仅对 object 列（文本）做 str.contains 模糊匹配，偏差数量/数量-实际 等数值列被跳过，搜索数字关键字无命中。改为所有列统一 astype(str) 再匹配，输入「0.5」「100」等数字关键字即可命中。",
        ],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.64",
        "date": "2026-08-08",
        "features": [],
        "fixes": [
            "修复偏差率预警看板「原料」合计仍为 0 的二次回归：根因是 _mat_mask 过滤条件 vals == '原料' 与主表实际值 '原材料' 不匹配，改为 isin(('原材料', '原料')) 同时兼容两种命名。",
            "移除备注编辑功能：删除主表备注列双击编辑、右键菜单「编辑备注」等入口，备注改为只读展示（原功能已废弃且引发多处 NameError）。",
            "对齐根目录过期测试：清理 c77cd84 遗留的测试脚本引用。",
            "清理死代码 16 个文件：分析调试脚本（repro_*/analysis_time_check/_verify_analysis_time/marker_test）、旧版打包脚本（build_pyside6/build_ppt_excluded/run_build）、过期测试入口（test_main_window/test_script/run_tests）、已迁移模块（logger.py）、测试生成器（生成报告.py）。tests/ 目录保留，CI 仍跑 68 个 unit 测试。",
        ],
        "optimizations": [],
        "notes": [],
    },
    {
        "version": "v42.63",
        "date": "2026-08-07",
        "features": [
            "隔离区失效复核（Tab2）列调整：物料编码/物料名称/车间移到前面（一眼能看懂是哪条料），data_id 移到最后一列。",
            "隔离区 Tab1 隔离数据列表新增「序号」列（1,2,3…），筛选后自动重编。",
            "失效复核（Tab2）新增「关键字搜索」框，跨所有列模糊匹配（物料编码/名称/车间/原因/说明…），大小写不敏感。",
            "日期范围区新增「取消筛选」按钮：点击后筛选日期恢复为输入文件日期范围，并清除日期筛选条件、主表恢复全量。",
            "自动已读规则条件新增「偏差率」6 个类型（等于/范围/大于/小于/大于等于/小于等于），保护小单位物料（如总量0.9g只投0.09g、偏差率90%不误判自动已读）。",
            "替代料配对：添加时工厂/编码/名称自动 strip 空字符（清理首尾半角/全角空格、Tab）；放大窗口右键菜单新增「修改此配对」（复用编辑框、预填当前值、写回后刷新）。",
        ],
        "fixes": [
            "失效说明「盘盈」改为「多耗用」：实际>定额是多用料（如纸箱破损补投），与会计盘盈概念相反，共改 4 处（quarantine_manager 源头 + 对话框 hint + 版本日志两处）。",
            "修复自动隔离/已读规则关键词仅按逗号拆分、顿号「、」被当成整体关键词导致匹配失败的 bug：拆分前补 replace(\"、\", \",\")。",
            "修复「取消筛选」按钮：初版只清主表未同步日期控件；随后修正回填判断（>= 改接输入文件日期范围），现与源数据最早/最晚日期对齐。",
        ],
        "optimizations": [],
        "notes": [
            "auto_quarantine_config.json 中规则2的关键词已由「胚、盖」纠正为 [\"胚\",\"盖\"]（顿号拆分 bug 的存量配置修复）。",
            "偏差率条件数值按百分比（填 10 = 10%），与偏差率预警看板阈值口径一致；保护小单位需在「偏差数量 0~10」规则内「添加条件」加「偏差率小于等于 10」，组成双条件 AND。",
        ],
    },
    {
        "version": "v42.62",
        "date": "2026-08-07",
        "build_datetime": "2026-08-07 09:10:00",
        "features": [],
        "fixes": [
            "修复偏差率预警看板「原料」合计恒为 0、统计不到的 bug：根因是 infer_material_type 把「原料」写死为编码 30 开头，但真实 ZPP011 数据里原料是 10 开头（SAP 原辅料）、根本没有 30 开头编码，导致主表「物料类型」列把 10 开头的真·原料全错归为「其他」，看板用 ==\"原料\" 精确匹配恒落空（包材 20 开头正常）。",
            "修正 infer_material_type 映射与 SAP 一致：10→原料、20→包材、40/41→半成品、60→广宣、其余→其他；一处改全局一致（看板料别筛选 + 主表「物料类型」列 + dashboard「物料类型偏差金额占比」饼图）。",
        ],
        "optimizations": [],
        "notes": [
            "⚠️ 改的是 analyzer，需重新点一次「分析」刷新主表，看板与 dashboard 饼图才会显示正确的原料数（旧内存主表不会自动变）。",
        ],
    },
    {
        "version": "v42.54",
        "date": "2026-08-06",
        "build_datetime": "2026-08-06 11:12:00",
        "features": [
            "失效复核（Tab2）列顺序调整：定额与实际互换位置，并新增「偏差数量」列（=实际-定额）。",
            "隔离区两个列表打开即默认排序：Tab1 隔离区列表按 data_id 升序，Tab2 失效复核按偏差数量降序（偏差大优先复核）。",
            "失效复核 Tab2 新增「✓ 设为已读并移出隔离区（选中行）」按钮，一键标记已读（建立变更检测基线）并移出隔离区。",
        ],
        "fixes": [
            "修复隔离区 Tab1（FilterHeader 自定义表头）列头点击排序失效：补发 sectionClicked 信号，保留筛选三角与列宽拖动。",
        ],
        "optimizations": [],
        "notes": [
            "打包带控制台（--debug），崩溃可见 traceback。",
        ],
    },
    {
        "version": "v42.53",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 09:30:00",
        "fixes": [
            "修复 dry_run_analyzer.py try 块缩进错误（lines 44-50 未正确缩进，导致 IndentationError）。",
            "修复 _ui_refactor_notes.py 两处中文引号语法错误（lines 30、41 的「」改为『』），避免 SyntaxError。",
        ],
        "notes": [
            "📌 本次为代码质量修复版，零功能变更。",
            "📌 今天密集迭代 6 个版本（v42.47→v42.52），均因同一需求（规则1豁免排除单位）反复调试导致；本版集中修复遗留的语法隐患。",
        ],
    },
    {
        "version": "v42.52",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 15:30:00",
        "features": [
            "自动已读规则中心新增「逐规则豁免排除单位」功能：全局开启「排除指定单位」后，默认单位命中清单的行不自动已读，但每条规则可单独勾选「本规则包含这些单位（不受上面的「排除单位」开关影响）」豁免，便于针对不同业务场景精细化管理。",
            "「偏差数量=0」规则默认豁免排除单位（与600规则一致），确保关键行不受单位排除逻辑干扰。",
        ],
        "fixes": [
            "修复规则1（偏差数量=0）在启用「排除指定单位」时也被拦截的误判：该规则默认豁免，与600规则保持一致。",
        ],
    },
    {
        "version": "v42.51",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 15:15:00",
        "features": [
            "自动已读规则1「偏差数量=0」默认豁免「排除单位」开关：勾选全局「排除指定单位」后，该规则仍正常生效，不受单位清单影响。",
            "与规则2「物料600开头」行为保持一致，600物料和偏差为0的记录均不受单位排除干扰。",
        ],
        "fixes": [],
    },
    {
        "version": "v42.49",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 15:10:00",
        "features": [
            "自动已读规则1「偏差数量=0」默认豁免「排除单位」开关：勾选全局「排除指定单位」后，该规则仍正常生效，不受单位清单影响。",
            "与规则2「物料600开头」行为保持一致，600物料和偏差为0的记录均不受单位排除干扰。",
        ],
        "fixes": [],
    },
    {
        "version": "v42.48",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 12:40:00",
        "features": [
            "替代料看板（实时替代料看板）新增「备注」「备注来源」列，并前移到物料信息之后（第5-6列），默认视图即可见，无需横向滚动。",
            "删除看板中恒为空的「备注原因」列（主表 dev_df 无此列，analyzer 已将原数据「备注原因」内容并入「备注」列），避免误导。",
            "自动弹窗（AlertMonitor 触发）与手动打开（菜单）两条路径的看板均同步生效。",
        ],
        "fixes": [
            "修复替代料看板「备注看不到」的问题：原备注列排在最后（第13-14列），被窄窗口挤出可视区；现前移并移除空列后可直接查看料控备注与系统备注来源。",
        ],
    },
    {
        "version": "v42.47",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 11:30:00",
        "features": [
            "「系统无定额」自动备注规则重构：统一前置条件为 产量>0 & 定额=0 & 实际>0 & 无备注，精准排除「投了料但没填产量→SAP不推送定额(显示0)」的假象（如4车间投料未填产量被误判系统无定额）。",
            "广宣自动备注由「物料号6开头」收窄为「600开头」，并统一受上述产量/实际条件约束。",
            "透明胶带自动备注保留，同样受 产量>0 & 定额=0 & 实际>0 & 无备注 约束。",
            "删除原「全部包材+定额0」宽泛自动备注规则：200开头包材不再自动填备注，回到与原数据一致的无备注状态。",
        ],
        "fixes": [
            "修复系统自动生成的「系统无定额」备注来源被错误标记为「人工填写」的误导问题：gx 分支标「系统无定额(广宣)」、tape 分支标「自动填充」，一眼可区分系统生成 vs 人工填写。",
            "复现案例：ZPP011_20260801-20260804.xlsx 第346行(20000947)原数据无备注，旧逻辑误填「系统无定额」且来源标「人工填写」；现因产量=0 不满足新条件，正确保持无备注、来源「无」。",
        ],
    },
    {
        "version": "v42.46",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 10:00:00",
        "features": [
            "侧边栏筛选面板新增「单位」多选筛选：复选框列表动态列出数据中出现的全部单位（如 G、个、KG），勾选即只显示被勾单位（OR 关系），全不勾=不限制。配套「清空单位」按钮一键复位。",
            "单位复选框在刷新/重灌数据时保留已勾选项，不会因数据更新而丢失选择。",
        ],
    },
    {
        "version": "v42.45",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 09:30:00",
        "features": [
            "自动已读新增全局开关「排除指定单位（留给我重点看）」：开启后单位命中清单（如 G、个）的行默认不自动已读，便于重点审计。清单逗号分隔，中英文逗号均可、忽略大小写。",
            "每条规则新增「包含这些单位（豁免排除）」勾选项：勾选后不受上面的全局单位排除开关影响；600 开头物料默认即带此豁免（最高优先级，永远直接自动已读），不受单位排除波及。",
        ],
        "fixes": [
            "修复自动已读规则对话框「保存」漏存「排除单位」开关与单位清单的问题（此前设置了单位排除点保存会白存），现已正确持久化。",
            "加载已有配置时，自动为 600 开头物料规则补上单位排除豁免，确保历史 config 下 600 仍恒自动已读。",
        ],
    },
    {
        "version": "v42.44",
        "date": "2026-08-05",
        "build_datetime": "2026-08-05 09:30:00",
        "features": [
            "隔离区「失效复核」页（Tab2）支持点击列头排序（与列表页一致）。",
            "偏差率预警看板、实时替代料看板支持点击列头排序（此前 setSortingEnabled 在本项目 PySide6/Qt6 下失效、点列头不排序，已改为显式连接修复）。",
            "抽公共模块 gui_pyside6/utils/table_sort.py（HeaderSortController），统一所有 QTableView+DataFrameModel 的「点列头排序」：两态升↔降切换 + 自管排序箭头 + 筛选/重渲染后恢复排序态，规避 Qt6 失效连接。隔离区列表页原内联 handler 已重构复用该公共函数。",
        ],
        "fixes": [
            "隔离区列表页列头排序在筛选/刷新后保留（应用原因筛选后自动恢复之前的排序列与方向）。",
            "偏差预警/替代料看板在应用已读筛选后保留列头排序态。",
        ],
    },
    {
        "version": "v42.43",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 16:45:00",
        "fixes": [
            "新增「物料名称不含」条件类型（精确针对物料名称列，支持逗号分隔多值 OR：填「箱,彩罐」即名称且不含其中任一才命中），用于自动已读规则排除特定物料。",
        ],
    },
    {
        "version": "v42.42",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 14:20:00",
        "fixes": [
            "修复 exe 模式下自动已读规则/隔离区配置不持久化：配置路径改用项目真实 config 目录（E:\\zpp011_v2\\config\\），与源码配置同处，不再写进临时解压目录或 dist，重启后规则不再丢失。",
        ],
    },
    {
        "version": "v42.41",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 13:10:00",
        "features": [
            "自动已读规则新增「实际数量」条件类型（等于/大于/大于等于/小于/小于等于），可直接写「实际数量>0」来排除未投料的行。",
            "自动已读新增全局开关「排除未投料（实际数量=0）」：开启后默认挡掉所有实际=0 的行，避免替代料/非耗用被自动已读掉而漏审计。",
            "每条规则新增「包含未投料（豁免排除）」勾选项：勾选后不受上面的全局排除开关影响；默认 600 规则已勾选豁免，符合「600投不投料都无所谓」的诉求。",
        ],
        "fixes": [
            "规则中心对话框同步支持以上开关与豁免勾的读写（载入/保存均与 config/auto_read_rules.json 一致）。",
        ],
    },
    {
        "version": "v42.40",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 12:45:00",
        "features": [
            "主表格新增「已读来源」列（紧邻「状态」列之后），显示 自动 / 手动 / —，一眼区分某行当初是自动已读还是手动已读。",
            "筛选面板新增「已读来源」下拉（全部/自动/手动），可只看被规则自动标已读的行，或只被人手动标已读的行。",
        ],
        "fixes": [
            "read_status 库新增 read_source 来源字段：自动已读写 auto、手动已读写 manual，历史已读无来源统一归为手动；手动标已读会覆盖旧来源（如数量改动翻回未读后手动确认→记 manual）。",
            "修复自动/手动已读回写来源不一致：_auto_read_by_rules 与 _sync_main_read_status 均正确写入主表 df._read_source 与数据库，来源真实可溯。",
        ],
    },
    {
        "version": "v42.39",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 11:35:00",
        "fixes": [
            "「物料名称包含」条件支持逗号分隔自动 OR：填「胶带,卷膜,白内袋」等价于名称包含其中任意一个，与「物料编码属于(in)」行为一致。预览文本同步显示顿号分隔列表。",
        ],
    },
    {
        "version": "v42.38",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 11:20:00",
        "fixes": [
            "自动已读规则升级为「多条件 AND」：每条规则内可添加多个条件，全部满足才命中（多条规则之间仍为 OR）。",
            "新增条件类型：偏差数量在范围(开区间 dev_qty_range)、偏差数量大于(dev_qty_gt)、小于(dev_qty_lt)、大于等于(dev_qty_gte)、小于等于(dev_qty_lte)，覆盖「偏差数量>0且<1」等区间与单边界需求。",
            "UI：规则编辑区改为可增删的条件行列表，每行=类型下拉+参数输入（range 显示双数字框），底部「添加条件」按钮；预览文本按「且」拼接。",
            "向后兼容：旧单条件配置（顶层 type/params）自动包成 conditions[0]，老规则继续生效；条件缺列时该条件判 False（保守）。",
        ],
    },
    {
        "version": "v42.37",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 10:50:00",
        "fixes": [
            "新增「隔离区失效复核」：监控隔离区旧数据的改动，把入区原因已失效的记录告诉你。",
            "场景：某行当初因「负损（实际<定额）」进入隔离区，后来补投使实际≥定额（相符/多耗用）或实际归零，其入区原因即已失效，但旧逻辑只增不删、会一直躺在隔离区。",
            "实现：隔离区表新增 reason_basis 列（入区判定依据快照）；scan_expired_quarantine 对每条仍存在于主表的隔离记录实时重判——负损类用实时实际/定额（相符/多耗用/归零细分），自动规则类重跑规则看是否还在命中集；手动非负损类无数据依据不翻标。",
            "告知方式：每次分析完成后静默扫描，仅当「新增」失效记录出现时才弹窗+隔离区按钮亮角标（如「⚠️ 隔离区 (3失效)」），不重复打扰；隔离区弹窗新增「失效复核」Tab + 「扫描失效」按钮，每行带「移出隔离区」一键按钮，默认不自动移出，只通知。",
        ],
    },
    {
        "version": "v42.36",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 09:52:00",
        "fixes": [
            "修复左侧栏「☰ 隐藏左侧栏」点击隐藏后再点显示无法恢复的问题。",
            "根因：_toggle_left_panel 仅调 setVisible 未同步 body_splitter 的 sizes，QSplitter 在面板隐藏后把其宽度让给表格区，再次显示时左栏宽度被压成 0，表现为「回不来」。",
            "修复：与 _toggle_filter_panel 同一模式——隐藏时把左栏宽度加到表格区，显示时 setSizes([360, …, 剩余]) 把约 360px 还给左栏，无头验证切换两轮 sizes 正确恢复为 [360, 0, …]。",
        ],
    },
    {
        "version": "v42.35",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 09:00:00",
        "fixes": [
            "新增状态栏常驻「分析时间」标签：显示最近一次分析的触发方式(自动/手动)与完成时刻(月-日 时:分:秒)。"
            "windowed exe 无控制台，自动读取/自动分析后用户无从知晓何时发生，现常驻显示解决盲区。",
            "区分触发方式：自动=文件夹监控自动读取后自动分析(_monitor_auto_loading=True)；手动=点「分析」按钮/F5。",
            "标签状态机：新文件加载→「🕒 分析：—」；分析进行中→「🕒 分析中…（自动/手动）」；"
            "分析完成→「🕒 分析：自动/手动 时间」；分析失败→「🕒 分析失败（自动/手动）时间」。",
            "与「📖 已读」标签并列于状态栏右侧，琥珀色加粗字+左边框，视觉区分。",
        ],
    },
    {
        "version": "v42.34",
        "date": "2026-08-04",
        "build_datetime": "2026-08-04 09:00:00",
        "fixes": [
            "修复文件夹监控自动加载误读非 SAP 导出文件：新增文件名白名单 _is_monitor_accepted_file",
            "只自动加载 ZPP011_YYYYMMDD[-YYYYMMDD].xlsx（导出范围，含 Excel 副本后缀 (1)）与 ZPP011_SAP_*.xlsx（SAP 自动拉取输出）",
            "排除测试产物（如 _verify_fallback.xlsx）、分析报告、临时锁文件（~$ 开头）；_seed_monitor_baseline 与 _scan_monitor_dir 两处扫描均经该白名单过滤",
        ],
        "title": "修复文件夹监控自动加载误读非 SAP 导出文件",
        "changes": [
            "监控自动加载文件名白名单：只接受 ZPP011_导出范围(SAP 手工导出) 与 ZPP011_SAP_*(SAP 自动拉取)，排除测试/报告/锁文件",
        ],
    },
    {
        "version": "v42.33",
        "date": "2026-08-03",
        "build_datetime": "2026-08-03 18:00:00",
        "fixes": [
            "🔗 修复「未读概览」与「变动提醒」看板数据不一致：未读概览按主表 _post_audit_changed==1 & _read==0 算到 N 条，而看板 get_audit_changes 额外二次重比对 DB 历史基线、在缺基线/重比对相等时把变动行归零，弹出「暂无变动」，导致两边对不上",
            "👁 变动提醒看板改为以主表 _post_audit_changed 列为唯一真相（与未读概览同源），不再二次重比对归零；旧值取自 DB 基线快照、新值取当前主表值，缺基线也照常列出该行。现「概览 N 条 = 看板 N 条」完全一致",
        ],
        "notes": [
            "根因：两个弹窗对「变动提醒未读」用了两套口径——概览宽松（纯 df 列）、看板严苛（额外查 DB 基线并重比对），边界情况下看板归零",
            "已实测排除 data_id 类型(int/str)查不到主键的嫌疑（SQLite 列亲和性会让 int 命中 str 主键），确认是口径不一致而非查询 bug",
        ],
    },
    {
        "version": "v42.32",
        "date": "2026-08-03",
        "build_datetime": "2026-08-03 17:30:00",
        "fixes": [
            "🚑 修复 --windowed（无控制台）exe 启动即崩溃：run_pyside6.py 顶层 faulthandler.enable() 在 sys.stderr 为 None 时抛 RuntimeError: sys.stderr is None。现检测到无控制台即把 sys.stderr/stdout 重定向到 zpp011_stderr.log 再启用 faulthandler，启动不再崩、崩溃堆栈可落盘",
            "🔧 global_exception_hook 错误文案由「已输出到控制台」改为「已输出到日志文件 zpp011_stderr.log」，与实际落盘位置一致",
        ],
        "notes": [
            "此崩溃为历史遗留（v42.30/v42.31 同一份启动文件均会崩），只是此前未真正双击 exe 运行；本次因要查看状态栏已读计数才首次暴露",
            "源码模式（有控制台）下 sys.stderr 不为 None，不触发重定向，行为不变",
        ],
    },
    {
        "version": "v42.31",
        "date": "2026-08-03",
        "build_datetime": "2026-08-03 17:30:00",
        "fixes": [
            "🐞 修复「变动提醒弹窗」（未读概览 / 分析后弹窗）手动标已读不计入状态栏：选中标记、全部标记两处补 self._on_manual_marked(n) 回调，现全部手动入口（右键 / 工具栏 / 预警弹窗 / 偏差预警弹窗 / 变动提醒弹窗）均正确累加手动计数",
            "👁 状态栏「📖 已读：自动 N / 手动 M」标签改醒目样式：加粗蓝字 + 左边框分隔，避免用户注意不到",
        ],
        "notes": [
            "此前 v42.30 仅右键/两弹窗回调了计数器，而用户最常用的「未读概览弹窗标已读」走 data_service.mark_changes_as_read 直连，漏接导致计数恒为 0/0，误以为功能没生效",
            "自动计数仍在 _auto_read_by_rules 成功后累加 _auto_read_count；每批新数据（_on_file_loaded）清零两计数器",
        ],
    },
    {
        "version": "v42.30",
        "date": "2026-08-03",
        "build_datetime": "2026-08-03 09:20:00",
        "fixes": [
            "📊 状态栏常驻「已读计数」标签：📖 已读：自动 N / 手动 M，每批数据清零",
            "手动已读累计覆盖全部入口：右键/工具栏（audit_controller.batch_mark_read 新增 manual_marked 信号）、预警弹窗、偏差预警弹窗，均回调主窗口 _on_manual_marked 累加",
            "自动已读在 _auto_read_by_rules 标记成功后累加 _auto_read_count；新文件加载（_on_file_loaded）清零两个计数器",
        ],
        "notes": [
            "计数口径为「本次数据中自动/手动累计标记已读的条数」，只加不减（标未读为取消动作，不扣减）；toast 错过也能随时回看状态栏",
            "_update_read_counter / _on_manual_marked 对标签已回收（RuntimeError）做容错，关窗时序下不崩",
        ],
    },
    {
        "version": "v42.29",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 17:50:00",
        "fixes": [
            "🔔 自动已读 toast 显示时间 3s → 6s（_auto_read_by_rules 内 4 处 toast 调用全部加 duration=6000），解决「自动已读闪一下没看清」的盲区",
            "📋 工具栏新增「📋 未读概览」按钮：分析后未读概览弹窗可能被数据/面板挡住，工具栏随时可重开。复用现有单例机制 + 新增 show_unread_summary(force=True) 入口，force=True 时全已读也弹（标题下显示「🎉 全清零啦」副标题，再有新未读自动隐藏）",
        ],
        "notes": [
            "UnreadSummaryPopup 新增 mark_all_clear / clear_all_clear 两个方法（默认 hidden 的 QLabel 副标题），数据变化时主窗口自动切换",
            "工具栏位置在「⚡ 进度」之后，符合「分析 → 概览/进度/未读」流程顺到底",
        ],
    },
    {
        "version": "v42.28",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 17:15:00",
        "fixes": [
            "🐞 修复打开「自动已读规则」页崩溃（AttributeError: 'AutoReadRuleWidget' object has no attribute '_param_input'）：__init__ 中 edit_name.setText / chk_rule_enabled.setChecked 会同步触发 textChanged/stateChanged → _refresh_summary → _read_param_value 提前访问尚未构建的参数控件。改为在 __init__ 早期先声明 self._param_input = None，并让 _read_param_value 对 None 返回该条件类型默认值",
        ],
        "notes": [
            "v42.27 的 exe 打开自动已读规则页必崩，本版为 v42.27 的必须补丁，建议直接覆盖",
        ],
    },
    {
        "version": "v42.27",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 17:10:00",
        "features": [
            "✨ 新增「规则中心」对话框（菜单 审核 ▸ ⚙ 规则中心（隔离/已读），工具栏「⚙ 规则」按钮也指向它）：用 Tab 区分两页——① 自动隔离区规则（复用原自动隔离配置）② 自动已读规则，底部「保存全部」一次写盘两者",
            "✨ 自动已读规则可视化配置：支持条件类型 偏差数量等于 / 物料编码前缀 / 物料编码属于集合 / 物料名称包含 / 物料类型等于；多规则 OR 并存、独立启停、增删改排序",
            "✨ 默认内置两条自动已读规则：① 偏差数量=0 ② 物料编码前缀 600（即用户要求的「物料编码前3位 600 开头自动已读」），首次运行自动生成 config/auto_read_rules.json",
        ],
        "fixes": [
            "🔧 解决「自动已读的数据没有告诉我」盲区：旧逻辑只弹一条不列明细的 toast。现按规则分行反馈，例如「✅ 自动已读 120 条｜「偏差数量=0」93｜「物料600开头」27」，状态栏同步保留 6 秒可回看；总开关关闭或单条规则停用均有对应提示",
            "🔧 把原自动隔离规则对话框的内部 UI/逻辑抽成 AutoQuarantineRuleWidget(QWidget)，供规则中心 Tab 嵌入复用，对话框改为薄壳包装，工具栏按钮行为不变",
        ],
        "optimizations": [],
        "notes": [
            "📌 自动已读判定：多条规则 OR；仅对未读行生效（已读行不重复打扰，数据变动会自动翻回未读）；列名用候选名依次探测，缺失则该规则整条不匹配（保守不误伤）",
            "📌 复用 core/auto_read_rules.py 镜像 core/auto_quarantine.py 的结构（load/save + compute_auto_read_mask + build_rule_summary），配置独立存放 config/auto_read_rules.json，实时读取无需重启",
            "📌 验证：py_compile + pyflakes 无 F821/F822；自动已读求值逻辑用真实代码跑通（600 前缀命中、偏差数量=0 命中、已读行跳过、总开关/单条规则停用、配置读写 round-trip 全通过）",
        ],
    },
    {
        "version": "v42.26",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 16:25:00",
        "features": [],
        "fixes": [
            "🔧 修复潜在必崩点：_on_ai_preprocess_error() 读取 self._ai_preprocess_worker，但该属性全项目从未赋值、__init__ 也未初始化 → 只要 AI 审核后预处理失败走进该降级分支就 AttributeError；已在 __init__ 补 self._ai_preprocess_worker = None（与 v42.22 的 AuditLogger.queue 同类型隐患，pyflakes 查不出实例属性）",
            "🔧 关窗收尾补齐三个后台线程：closeEvent 此前只处理 analysis / ai / alert_monitor / _cache_worker，遗漏 _full_report_worker（完整报告导出）、_ppt_worker（PPT 生成）、_file_worker（大文件后台读取）。导出/生成/读文件途中关窗，主窗口先析构而线程回调后触发，存在崩溃风险；现统一 quit + wait(3000) 收尾并置 None",
        ],
        "optimizations": [
            "⚡ closeEvent 收尾对支持协作式取消的 worker（含 request_cancel 的完整报告 worker）先置取消标志再等待，避免硬等满 3 秒才关窗",
            "🛡️ closeEvent 收尾包 try/except RuntimeError，兼容底层 C++ 对象已被 deleteLater 回收的情形，关窗不再有二次异常风险",
            "🧹 save_snapshot / save_snapshot_batch 不再 except Exception: pass 静默吞错，改为打印 [read_status] 前缀的失败原因（含 data_id / 记录条数 / 异常类型）；仍不向上抛出，不打断主流程。基线写失败会导致「偏差变动」判断失真，此前完全无痕迹可查",
        ],
        "notes": [
            "📌 本版处理 AI 代码质量审查报告「第二批」问题，全部经真实代码逐条核实后才修（报告把 _full_report_worker 与 _ppt_worker 混为一谈，实际两者创建位置与生命周期不同）",
            "📌 验证：py_compile 通过；pyflakes 无 F821/F822；异常留痕与 closeEvent 收尾块均以真实源码 exec 方式做了运行时验证（含「运行中可取消 / 未运行 / C++ 对象已回收」三种 worker 状态），全部通过",
            "📌 改动集中在 gui_pyside6/main_window.py（__init__ + closeEvent）与 core/read_status.py（两处异常处理），不触碰任何分析算法与报表逻辑",
        ],
    },
    {
        "version": "v42.25",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 14:55:00",
        "features": [],
        "fixes": [],
        "optimizations": [
            "🧹 修复 ws6「异常预警」sheet 头部阈值说明硬编码：note_c 单元格原为写死字符串 '阈值说明：主表明细±10%（业务口径）...'，未跟随 UI 动态阈值；改为 f-string 跟随 dyn_thresh（±{dyn_thresh:.0f}%），UI 设 20% 时显示 ±20%、默认 10% 显示 ±10%",
        ],
        "notes": [
            "📌 这是 v42.22 dyn_thresh 贯穿修复遗留的一处漏网硬编码（用户反馈「分析说明阈值没改」时排查发现，当时 UI 默认值=10% 故未暴露）",
            "📌 仅改 analysis/analyzer.py 第 883 行 1 行字符串，零侵入业务逻辑",
            "📌 验证：py_compile 通过；pyflakes 无 F821/F822；dyn_thresh=20/10 两路径 ws6 头部实测分别显示 ±20%/±10%",
        ],
    },
    {
        "version": "v42.24",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 14:30:00",
        "features": [],
        "fixes": [
            "🔧 修复 v42.22/42.23 崩溃回归：分析完成回调 _on_analysis_finished_ui 启动后台缓存线程 _FullCacheWorker 时传入 dyn_thresh= 关键字，但该局部类的 __init__ 未声明该形参 → TypeError: unexpected keyword argument 'dyn_thresh'（每次点「分析」后必炸）。给 __init__ 补 dyn_thresh=None 形参并 self.dyn_thresh=dyn_thresh，调用处与兜底分支均能正确接收",
        ],
        "optimizations": [],
        "notes": [
            "📌 根因：v42.22 加 dyn_thresh 贯穿时漏改这个局部类（_FullReportWorker 已加、_FullCacheWorker 漏加）",
            "📌 主表分析本身不受影响，仅分析完成后的缓存线程异步启动时才炸；缓存正常路径复用 LATEST_INTERMEDIATES，Sheet3/4 阈值天然跟随 UI 设置（±20% 实测正确），仅极罕见兜底分支才显式传 dyn_thresh",
            "📌 验证：py_compile 通过；pyflakes 无 F821/F822；do_analysis_v2 三路径（主表 dyn_thresh=20 / 缓存复用中间结果 / 兜底 None）均不崩且阈值正确",
        ],
    },
    {
        "version": "v42.23",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 14:10:00",
        "features": [],
        "fixes": [],
        "optimizations": [
            "⚡ 取消（cancel）谨慎化：analysis_controller.cancel / audit_controller.cancel_ai_audit 的等待超时由 3000ms 提高到 5000ms，给后台 worker 在自身检查点（AnalysisWorker 的 cancel_check、AIAuditWorker 的 _cancel 轮询、_save_audit_results 前判 _cancel）优雅退出的机会——正常取消不再走到 terminate() 强杀线程，消除正在读 Excel / 写 SQLite 时被硬杀留下文件半截或锁残留的风险；terminate() 仍保留作最后兜底（真卡死才用），兜底后 wait() 确保线程真正结束。仅改 2 行 wait 阈值，零侵入 worker 内部逻辑",
        ],
        "notes": [
            "📌 属代码质量审查报告「第二批」里唯一有真实风险项的稳健化（其余 closeEvent 补 worker、save_snapshot 不吞错暂未做）",
            "📌 范围为用户确认的「只做 terminate 谨慎化」，未扩大改动面",
        ],
    },
    {
        "version": "v42.22",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 10:30:00",
        "features": [
            "✦ 动态阈值 UI 可调：筛选面板新增「动态阈值」输入框（0~50%，默认10%），贯穿 分析→主表→完整报告 Sheet3/4 数据及说明文字，sheet 描述里的阈值数值不再写死 ±10%",
        ],
        "fixes": [
            "🔧 修复 AuditLogger 后台线程启动即崩：__init__ 从未初始化 self.queue（queue.Queue），_worker 线程 self.queue.get() 直接 AttributeError、log() 同样崩；现补上 self.queue = queue.Queue(maxsize=max_queue_size)（仅被单测实例化，属潜伏缺陷，连自带单测都会挂）",
            "🔧 修复自动已读 mark_read_batch 主线程逐行 SQLite 写入（零偏差行多时界面冻结）：改为两条 executemany 批量化（INSERT OR IGNORE + UPDATE 各一批，单事务一次 commit），与 save_snapshot_batch 同款写法",
            "🔧 Sheet8「偏差原因汇总」备注完整输出——经复现已确认当前源码不截断，本次无代码改动，仅澄清旧版报表的截断现象",
        ],
        "optimizations": [],
        "notes": [
            "📌 合并上一轮未提交的 dyn_thresh 8 文件改动一并发版",
            "📌 代码质量审查报告（AI 生成）经逐条核对，其中 2 处 P1（AIAuditWorker 缩进、_get_conn 重复迁移）为误报，未采纳",
        ],
    },
    {
        "version": "v42.21",
        "date": "2026-08-02",
        "build_datetime": "2026-08-02 09:10:00",
        "features": [
            "✦ 分析完成自动已读：偏差数量=0 的行自动标记为已读（与手动标已读同一套变更检测基线，数量/备注真变了会自动翻回未读）",
            "✦ 自动已读完成后弹轻提示 + 状态栏同步：自动已读 N 条（偏差数量=0）｜食品 X/饮料 Y｜原料 A/包材 B｜其他 C（食品饮料按工厂列分词，原料包材按物料类型列）",
            "✦ 每次分析（含重新分析）都刷新主表（原为仅首次分析刷新，重分析后主表显示陈旧数据的坑一并修复）",
        ],
        "fixes": [
            "🔧 修复设「分析起始日/截止日」筛选后分析崩溃：订单级替代料布尔 mask 用 pd.Series(zip(...)) 默认带 RangeIndex，与日期切片后的非连续 df 索引错位，pandas 3.0.2 把 mask 当标签对齐抛 TypeError: unhashable type: 'Series'（@502 行）；构造时加 index=df.index 对齐",
            "🔧 修复日期区间筛出 0 条达阈值行时 build_sheet5 返回裸 pd.DataFrame([])（零列），后续取 dev_df['流程订单'] 抛 KeyError（@534 行）；空结果现返回带完整列结构的空表，兜底分支先判列",
            "🔧 顺带修复 _FullCacheWorker 后台重跑仍走完整分析，与正式分析结果一致",
        ],
        "optimizations": [],
        "notes": [
            "📌 打包采用 --debug（带控制台），崩溃时可直接查看 traceback",
            "📌 文件本身不缺列，崩溃纯属代码对筛选后非连续索引适配不足 + 空结果缺列；用户原数据 ZPP011_20260701-20260731.xlsx 经裸跑验证正常",
        ],
    },
    {
        "version": "v42.20",
        "date": "2026-08-01",
        "build_datetime": "2026-08-01 18:00:00",
        "features": [
            "✦ 导出「文件被占用」友好提示：新增 save_guard 防护模块，原始 PermissionError 翻译成中文，弹窗三选（我已关闭重试 / 存为副本 / 取消），已接 9 个导出入口（主表当前表/完整报告/隔离区/预警弹窗/偏差率看板/看板HTML/批量导出/PPT）",
            "✦ 主表右键批量导出与工具栏「导出当前表格」均改为导出筛选后显示的数据（遍历 proxy 可见行，所见即所得）",
            "✦ 偏差率预警看板新增「原料/包材」第二组筛选（与全部/未读/已读 叠加，各按钮实时显示点选后可得条数；无物料类型列时整组自动隐藏）",
            "✦ 偏差率预警看板导出改为当前筛选+排序后结果（默认文件名带筛选描述如 偏差率预警_未读_包材.xlsx，空结果拦截不生成空文件）",
            "✦ 未读概览弹窗三修：4 类未读计数与对应看板物理一致（统一 _get_master_df 单一数据源）、标记已读实时刷新、定位修正不再下溢出挡住第二行与关闭按钮、去掉盲关定时器、未清零自动挂起",
        ],
        "fixes": [
            "🔧 修复 df.to_excel 经 xlsxwriter 抛 FileCreateError（包着 PermissionError）导致 except PermissionError 接不住、占用回退失效的真 bug（改为沿异常链判定权限类）",
            "🔧 修复未读概览弹窗未读计数与看板不一致（source_model 副本与 view_model.df 分叉，统一取数口径）",
            "🔧 修复未读弹窗点「查看」后定位异常（show 前 height=0 下溢出屏幕，改 adjustSize 后定位 + showEvent 二次定位）",
        ],
        "optimizations": [],
        "notes": [
            "📌 打包采用 --debug（带控制台），崩溃时可直接查看 traceback",
            "📌 涵盖自 v42.19 起的累积改动：未读弹窗修复、偏差率看板筛选与导出改造、主表/批量筛选后导出、文件占用友好提示",
        ],
    },
    {
        "version": "v42.19",
        "date": "2026-08-01",
        "build_datetime": "2026-08-01 15:10:00",
        "features": [
            "✓ 修复「变动提醒」看板为空 bug：看板数据源由易失的 last_audit_changes 列表改为从主表 _post_audit_changed==1 且未读 的行实时重算（与未读概览弹窗/标记统计共用同一真相），重新分析导致列表被清空后看板不再空白",
            "✓ 主表未读数据存在 ~/.zpp011_audit/audit.db，与清缓存(__pycache__)、打包、预设持久化(已迁用户级)均互不干扰",
        ],
    },
    {
        "version": "v42.18",
        "date": "2026-08-01",
        "build_datetime": "2026-08-01 11:00:00",
        "features": [
            "✦ 新增「未读概览」弹窗：分析/加载完成后自动弹出（非模态、20秒自关、不阻塞主线程），汇总展示 4 类未读数——隔离区 / 变动提醒 / 替代料 / 偏差率预警，每行可点「查看」直达对应看板",
            "✦ 未读口径统一用主表 _read 列（与各看板一致）：隔离区=_quarantined&未读；变动提醒=已改动且未读；替代料=是否替代料且未读；偏差率预警=|偏差率|>=10% 且排除未投料且未读。全部已读则不弹",
        ],
        "fixes": [],
        "optimizations": [],
        "notes": [
            "📌 取代此前被关闭的「变动提醒表格 / 替代料预警」重模态弹窗，新弹窗不阻塞主线程，规避卡顿",
            "📌 触发点：分析完成、工厂切换重载、替代料净偏差重算、隔离/规则配置重预处理后，均会弹出",
        ],
    },
    {
        "version": "v42.17",
        "date": "2026-08-01",
        "build_datetime": "2026-08-01 10:45:00",
        "features": [
            "✦ 物料名称预设存储改为用户级目录（~/.zpp011_audit/material_name_presets.json），exe 内新增/修改预设永久保存，与已读数据同源",
            "✦ 打包配置修复：将整个 config 目录（含根目录 json）纳入 exe，补全此前遗漏的 material_name_presets.json / auto_quarantine_config.json / column_widths.json 等运行时配置",
        ],
        "fixes": [],
        "optimizations": [],
        "notes": [
            "📌 首次运行自动将项目内 config/material_name_presets.json 迁移至用户目录，源码与 exe 共用同一份预设",
            "📌 打包采用 --debug（带控制台），崩溃时可直接查看 traceback",
        ],
    },
    {
        "version": "v42.16",
        "date": "2026-08-01",
        "build_datetime": "2026-08-01 09:00:00",
        "features": [
            "✦ 主表上方常驻标记统计：偏差预警(橙)/替代料(蓝)/未投料(灰) 当前可见条数，随筛选实时动态更新",
        ],
        "fixes": [],
        "optimizations": [],
        "notes": [
            "📌 补发版：v42.15 打包时尚未包含「主表标记统计」功能（提交 7196cc6 于 2026-07-31 18:48，晚于 v42.15 打包），本次将其纳入发布",
            "📌 打包采用 --debug（带控制台），崩溃时可直接查看 traceback",
        ],
    },
    {
        "version": "v42.15",
        "date": "2026-07-31",
        "build_datetime": "2026-07-31 17:00:00",
        "features": [
            "✦ 物料名称预设管理支持拖拽排序+序号显示（1./2./...），新增「全部物料」哨兵项（真正显示全部，不再按字面搜\"全部\"）",
            "✦ 主表格默认显示未读：分析完成 / 重置 / 初始加载均回未读视图",
            "✦ 偏差率预警看板列序调整为定额在前、实际在后（贴合用户习惯）",
            "✦ 隔离原因改为简短规则序号（自动规则[第N条]），释放可见列宽",
            "✦ 隔离区增强：右键切换已读/未读并同步主表、弹窗按隔离原因筛选、原因列位置优化",
            "✦ 变动提醒增强：弹窗进度条防假死、批量标记已读、多行选中(Ctrl/Shift)、大数据量性能优化",
            "✦ 监控文件夹自动加载：发现新 Excel 自动加载（稳定性判定 + 去重 + 重新导出识别）",
            "✦ 自动隔离规则可配置化（JSON + 规则面板）、支持多条规则 OR 并存与规则管理 UI",
            "✦ 替代料看板逻辑增强（组内净偏差差异/偏差率超阈值均进入）且默认未读",
            "✦ 净偏差口径 PPT（build_ppt_net）、智能PPT菜单、Sheet8/9 多耗少耗物料级合计与原因分析列",
            "✦ 物料名称筛选可编辑下拉（用户预设 / 自动灌入常见名）、颜色标记筛选多选 OR 语义",
            "✦ 分析进度面板 v31 风格（12 步骤图标行）+ 右侧全局滚动区 + 替代料配对放大窗口（分组/查找/排序）",
        ],
        "fixes": [
            "🔧 修复预警监控线程裸自旋抢 GIL（拖慢纯 Python 代码约 1000× 的性能元凶）",
            "🔧 根除控制台「快速编辑模式」冻结 + Windows 后台限流导致的卡顿",
            "🔧 修复分析完成后主线程长时间未响应（预处理挪后台线程 + 代理重过滤风暴根治）",
            "🔧 消除分析完成后主表空白（清理上一轮残留代理筛选条件）+ 修复 UnboundLocalError 启动崩溃",
            "🔧 批量 SQLite 写入 + _build_cache 向量化，12K 行下消除\"未响应\"",
            "🔧 修复三类 NameError 低级错（漏导入/漏初始化）+ 物料预设对话框 QListWidgetItem 导入缺失",
            "🔧 修复绿色预警行原生崩溃(segfault)、列头排序崩溃、主表三态排序接入",
            "🔧 修复净偏差率列永远为空、异常预警阈值口径、统计卡片点击直写 proxy 筛选残留",
            "🔧 修复多项 UI 崩溃/截断（筛选面板加宽、下拉长选项截断、弹窗按钮中文等）",
        ],
        "optimizations": [
            "⚡ 诊断打点全面清理 + 统一 debug_util 开关（ZPP011_DEBUG 环境变量，默认静默）",
            "⚡ 主表快速路径：return_dataframe 模式算完偏差明细即返回，跳过导出专用 Sheet 构建",
            "⚡ proxy 预警行判定改缓存 O(1)，消除全表扫描卡顿",
            "⚡ SQLite 连接单例 + map/fill 向量化 + 墙钟时间戳打点",
        ],
        "notes": [
            "📌 本版本补齐 v42.14（2026-07-10）至 v42.15（2026-07-31）累积改动，约 130 次提交合并归纳",
            "📌 工程护栏：引入 pyflakes 提交前静态检查，拦截\"用了没导入的名字\"类低级错",
            "📌 打包采用 --debug（带控制台），崩溃时可直接查看 traceback 定位问题",
        ]
    },
    {
        "version": "v42.14",
        "date": "2026-07-10",
        "build_datetime": "2026-07-10 00:00:00",
        "features": [
            "✦ 新增隔离区功能：疑难数据可一键移入隔离区暂存，主表行浅黄标「隔离区」",
            "✦ 隔离区采用引用模式（仅存 data_id，不存副本），主表数量被改后重新导入，隔离行自动同步，零额外同步代码",
            "✦ 顶部统计卡片新增「⚠️ 隔离区 (X)」卡，点击一键过滤隔离行",
            "✦ 新增隔离区弹窗（工具栏「⚠️ 隔离区」按钮打开），支持批量取消隔离/导出/双击定位",
            "✦ 右键菜单支持「移入隔离区 / 取消隔离」",
        ],
        "fixes": [
            "🔧 修复统计卡片点击失效隐患：原 _on_stats_card_clicked 重复定义导致「审核后变更」卡点击无效，已合并为统一实现并支持隔离区卡点击过滤",
        ],
        "optimizations": [],
        "notes": [
            "📌 隔离区与审核后变更检测共用卡片+过滤模式，数据持久化于 ~/.zpp011_audit/audit.db 的 quarantine_records 表",
        ]
    },
    {
        "version": "v42.13",
        "date": "2026-07-10",
        "build_datetime": "2026-07-10 00:00:00",
        "features": [
            "✦ 复活顶部统计卡片（AI通过率/未读/真异常/替代料），并新增「审核后变更(X)」卡片：点击一键过滤出被私自修改过的数据行",
        ],
        "fixes": [
            "🔧 修复审核后数据被私自修改却「蒙在鼓里」的漏洞：每次加载数据均比对已审核记录的指纹，若实际数量/偏差金额/率被改动，自动打回未读、表格行红标「审核后已变更」、写入 deviation_history 留痕（改前→改后），并弹出变动提醒",
        ],
        "optimizations": [],
        "notes": [
            "📌 数据流：重新导入Excel→重新分析 即触发检测，覆盖主诉实际数量500→550被私自改动场景",
        ]
    },
    {
        "version": "v42.12",
        "date": "2026-07-09",
        "build_datetime": "2026-07-09 15:43:00",
        "features": [
            "✦ 替代料看板改名：原「预警看板」全面更名为「替代料看板」（菜单项/窗口标题/README 统一）",
            "✦ 替代料看板逻辑增强：替代料组内存在偏差差异（净偏差数量≠0）或偏差率超阈值，均进入看板，不再被单行偏差率阈值挡在门外",
        ],
        "fixes": [
            "🔧 修复净偏差率(%)跨订单聚合错误（核心计算模块 net_offset.py，红线区经授权修改）：替代料组净偏差率原按物料组全局聚合，同一替代料对跨多订单时净偏差率被压成≈0%；改为按「订单+组」维度计算，组_20004361@300402336 由 0.01% 修正为 -8.12%",
        ],
        "optimizations": [],
        "notes": [
            "📌 本版本为替代料看板增强与净偏差率计算修复版",
            "📌 net_offset.py 属核心计算冻结区，本次修改经用户明确授权执行",
        ]
    },
    {
        "version": "v42.11",
        "date": "2026-06-28",
        "build_datetime": "2026-06-28 16:15:00",
        "features": [
            "✦ 打包前自动源码备份：build_pyside6.py 增加 281 个源文件自动 zip 备份（保留最近20份）",
            "✦ 暗色主题默认：程序启动默认暗色主题，减少手动切换",
            "✦ 审核统计桌面卡片 P3：4 张实时展示本批次核心指标（审核通过率/需关注/已读未读/备注填写率）的可视化卡片",
            "✦ 历史频率推荐 P2：AI 审核时自动附加同物料+同工厂+同车间的高频备注原因",
            "✦ 成本换算器增强：审核卡片内支持材料偏差列，统计卡片和 PPT 报告增加总偏差金额实物换算",
            "✦ PPT 报告 V3（17页模板）：新增偏差率/预警等级分布/风险等级页面，支持偏差金额A/B双列分析、物料来源追溯、AI归因摘要",
            "✨ 智能小结生成器：基于统计数据生成自然语言报告，一键复制，含免责声明",
            "✨ 批量操作增强：多历史记录导出为多 Sheet Excel",
            "✨ 管理看板增强：图表 PNG 导出（白底/高 DPI）+ 同比/环比（上月/去年同期）",
            "✨ 视图管理：保存/加载/删除/刷新自定义筛选视图",
            "✨ AI 归因分析：物料大类+车间双维度贡献度分析",
        ],
        "fixes": [
            "🔧 回退全屏模式控件可见性判断逻辑（导致按钮/快捷键全部失效），恢复原版",
            "🔧 修复全屏模式状态不一致：基于控件可见性判断代替按钮 checked 状态",
            "🔧 修复全屏合计行高度设置错误（移除 21 行限制，改用固定合计行高度）",
            "🔧 修复全屏水平滚动条不可见 + F11 与按钮状态不一致",
            "🔧 真异常卡片改为可点击，状态栏显示详情",
            "🔧 删除旧版 gui/ Tkinter 目录（35 个文件/13907 行死代码）",
            "🔧 打包前强制校验版本日志已填写，否则拒绝打包",
            "🔧 修复审核来源列被备注来源覆盖",
            "🔧 修复订单类型列显示错误（order_type_val 未被提取和插入）",
            "🔧 修复 PPT 生成 advanced_ppt_generator_v2.py 三处 KeyError",
            "🔧 修复侧边栏筛选失效（替代料列名探测+类型清洗）",
            "🔧 修复预检报告窗口假死（改为非模态）",
            "🔧 修复分析按钮锁泄漏（所有 return 路径释放锁）",
            "🔧 修复 UTF-8 编码问题导致中文乱码",
        ],
        "optimizations": [
            "⚡ 打包流程自动化：版本号验证 + 版本日志校验 + 源码备份 + 打包一步到位",
            "⚡ 暗色主题设为默认启动主题",
            "⚡ 列表头排序修复：补全 _COL_TO_DF 映射及排序方法，替代料筛选列名探测",
        ],
        "notes": [
            "📌 本版本为 v42.10 的综合增强补丁，整合了全屏修复、源码备份、审核卡片、PPT V3 等功能",
            "📌 源码备份路径：C:\\Users\\Administrator\\.zpp011_audit\\source_backups\\",
            "📌 历史频率推荐需 AI 审核完成后可用",
        ]
    },
    {
        "version": "v42.10",
        "date": "2026-06-23",
        "build_datetime": "2026-06-23 17:45:00",
        "features": [
            "✦ 亮色主题支持：完整双主题系统（dark/light QSS），可切换明暗风格",
            "✦ 选中行合计：鼠标选中表格行后，底部状态栏动态显示选中行的数值合计（金额/数量）",
            "✦ 全屏模式保留状态栏：切换到全屏时选中合计依然可见",
        ],
        "fixes": [
            "🔧 删除标题栏物料搜索栏（减少冗余UI）",
            "🔧 删除标题栏自定义窗口控制按钮（复用系统原生按钮，消除点击无反馈问题）",
            "🔧 修复左侧工具栏遮挡右侧筛选面板的颜色问题",
            "🔧 修复文件选择后文件名不显示问题：增加占位符显示和扩展策略",
            "🔧 修复原表行号显示错乱：统一使用 openpyxl 真实行号映射",
            "🔧 异常分析 Sheet6 增加「订单类型」「净偏差数量」「净偏差金额」三列（全链路：生成+导出一致）",
            "🔧 全选选中合计显示为0：修复数值类型转换和求和数据源问题",
        ],
        "optimizations": [
            "⚡ 主题系统从内联 setStyleSheet 迁移至外部 QSS 文件，~70 处硬编码样式统一收口到 dark_theme.qss / light_theme.qss",
            "⚡ 选择变更通过 selectionChanged 信号实时触发底部状态栏更新，无性能损耗",
        ],
        "notes": [
            "📌 本版本为 UI 优化与主题增强版，零核心功能变更",
            "📌 亮色主题切换：菜单栏 → 视图 → 切换主题（亮色/暗色）",
            "📌 选中行合计：按住 Ctrl 可多选行查看合计，按 Ctrl+A 全选也可查看",
        ]
    },
    {
        "version": "v42.8",
        "date": "2026-06-11",
        "build_datetime": "2026-06-11 22:45:00",
        "features": [
            "✦ Agnes AI 批量审核：一次 API 调用处理 15 条，大幅提速",
            "✦ 审核结果 SQLite 持久化：审核结果/AI建议/备注来源跨 session 记忆",
            "✦ 双击主表格弹出明细卡片（三组信息，全部可复制）",
            "✦ 主表格 Ctrl+C 复制选中区域（TSV 格式，可粘贴到 Excel）",
            "✦ 筛选面板新增：审核结果（合格/需关注/需改进/需补备注）、备注来源（AI审核/人工填写）"
        ],
        "fixes": [
            "🔧 修复审核结果列名中英文混乱导致重复列/数据丢失",
            "🔧 修复 _替代料组 与 替代料组 同时存在的空列问题",
            "🔧 修复明细卡片列名模糊匹配（空格/别名）",
            "🔧 修复 AI 审核进度卡在 0% 的问题",
            "🔧 修复批量 API 超时后逐条重试浪费时间（改为直接 Mock 降级）",
            "🔧 修复 config/constants.py 和 __init__.py 的 VERSION 引用残留",
            "🔧 修复 workers.py try/except 缩进丢失",
            "🔧 修复 _build_cache 重复索引导致 Series 判空崩溃"
        ],
        "optimizations": [
            "⚡ AI 审核两阶段：本地分类（瞬间）→ 批量 API（15条/批），1000条从50分钟→3分钟",
            "⚡ HTTP 超时单条 15s→5s、批量 45s→20s，API 不通快速降级",
            "⚡ 列清理流程前置到 preprocess_audit_data 开头，防重复蔓延",
            "⚡ 明细卡片 _mk_label 统一创建可选中文案标签",
            "⚡ filter_panel 审核状态→审核结果，选项匹配 AI 输出值"
        ],
        "notes": [
            "📌 v42.8 基于 v42.7，重点完善 AI 审核流程和列数据完整性",
            "📌 Agnes AI 国内网络可能不稳定，超时 5s 即降级 Mock，不影响基础功能",
            "📌 审核结果已持久化，重新分析后自动恢复历史审核数据"
        ]
    },
    {
        "version": "v42.7",
        "date": "2026-06-11",
        "build_datetime": "2026-06-11 21:00:00",
        "features": [
            "✦ Agnes AI 真模型接入：制造业偏差智能审核，自动生成可执行建议（免费，20 RPM）",
            "✦ AI 审核上下文增强：传递物料编码/描述/大类/车间/工厂/偏差金额等完整信息",
            "✦ 历史源码入口：菜单栏「历史 → 历史源码」打开源码备份目录",
            "✦ 打包前自动备份源码：zip 备份全部源码，保留最近 20 份",
            "✦ 已读/未读 SQLite 持久化（指纹比对 + 跨 session 记忆）",
            "✦ 预警看板右键菜单支持多选批量标记已读/未读",
            "✦ 预警看板标记已读后主表格实时同步刷新"
        ],
        "fixes": [
            "🔧 修复已读状态不持久化：DataService 类未导入/未实例化，预处理管线完全失效",
            "🔧 修复 data_id 含工厂前缀与 DB 不匹配，统一为「订单日期|流程订单|物料编码」",
            "🔧 修复 export_controller.py 多层 try/except 语法错误（重复块 + 缩进）",
            "🔧 修复主表格右键批量标记 data_id KeyError（缺少列时动态生成）",
            "🔧 修复 QMenu/QAction/QMessageBox 等类未导入 main_window.py",
            "🔧 修复 SQLite is_read 列 numpy int64 存为 blob 导致读取失败",
            "🔧 修复预警看板 _sync_main_df 修改后未刷新主表视图"
        ],
        "optimizations": [
            "⚡ 版本号统一到 utils/version_history.py（get_current_version），消除 5 处硬编码",
            "⚡ ConfigManager tkinter API 加守卫：PySide6 环境静默跳过防崩",
            "⚡ 所有控制器 except 块增加 traceback.print_exc()，异常堆栈完整输出",
            "⚡ save_read_status 类型加固 int()/str() 强转，防止 blob 存储",
            "⚡ 删除 config/constants.py 僵尸 VERSION=\"v36\""
        ],
        "notes": [
            "📌 本版本修复了 v42.0→v42.7 迁移期间累积的所有语法和持久化崩漏",
            "📌 源码备份需执行 build_pyside6_exe.py 打包时自动触发",
            "📌 版本号以后只需改 version_history.py 一处，所有界面自动跟随"
        ]
    },
    {
        "version": "v41.3",
        "date": "2026-06-03",
        "build_datetime": "2026-06-03 23:05:00",
        "features": [],
        "fixes": [
            "🐛 修复 audit_batch_events.py 缩进错误导致批量操作无法使用",
            "🐛 修复表格列顺序错乱（补充「备注来源」列）",
            "🐛 修复 export_events.py 缺少 with_feedback 导入",
            "🐛 修复 ppt_generator 依赖 matplotlib 缺失导致程序启动失败",
            "🐛 修复 analyzer.py 文件名日期截断问题（结束日期缺少年份）",
            "🐛 修复 analysis_events.py 列映射时覆盖已有列",
            "🐛 重写 AI 审核规则，增加 5%≤偏差率<10%「需关注」分级，优化关键词与字数优先级",
            "🐛 修复 AI 审核范围过窄（AI 审核过的短备注可重新审核）",
            "🐛 修复排序与筛选冲突（_apply_sort_and_refresh 优先使用 filtered_data）"
        ],
        "optimizations": [
            "⚡ 优化 matplotlib 导入方式，未安装时仅影响 PPT 生成功能"
        ],
        "notes": [
            "📌 本版本为 v41.3 紧急修复版，解决了多个稳定性问题",
            "📌 重写 AI 审核规则后需重新运行 AI 审核以获得更准确结果",
            "📌 建议所有用户升级至此版本"
        ]
    },
    {
        "version": "v41.2",
        "date": "2026-06-03",
        "build_datetime": "2026-06-03 14:50:00",
        "features": [
            "✨ PPT报告V3（17页模板结构）：新增偏差率/预警等级分布/风险等级页面，支持偏差金额A/B双列分析，物料来源追溯，AI归因摘要",
            "✨ 效益报告（8页完整版）：执行摘要、车间排行、物料排行、趋势分析、成本换算、改进建议、附录",
            "✨ 规则配置界面：帮助菜单新增入口，RuleConfigDialog 支持正则匹配、优先级、颜色定制"
        ],
        "fixes": [
            "🐛 GBK编码兜底：MessageBox 全量参数 `_safe_for_gbk` 包装，错误消息去除emoji/非GBK字符",
            "🐛 Worker线程 `sys.stdout.flush` OSError崩溃（加try/except防护）",
            "🐛 PPT生成 `line[0].isdigit()` 空字符串IndexError（4处，改为 `line and line[0].isdigit()`）",
            "🐛 偏差率/偏差金额字符串无法格式化（加 `pd.to_numeric(..., errors='coerce')`）"
        ],
        "optimizations": [
            "⚡ `_safe_for_gbk` 工具函数：strip非GBK字符 + encode('gbk','replace') 双重保险",
            "⚡ 临时文件清理延后到程序退出时执行，减少运行干扰"
        ],
        "notes": [
            "📌 PPT V3 修复 line[0].isdigit() 空字符串风险（line 672, 800, 979, 1022）",
            "📌 规则配置支持正则表达式、优先级排序、颜色标记（红/黄/绿）",
            "📌 本版本基于v41.0合并后的稳定版"
        ]
    },

    
    {
        "version": "v41.0",
        "date": "2026-06-01",
        "build_datetime": "2026-06-01 21:00:00",
        "features": [
            "✨ 可视化规则配置界面（图形化编辑备注校验规则，支持多条件组合、测试、原子保存）",
            "✨ 效益报告（一键生成PPT，包含执行摘要、车间排行、物料排行、趋势分析、成本换算、改进建议）",
            "✨ AI 归因分析增强（增加物料大类贡献度、偏差方向分解、审核进度等维度）",
            "✨ 合计行按单位汇总弹窗（解决不同单位数量无法合并的问题）"
        ],
        "fixes": [
            "🐛 管理看板下钻修复（点击物料大类柱状图自动筛选主表格）",
            "🐛 AI 归因分析无内容修复（兼容缺少物料大类列的情况）",
            "🐛 视图导入导出测试失败修复（完善返回值和方法签名）",
            "🐛 加载审核数据时临时文件提前删除导致报错修复"
        ],
        "optimizations": [
            "⚡ 成本换算器增强（审核卡片内支持材料偏差列，统计卡片和F6报告增加总偏差金额实物换算）",
            "⚡ 审核卡片中文化（字段显示中文，与黄金模板同步）",
            "⚡ 审核表格增加订单类型列，物料大类优先使用原表组件物料类型描述",
            "⚡ 历史菜单恢复（分析完成后显示）"
        ],
        "notes": [
            "📌 本版本基于 v40.2 补丁，新增多项核心功能，建议所有用户升级",
            "📌 可视化规则配置需注意表达式安全性，已采用 AST 解析 + 字段白名单",
            "📌 效益报告依赖 python-pptx 库，打包时已包含",
            "📌 归因分析需历史数据支持，至少两次分析记录才能显示对比"
        ]
    },

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
