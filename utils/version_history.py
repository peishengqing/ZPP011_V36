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
        "version": "v43.282",
        "date": "2026-10-27",
        "fixes": "**清掉全部 13 个存量测试失败 + 2 个 teardown 错误（全量单测 228 passed 全绿）**。① v43.270「Phase 5」把筛选预设 7 个核心方法改走 FilterController 内存 store，引入两个真实回归：预设存 app_state._preset_store 重启即丢（旧走 config_manager.filter_history 落盘）；应用预设改 fc.apply_preset→app_state（_data 从未填充）→get_filtered_dataframe 返回 None→on_data_changed(None) 崩溃。7 个方法体回退到 v43.195 实现（git 考古 99ab5c6 原文件比对确认），修好 11+2 个测试；Phase 5 导入导出/复制方法保留仍走 fc store。② test_custom_header_sort teardown：setAttribute(2048) 裸 int 改 Qt.WA_DeleteOnClose 枚举（PySide6 6.x 要求），sendPostedEvents(None,4) 笔误改 QEvent.DeferredDelete(52)。③ 生产真 bug×2：filter_controller 导出预设 json.dump(ensure_only=) 参数不存在（应为 ensure_ascii，一处被 except 吞致导出永远失败、一处无 except 直接抛）。",
    },
    {
        "version": "v43.281",
        "date": "2026-10-27",
        "fixes": "**状态栏「已读：自动 N / 手动 M」常驻 0/0 不再计算**（用户 17:27 截图反馈）。根因：计数是「本次会话新标记增量」累加，从数据库恢复的历史已读（日志「恢复了 36 条审核结果」）永不计入，且自动已读命中 0 条时连刷新都不触发。修法：update_read_counter 改为对 view_model.df 实时统计（_read==1 按 _read_source 分桶，auto 归自动、其余归手动），并在分析完成 setDataFrame+view_model 赋值后固定刷一次；df 不可用时兜底回会话累加值。",
        "features": "**移除主表底部 5 个合计标签**（定额/实际/偏差金额/偏差量/净偏差率，用户 17:37 截图圈定「这些合计不要了」）：main_table 不再创建标签，update_summary 改空壳（信号链保留），选中行合计仅走状态栏提示，QSS #summaryLabel 规则清理。",
    },
    {
        "version": "v43.280",
        "date": "2026-10-27",
        "fixes": "**点击列头打开筛选浮层崩溃：'QWidget.__init__ called with wrong argument types: QWidget(ColumnController, WindowType)'**。根因：v43.193 ARC-003 第一刀把列筛选从 MainWindow 切出到 ColumnController 时，方法体内两处 `QWidget(self, Qt.Popup)` 的 self 从 MainWindow 变成了非 widget 的 controller——parent 参数必须是 QWidget，点「列筛选」浮层一开即抛 TypeError。修法：两处（_open_column_filter 主浮层 + _open_empty_column_filter_popup 兜底浮层）parent 改 self.mw。offscreen 验证：popup 构造成功且 parent() is mw。",
    },
    {
        "version": "v43.279",
        "date": "2026-10-27",
        "fixes": "**保存筛选预设报「保存上次使用失败: No module named 'pwd'」**（用户 17:15 截图反馈）。根因：`filter_controller.FilterPreset._get_user_hint` 用 `import pwd` 取 Unix 用户名——pwd 是 Unix 专有模块，Windows 上 import 即抛 ModuleNotFoundError，且发生在 try 之前，兜底的 `os.getenv('USERNAME')` 永远执行不到。修法：删 pwd 路径，改为 Windows 正确的环境变量链 USERNAME → USER → LOGNAME，兜底 'User'。验证：offscreen 实测 _get_user_hint() 返回 'Administrator'。",
    },
    {
        "version": "v43.278",
        "date": "2026-10-27",
        "fixes": "**点「显示筛选」连弹多个日历窗**（用户 16:49 截图反馈）。根因：v43.276 在 filter_panel.eventFilter 加的 `QEvent.ShowPopup` 兜底拦截（后改为 Show/ShowToParent），面板每次显示时 Qt 会对每个 QDateEdit 子控件派发 Show 事件 → 每个日期框各弹一个手画日历窗。而 v43.277 后全部日期字段都是 _make_date_field（setCalendarPopup(False) + 「选择」按钮直调 _popup_calendar），该兜底已无必要，整段删除。附带：修 ShowPopup AttributeError 启动崩溃（PySide6 6.x 枚举无此成员，eventFilter 一被调用即抛错）。",
        "features": "清理 QSS 告警：light/dark_theme.qss 删除 Qt 不支持的 box-shadow 属性（启动时刷 26 条 'Unknown property box-shadow'），焦点视觉反馈由 border-color 高亮承担。",
    },
    {
        "version": "v43.277",
        "date": "2026-10-27",
        "fixes": "**修复 v43.276 引入的启动崩溃（无限 eventFilter 嵌套）**。根因：`_install_table_copy_handler` 把 MainWindow 注册为*应用级* eventFilter，app 级 filter 收到全窗口事件，`filter_panel.eventFilter` 的 `QEvent.ShowPopup` 拦截在 delivery 期间触发窗口级 eventFilter 的再入调用，不断套壳 `Error calling Python override of QMainWindow::eventFilter()`，导致 `showMaximized()` 阶段抱错退出。修法：拆掉 `app.installEventFilter(self)`，只保留 `self.table_view.installEventFilter(self)`（控件级）；`_ctrl_down` 仍由该过滤器的 KeyPress/KeyRelease 事件流自行维护，`column_controller` 通过 getattr('mw', '_ctrl_down', False) 容错读取。`main_window.py` 第 2906-2914 行 `_install_table_copy_handler`。",
    },
    {
        "version": "v43.276",
        "date": "2026-10-27",
        "fixes": "**堵住 v43.275 遗漏的第二条 QCalendarWidget 弹窗入口**。用户 10:37 截图仍显示「...」，定位：`filter_panel.py:309/315` 的 `start_date_edit` / `end_date_edit` 是独立的 QDateEdit，`setCalendarPopup(True)` 直接触发 Qt 内置 QCalendarWidget 弹窗——绕开 v43.275 手画的 QTableWidget 日历。之前只改了 `_make_date_field` 生成的 analysis_start/end 日期字段，漏了「日期范围」分组里这一对。修法：把 start/end_date_edit 也改成用 `_make_date_field` 生成（`setCalendarPopup(False)` + 加「选择/清除」按钮），UI 与另一个日期字段组保持一致。同时补一个 eventFilter 拦截 `QEvent.ShowPopup` 作兜底（万一未来哪一天又加回 setCalendarPopup(True) 也不会漏）。验证：4 个 QDateEdit 全部 calPopup=False，4 个「选择」按钮全部弹 QTableWidget 而非 QCalendarWidget，7x7 表格日期 1-31 完整显示（含两位数 10-31）。",
    },
    {
        "version": "v43.275",
        "date": "2026-10-27",
        "fixes": "**彻底根治日期选择器日历弹窗日期数字显示为「...」的问题**（推翻 v43.273/v43.274 两条路径）。诊断证据：QStyledItemDelegate 内部对 option.rect 有二次省略号判定，即使手动 QPainter.drawText 也挡不住——只要 cell 宽 < QFontMetrics('30').width()=30px 就强制省略。QCalendarWidget 每列默认 ~30px 正好触发。正解：放弃 QCalendarWidget，用 QTableWidget 手画日历——(1) 7 列 × 7 行，第 0 行是「周一~周日」表头，(2) QHeaderView.Stretch 均分列宽彻底解决两位数被省略，(3) QTableWidgetItem 用 foreground 控制「相邻月灰色 / 今天红字加粗 / 选中蓝底白字」，(4) QTableWidgetItem.setData(Qt.UserRole, 'yyyyMMdd') 存真实日期，(5) 顶部 ◀ 年月 ▶ 前后月切换，底部「将选择：yyyy-MM-dd」预览 + 确定/取消，(6) 越界日期（小于 min 或大于 max）禁用点击，(7) Escape 取消、Enter 确定、Double-click 立即接受。验证：offscreen 结构数据 7x7 表格，日期 1-31 全部两位数完整显示。",
    },
    {
        "version": "v43.274",
        "date": "2026-10-27",
        "fixes": "**彻底修复日期选择器日历弹窗日期数字显示为「...」的问题**（推翻 v43.273 的 QSS 方案）。诊断证据：QCalendarWidget 内部有独立的 QTableView + QStyledItemDelegate，外部 QSS 覆盖不到 delegate 层的省略号判定；`setDefaultSectionSize(42)` 被 QCalendarWidget 内部 layout 覆盖成 16px，导致两位数日期被 QStyledItemDelegate 自动省略成「...」。正解：(1) 用 `cal.findChild(QTableView)` 钻到内部表，(2) 装自定义 `QStyledItemDelegate` 强制每格 44×42 sizeHint + 手动 QPainter.draw 深字绕过默认省略号，(3) `dlg.show()` 后用 `verticalHeader().resizeSection(r, 42)` **逐行** 锁定行高（setDefaultSectionSize 被 QCalendarWidget 忽略，只有逐行 resizeSection 生效），(4) 隐藏 verticalHeader 让每个日期单元格横向腾出空间。修复后 offscreen 诊断：tv 实际 416×411（填满 dialog），每行 59px 高，两位数完整显示。附带：QDialog 底部增加「将选择：yyyy-MM-dd」预览标签，选择实时同步。",
    },
    {
        "version": "v43.273",
        "date": "2026-10-27",
        "fixes": "**修复日期选择器日历弹窗日期数字显示为「...」的问题**（用户 2026-10-27 09:21 截图反馈）。根因：`light_theme.qss:14` 有 `QMainWindow, QDialog, QWidget { background-color: #F3F3EE; ... }` 规则，`QWidget` 选择器会级联到 `QCalendarWidget` 内部所有子控件，把单元格底盖成米黄底；加之日历默认单元格高度只有 ~20px，日期数字被挤到只剩几个像素宽，看起来像三个点。修法：在 `_popup_calendar` 里给 dialog + calendar 加内联 QSS 覆盖（白底 + 深字 + 13px 字体），并强制 dialog 最小尺寸 360×400、calendar 最小尺寸 320×280，让每个单元格至少 40×36 保证数字完整显示。",
    },
    {
        "version": "v43.272",
        "date": "2026-10-27",
        "fixes": "**修复 FilterController.connect_filtersChanged 命名不一致 bug**（Phase 3 遗留隐患）：filter_controller.py:320 定义的是 snake_case `connect_filters_changed`，而 main_window.py:353 调用的是 camelCase `connect_filtersChanged`——Python 运行时才校验方法名，py_compile / pyflakes 均无法发现；此前被上游更早失败掩盖，一旦上游修复到该位置即触发 AttributeError。将方法名统一为 camelCase（与同类的 connect_filtersApplied / connect_filtersReset 保持一致），调用方 main_window.py 无需改动。",
    },
    {
        "version": "v43.271",
        "date": "2026-10-27",
        "features": "**筛选解释器（Phase 6）**：① 新增 FilterExplainerDialog，选中被排除行逐条解释为什么没显示（每条规则的 ✓/✗ + 实际值 vs 期望值）；② FilterController 新增 explain_rows / summarize_exclusions / _compute_rule_mask 三个方法；③ 筛选面板底部显示「已过滤 X 条 · 主要因: Y」实时摘要；④ 快捷键 Ctrl+Shift+E 直接打开解释器。",
    },
    {
        "version": "v43.270",
        "date": "2026-10-27",
        "features": "**Phase 5 收尾与集成**：① 新增 FilterPresetManagerDialog（管理对话框）；② 主窗口集成预设管理入口（Alt+M）；③ 添加快速切换快捷键 Ctrl+1~9；④ 显示预设使用次数、最后时间；⑤ 完整导出的 JSON 格式支持版本号和导出时间戳。",
    },
    {
        "version": "v43.269",
        "date": "2026-10-27",
        "features": "**Phase 5：筛选可视化与预设管理增强**：① FilterPreset 完善，新增预设使用 history 追踪、导入导出、快速切换功能；② 预设支持真 JSON 导出/ZIP 批导、单个预设文件导出；③ 新增 Clone、Duplicate、GetHistory 等高级管理方法；④ 预设存储使用 AppState 扩展（碾压本地 JSON）。",
    },
    {
        "version": "v43.268",
        "date": "2026-10-27",
        "fixes": "**Phase 4 动态级联筛选升级**（裴哥选「A 全做」）：① FilterPanel 新增级联规则定义与 `_apply_cascades()`，工厂/车间/物料类型间建立联动；② `set_data()`自动触发级联，车间下拉框先清空并重建，候选值基于当前工厂筛选；③ 级联后自动重新发射筛选信号，保证视图与筛选状态一致；④ 修复 `Store.set_cascade_filters()` 语法错误（`.py` 换行符异常），移除不影响功能的 `_to_date()` 无用方法；⑤ 升级版本号至 v43.268。",
        "features": "动态级联筛选：基于当前筛选条件动态计算并刷新相关下拉框选项，避免「死选项」。",
    },
    {
        "version": "v43.266",
        "date": "2026-10-26",
        "fixes": "**修掉「全仓 emoji → SVG」漏网的最后一批（裴哥 10-26 截图指正：主表底部工具条的三个按钮显示成怪字形——锁显示成黑白黄油漆桶、全屏显示成四点方阵、隐藏列显示成「i」）**。根因有两层：① v43.264 的「全仓图标化」只盘点了主窗口/看板/侧栏/统计卡这几处显眼界面，**漏了主表底部合计条与各看板对话框的操作按钮**；② 更要命的是这些按钮的文本是**纯符号**（`QPushButton(\"🔒\")`），emoji 撑满 32px 按钮时 Microsoft YaHei 字体回退把它渲染成了毫不相干的字形——这不是「不够好看」，是「看不懂是什么按钮」。**改法**：① `utils/icons.py` 补 23 个新图标（maximize/minimize/eye/unlock/clock/timer/book/scroll/gear/exchange/sparkles/chevron-down/up/left/right/check-circle/close-circle/paperclip/folder-open/undo/menu/tag/flag，图标集 37 → 60 个）并新增 **`EMOJI_TO_ICON` 映射 + `split_emoji()` / `make_button()` / `make_tool_button()` / `add_icon_action()` 四个工厂**——工厂自动剥掉文本里的 emoji 前缀并挂对应 SVG 图标，调用方一行不改语义；② 用迁移脚本把 **67 处按钮/菜单项**（15 个文件）切到工厂：主窗口右键菜单 6 项、隔离区/负损/正损/半成品/偏差率预警看板的「标记为已读/未读/移入隔离区/导出 Excel/放大/修复一致性/扫描失效」等按钮、规则编辑器与自动已读规则对话框的增删按钮、归藏「AI 重新设计」、微信草稿配置 6 个按钮、菜单栏「⚙ 规则中心 / 🔔 替代料看板」；③ **状态栏/进度条/通知文字的 emoji 前缀去掉**（状态栏三件套「分析/已读/列头筛选」、计时器「⏱ 00:00」、进度「✅ 完成 / ❌ 错误 / 📦 缓存」、8 处 toast 通知、系统对话框标题）——这些是纯文本载体，装不了图标，去前缀后语义不变且不再有字体回退风险；④ **状态切换逻辑改图标而非改文字**：列宽锁按钮 `_toggle_column_lock` 原来 `setText(\"🔓\"/\"🔒\")` 会把 v43.264 刚加的图标洗回 emoji，改 `setIcon(get_icon(\"unlock\"/\"lock\"))`；工具栏「左侧栏/筛选/列头筛选」的显隐切换同理只改文字、保留图标；列头筛选提示改用 `col_filter_ui.set_col_filter_button_on` 统一口径。**保留不动**：折叠箭头的 ▼▶◀▲▾（几何符号，Windows 字体渲染正常）、步骤图标的 √（测试锁定）、版本日志正文的 ✦新功能/🔧修复/⚡优化 图例（内容语义标记）。**验证**：新增 emoji 扫描脚本（正则扫 QPushButton/QToolButton/QAction/QLabel/addAction 构造与 setText），全仓可见文本剩余 11 处均为上述保留项；离屏冒烟新增底部三按钮「图标有实际像素 + 文字无 emoji + 锁定态切图标 + 面板显隐切换后图标不被洗掉」共 10 项断言 ALL-PASS；pytest 307 passed / 1 skipped / 2 xfailed 零回归；pyflakes 与 HEAD 基线一致（仅 1 条因迁移而闲置的 QPushButton 导入，已清）。",
        "features": "「全仓 emoji → SVG 线性图标」在 v43.264 基础上补完最后一批：新增 4 个按钮/菜单工厂（make_button / make_tool_button / add_icon_action / split_emoji）与 EMOJI_TO_ICON 映射表（54 个图标），67 处按钮/菜单项 + 状态栏/通知文字全面去 emoji；图标集总量 37 → 60。",
    },
    {
        "version": "v43.265",
        "date": "2026-10-26",
        "fixes": "**修掉 v43.264 引入的两个显示回归（裴哥 10-26 截图指正：「看不清」「太窄了」）+ 一个更底层的图标空渲染 bug**。① **统计卡被压扁、数字被裁**：v43.264 把 7 张卡从单行 QHBoxLayout 改成 `QGridLayout` 4+3 **两行**，但卡片区位于 `top_panel`（限高 240px）内、垂直分割器初值只给 150px —— 两行卡片的布局最小高度（约 146px）+ 标题行超出了可用高度，Qt 按比例压扁子控件，22px 的卡片数字被压到十几像素、只剩半截（截图里每张卡只剩一条色带和半行数字）。修法：**改回单行 1×7 的 KPI 条**（7 张卡平铺等宽，只吃一行高度，实测统计卡区总高 96px）、数值/说明标签各加 `setMinimumHeight(28/16)` 兜底防再被压、卡片 `QSizePolicy.Expanding/Fixed`、顶部分割器初值 150→175 与 `top_panel` 限高 240→260 一并放宽。② **未读概览弹窗太窄**：宽度下限 360→**420**，行内边距 8/5→10/7、间距 6→10、计数标签定宽 84 右对齐（4 行数字上下对齐，不再随名称长度飘）、「查看」按钮 48→56px 且带最小高度 26（原先文字贴着边框）。顺带把该弹窗也完成图标化：标题 📋 → clipboard 图标、「🎉 全清零啦」→ check 图标、4 个分类图标 emoji → SVG（`main_window.py` 改传图标名，弹窗侧保留旧 emoji 兼容映射）。③ **根子上的图标空渲染 bug（v43.264 埋的）**：`utils/icons.py` 的 SVG 模板把 path 数据直接塞进 `<svg>` 里、**忘了包 `<path d=\"...\"/>` 元素**，结果 QSvgRenderer 渲染出的是**全透明图**——`QIcon` 本身非 null（所以「图标非空」断言全过），但屏幕上**一个图标都画不出来**（v43.264 截图里那些小方块就是空白图）。修法：模板补 `<path d=\"{paths}\"/>`；**验证手段同步升级**——离屏冒烟新增「像素级非空」断言（逐个图标渲染 24×24 统计 alpha>0 的像素数 ≥5，37/37 通过；此前只查 `QIcon.isNull()` 完全查不出这类空图）。**教训：GUI 图标类需求的验收必须看像素，不能只查对象非空。**",
        "features": "统计卡改单行 KPI 条（1×7 平铺）；未读概览弹窗加宽到 420px 并重排行内布局（计数列右对齐、按钮加大）；未读弹窗与主表状态列图标全部 SVG 化。",
    },
    {
        "version": "v43.264",
        "date": "2026-10-26",
        "features": "**GUI 结构现代化 Phase B（裴哥选「A 全做」）**：① **全仓 emoji 图标 → 内联 SVG 线性图标**——新建 `gui_pyside6/utils/icons.py`（37 个 24×24 stroke 线性图标，QSvgRenderer 渲染 + 2× 超采样，按 (名字,颜色,尺寸) 缓存），标题栏工厂标/主题日月、操作栏 8 平铺按钮 + 3 收纳菜单 12 项、侧栏 4 张卡片头 + 📌 按钮、统计卡标题、6 个看板对话框的列头筛选按钮全部换图标；按钮文本去掉 emoji 前缀（「📊 看板」→「看板」+ 图标），`test_toolbar_reorg.py` 同步对齐（菜单 3 项/平铺 8 键文本、看板 8/导出 2/维护 2 逐项断言），窗口最小宽度断言（≤1300）复测通过。② **标题栏去 Tkinter 化**：emoji 大图标改 SVG 工厂标（圆角方块承托，与主色呼应），主题按钮改「图标+文字」并保留 `set_theme_light/set_theme_dark` API 与 `theme_toggled` 信号，主副标题层级与版本号展示不变。③ **统计卡网格化 + 数字等宽**：7 张卡从单行 QHBoxLayout 改 QGridLayout（4+3 两行、等宽列、stretch 收尾），每卡顶部加 3px 品牌色 accent 条（此前 `_make_card` 的 color 参数**收了 7 个颜色却一个都没用上**，卡片完全无色觉编码），卡片数值与主表数值列统一等宽字体（Consolas，tabular figures，主表新增 `Qt.FontRole` 分支按数值类型判负，DisplayRole/TextAlignmentRole/ForegroundRole 行为零变化）。④ **表格密度收紧**：`#tableView::item` 垂直 padding 3px→2px（主表约 30 行一屏的观感收益）。⑤ **6 个看板对话框列头筛选条去重**：`alert/deviation_warning/neg_loss/pos_loss/quarantine/semi_dashboard` 各自重复的 7 行按钮构造 + 「🔽 列头筛选✓」状态文本逻辑（quarantine 有两个按钮共 4 处）收敛到新模块 `gui_pyside6/dialogs/col_filter_ui.py`（`make_col_filter_button` / `set_col_filter_button_on` / `make_col_filter_hint_label`），按钮改 funnel 图标 + 勾选态图标不变文字加「✓」的语义由样式承担。⑥ **顺手修 `dialogs/wechat_draft_config_dialog.py` 3 个既存 bug**（该对话框全仓无调用方、从未被触发过）：`:37` `QWidget` 未导入（F821，一开窗就 NameError）、`:221/:223` `clicked_connect` 拼写（AttributeError）、清 3 个未用 import。⑦ **主表第 0 列已读状态图标化 + 筛选键语义化**：✅/🔘 emoji → DecorationRole SVG 图标（已读=绿勾/未读=蓝环，DisplayRole 清空），`build_display_key_list` 第 0 列返回「已读/未读」语义键（弹层收集与 proxy 匹配同源一致）。验证：pytest 全量 307 passed / 1 skipped / 2 xfailed（零回归）+ pyflakes（零新增）+ 离屏冒烟 32 项全 PASS（图标全覆盖/网格 4 列/accent 7 条/隔离区对话框共用组件/模型 FontRole 与 DisplayRole 未回归/主题往返/QSS 解析告警 0 条/最小宽度 1194px ≤1300）+ 亮暗双主题截图。",
        "fixes": "同 entry features 内⑥：wechat_draft_config_dialog.py 的 QWidget F821 与 clicked_connect 拼写（死代码路径，修掉消除 pyflakes F821 与将来启用即崩的隐患）。**另修掉 v43.263 遗留的真 bug「统计卡样式从未生效」**：`stats_cards.py` 的数值/说明/标题标签用的是 `setProperty(\"class\", \"statsCardVal\")`（class 属性），而两套 QSS 里写的是 `#statsCardVal`（ID 选择器，只匹配 objectName）——**选择器与控件属性口径不一致，22px 加粗 Consolas 的卡片数字从来没渲染出来过**（离屏冒烟的字体检查抓到的：`widget.font()` 与 QSS 规则文本对不上）。修法为两套 QSS 三个选择器 ID→class（`#statsCardTitle/Val/Desc` → `.statsCardTitle/Val/Desc`），选择器集合仍逐条对齐。**主表第 0 列已读状态 emoji（✅/🔘）→ SVG 图标**（DecorationRole：已读=绿勾、未读=蓝环；DisplayRole 清空），列头筛选键同步改语义文本「已读/未读」——改在 `build_display_key_list` 最上游一处，弹层收集与 proxy 匹配两边天然一致（此前第 0 列返回 None 走逐行兜底，会退化成「(空)」单键）。",
    },
    {
        "version": "v43.263",
        "date": "2026-10-26",
        "fixes": "**修掉「没点分析就看看板 → 崩溃弹窗」的既有缺陷（ARC-003 拆分遗留）**：`controllers/dashboard_controller.py`（24 处）与 `controllers/semi_category_controller.py`（12 处）里所有 `QMessageBox.information/warning/critical/question(...)` 和 `QFileDialog.getOpenFileName/getSaveFileName(...)` 的第一个参数写的是 `self`——这些调用是从 `MainWindow` 原样搬进控制器的，搬完之后 `self` 变成了纯 Python 控制器对象（`DashboardController` 不继承 QWidget），PySide6 的参数类型检查当场拒绝 → 抛 `TypeError: QMessageBox.critical called with wrong argument types`。也就是说**「暂无数据，请先分析」「当前数据无偏差率列」「没有替代料预警记录」这类本该安抚用户的提示框，一个都弹不出来，反而触发全局异常钩子变成「程序发生未捕获的异常」大弹窗**（裴哥 10-26 实测：忘了点分析直接开替代料看板即中招；同一批代码路径还包括半成品分类的删除/重置/导入导出全部提示与文件选择框）。修法为父窗口统一改成 `self.mw`（控制器构造时持有的主窗口引用），提示文案、判定条件、异常处理结构零改动。另：`gui_pyside6/dashboard_manager.py` 是 ARC-003 拆分前的旧副本，应用侧已无任何引用（只有 `tests/unit/test_dashboard_manager.py` 还指着它），里面同样的 23 处 `self` 父窗口一并留着不动——它是死代码，删文件需裴哥点头。**配套新增回归网** `tests/unit/test_controller_dialog_parent.py`：L1 用 AST 扫 `controllers/` 目录，禁止再出现「静态对话框首参是裸 self」（防止以后继续从 MainWindow 搬代码时复发），L2 用真实 QWidget 假主窗口走一遍空数据分支，断言提示框确实弹出且父窗口是主窗口。实测：pytest 307 passed / 1 skipped / 2 xfailed（较改前 305 增加 2 条新用例）。**同轮 UI 自查修掉两个我自己引入的显示回归（裴哥 10-26 实测「复选框看不见了」）**：① 新增的通用段里 `QCheckBox, QRadioButton` 写了 `background: transparent` → Qt 的 QStyleSheetStyle 一旦接管这两个控件就**不再画原生小方框**，筛选面板「颜色标记」六行全部只剩文字（亮色主题实测复现）。② 同一批新增规则里的 `QComboBox::drop-down`、`QSpinBox::up-button/down-button`、`QDateEdit::drop-down`（以及历史遗留的 `#factoryCombo::drop-down`、`.comboStyle::drop-down`）同理把下拉箭头与数字框上下箭头抹成空白条，控件看起来完全不能点。修法：两套主题各删掉这 5 条子控件规则（让 Qt 继续画原生箭头，实测亮/暗均恢复），复选/单选改为**显式画 indicator 并把 normal/hover/checked/disabled 四态配齐**（勾选态用主色实心方块、单选为实心圆，暗色下对比度实测达标——原生方框在 `#1C1C1A` 深底上几乎看不见，这也是暗色主题没配 QPalette 的老毛病）；两套主题的选择器集合仍逐条对齐（202 vs 202，diff 为空），QSS 解析告警 0 条，`pytest` 复跑 307 passed / 1 skipped / 2 xfailed。**顺带修未读概览弹窗文字被裁（裴哥 10-26 截图：右下角「未读概览（本次分析）」四类未读的弹窗文字显示不完整）**：`widgets/unread_summary_popup.py` 从 `setFixedWidth(330)` 写死宽度改为按布局内容算宽（`setMinimumWidth(360)` + `_setup_ui()` 后 `adjustSize()` 取内容真实所需宽度，下限 360），标题与「图标+类别名+N 条未读+查看」整行的最小宽度都会自动参与计算，字号变大或类别名变长时不再挤压裁字。实测：离屏渲染 4 行弹窗亮/暗两张图无重叠、无裁字，pytest 307 passed / 1 skipped / 2 xfailed。",
        "features": "**GUI 全面现代化（两套主题重写 + 50 处内联样式清零）**（裴哥「检查代码，优化 ui，改成现代化ui面板」）。① `light_theme.qss` / `dark_theme.qss` 整套重写：统一 8/10/12px 圆角体系 + 1px 描边卡片 + 浅色调色底 hover（旧版 hover 是「整块实心主色」，观感生硬），亮色补齐了暗色早就有的标题栏/状态栏/表格斑马纹（此前亮色主题下 `#titleBar`、`QStatusBar`、`alternate-background-color` 三条规则根本不存在）；两套文件**选择器集合逐条对齐**（脚本 diff 结果：仅亮色缺 3 条、已补齐；`#statusBar/#statusAccentBar/#statusLabel` 三条 Tkinter 时代死选择器删除，代码零引用）。② **全仓 50 处内联 `setStyleSheet` 清零**（`gui_pyside6/**/*.py` 现在只剩 4 处合法的 `QApplication.instance().setStyleSheet()` 主题加载），控件侧只留 objectName / `setProperty(\"class\",...)` 钩子：工具栏 10 个幽灵按钮 `toolGhostBtn`、分析步骤图标 `stepIcon`（`[active=\"true\"]/[done=\"true\"]` 动态属性进 QSS，原来是 22 行内联）、侧栏输入框 `sideInput`、列头筛选浮层标题 `columnFilterTitle`、对话框琥珀提示 `amberHint`、次级说明文字 `mutedText`、规则预览框 `ruleSummaryLabel`、物料画像异常值 `profileWarnValue`、未读汇总弹窗 `unreadRow/unreadCount/unreadSummaryTitle/unreadAllClear`。这一步同时修掉三类真实错位：侧栏输入框内联写死暗色（亮色主题下深灰底白字）、工具栏按钮内联 `color:#666 + hover #eee`（暗色主题下 hover 是一块白斑）、分析按钮内联 `#7F77DD`（亮色主题的主色应是 `#6B63D5`，被暗色值覆盖）。③ **新增「通用控件基样式」段（两套主题各一份、选择器一一对应）**——这是本次观感提升最大的一块：`QDialog/QMessageBox/QFileDialog`、`QPushButton`（含 hover/pressed/checked/disabled/default 五态）、`QToolButton`、`QLineEdit/QTextEdit/QPlainTextEdit`、`QComboBox`（含下拉 `QAbstractItemView`）、`QSpinBox/QDoubleSpinBox/QDateEdit`、`QCheckBox/QRadioButton`、`QGroupBox`（+`::title`）、`QTableView/QTableWidget/QListWidget/QListView/QTreeView/QTreeWidget`（含 `::item` 内边距与斑马纹）、`QHeaderView::section`、`QTabWidget::pane/QTabBar::tab`、`QScrollArea`、`QProgressBar`、`QWidget#colFilterPopup`。此前这些控件在 20 多个对话框/看板里**完全没有主题规则**，全靠 Fusion 原生浅色外观 → 暗色模式下就是深色面板上一块块白斑（表格、按钮、输入框、分组框全白）。`QScrollArea` 只改背景不改边框（Qt 的类选择器匹配子类，写边框会把表格边框一起吞掉）；`colFilterPopup` 是 `Qt.Popup` 顶层控件，只描边不加圆角（无 `WA_TranslucentBackground` 时圆角会露毛角）。④ 验证：`pytest` 305 passed / 1 skipped / 2 xfailed（与改前基线完全一致，`test_toolbar_reorg.py` 锁定的 3 个 `actionMenuBtn` 收纳菜单与 8 平铺按钮结构未破）；新增离屏渲染脚本抓 4 张图（亮/暗 × 主窗口/控件全家福），`qInstallMessageHandler` 捕获 QSS 解析告警 **0 条**，两套主题选择器集合 diff 为空。纯 UI 层改动（`.architecture/constraints.md` 绿灯区），分析口径、数据、交互逻辑零改动。",
    },
    {
        "version": "v43.262",
        "date": "2026-10-26",
        "fixes": "**清掉 3 个既有测试失败（均为测试过期，非代码缺陷，裴哥 10-26 点头「清掉」）**：① `test_mainwindow_only_shells_remaining`——`main_window.py` 的 `_on_cell_double_clicked` 薄壳里残留 v43.236 调试脚手架（statusBar 消息 + try/except traceback/raise，去 docstring 后 3 条语句），而 `InteractionController._on_cell_double_clicked` 本身已有完整 log+traceback+QMessageBox 错误处理，调试代码纯属冗余 → 收敛为标准一行薄壳 `return self.interaction_controller._on_cell_double_clicked(index)`。②③ `test_toolbar_reorg.py::test_toolbar_grouped_layout` / `test_menu_contents`——两个测试锁定的是 2026-09-30 旧工具栏结构（按钮带 ▾ 后缀、objectName=actionMenuBtn、看板菜单 12 项、平铺按钮叫「📊 分析/☰ 隐藏左侧栏/📋 未读概览」），但裴哥本人此后亲手演化了两轮：v43.218 LayoutComposer 重建操作栏（视图开关改 QToolButton、文本改「分析/☰ 左侧栏/🔍 筛选/📢 未读」）、v43.228 亲手提交「恢复看板与导出的下拉菜单选项」（看板 9 项、无 ▾）、ARC-003 加「🔒 自动隔离」平铺按钮、后续把物料画像挪进维护菜单 → 测试从 v43.228 起就一直在假红。修法为**测试对齐现行设计**（代码是裴哥的有意变更，不回退）：给 `layout_composer.py` 三个下拉按钮补 `setObjectName(\"actionMenuBtn\")` 提高可测性（零 UI 变化），两个测试改为锁定现行结构——收纳菜单 3 个（📊 看板/📤 导出/🔧 维护，菜单ButtonPopup 模式自带箭头无需 ▾）、看板菜单 8 项（替代料看板/偏差率预警/负损看板/正损看板/隔离区/数据稳定性/替代料长链/半成品看板）、导出 2 项、维护 2 项（自动隔离规则/物料画像）、平铺 8 键（分析/☰ 左侧栏/🔍 筛选/🔽 列头筛选/📊 概览/⚡ 进度/📢 未读/🔒 自动隔离），并逐项断言关键菜单项防数字对内容错；docstring 补记演化史。实测：3 个失败全清，pytest 305 passed / 1 skipped / 2 xfailed（此前 302+3 失败）。",
    },
    {
        "version": "v43.261",
        "date": "2026-10-24",
        "features": "**归藏 AI 报告改「混合外壳」模式（fragment mode）**——裴哥反馈「怎么感觉没有原来的效果」后的方向选择（A 方案）：实测纯 AI 单文件版 `animate()=0 / motion.min.js=0 / canvas=0`，而模板版有 90 处 `animate` + motion.min.js + WebGL 网格背景 + 导航点 + 预置 CSS 动效体系——**「原来的效果」全部来自模板外壳**，纯 AI 路径产出的是静态单文件（杂志风有 92 个 data-anim 钩子但无驱动脚本，空转；瑞士风连钩子都没有）。方案：**模板外壳全保留**（WebGL/Motion One/导航/键盘翻页/B 静态模式/ESC 总览一样不少），**AI 只重新设计每期 `<section>` 幻灯片内容**，类名必须取自模板 CSS 词表（瑞士 243 个 / 杂志 116 个，模板未定义的类名不会有任何效果），注入 `%%GZ_SLIDES%%` 占位符。`core/guizang_ai.py` 新增 fragment 模式全套：`load_template_shell(style)` / `template_class_vocab(style)`（从模板 `<style>` 块提取类名表）/ `template_recipes(style)`（瑞士 21 种 data-animate recipe / 杂志 pipeline|directional|quote|hero|cascade）/ `extract_fragment(raw)`（剥围栏、取首个 `<section` 到末个 `</section>`）/ `looks_complete_fragment(frag)`（fragment 级硬门：`<section` 开头 `</section>` 结尾、≥8 个 section、**禁止出现 html/head/body/doctype/style/script 标签**（外壳由模板提供，AI 不许重造）、可见文本 ≥3000、中文门 ≥600 且占比 ≥50%）/ `inject_fragment(style, frag, title)` / `build_fragment_prompts(data, style, direction)`；`generate_ai_html()` 新增 `style` 参数——传入 magazine/swiss 走 fragment 路径，不传保持原全页行为（向后兼容）。Fragment prompt 写明两种风格的 section 结构规范（瑞士=`class=\"slide light|dark|accent|grey\" data-animate=\"recipe\"` + 内层 `data-anim=\"kicker|title|kpi|stats|note|table|bars|left|right|bottom|lead|line|up\"`；杂志=`class=\"slide light|dark|hero\" data-theme=\"light|dark\"` + 可选 `data-animate=\"pipeline|directional|quote\"`，封面/收尾按模板既有约定），**颜色一律用模板 CSS 变量**（var(--accent)/var(--ink)/var(--paper)/var(--grey-1)…，禁止写死 hex、禁止 @font-face、禁止 <style> 块——配色字体由外壳统一提供），数字纪律/中文纪律/内容覆盖 10 条硬规则与全页版完全一致，数字护栏同一套白名单照跑。GUI「AI 重新设计」按钮透传 style 走混合外壳，预览仍落 `resources/guizang/{style}/_preview.html`（与 assets/ 同目录，`./assets/motion.min.js` 相对路径可用）；CLI 加 `--style=`，输出时自动把 assets/ 复制到输出同目录（保证双击打开也有完整动效，不再静默丢动画）。**首轮端到端实测（2026-10-03~10-23 真实分析结果，双风格串行共 16 分钟）**：杂志风 2 轮过（第 1 轮护栏抓下 4 个越界），57,301 字符 / 14 页 / 0 违规 / 中文 96% / animate×10 + motion×2 + canvas×2 + data-anim×67 全在；瑞士风补跑 1 轮过（第 1 轮护栏抓下 AI 把 −238.76 负号丢成 238.76——正是护栏存在的意义），118,176 字符 / 15 页 / 0 违规 / 中文 97% / animate×90 + motion×1 + canvas×3 + data-anim×129 全在；两版替代料关键数字（125 条 / −238.76 / −7.06 / +0.48）均原文在位（v43.259 修的坑回归通过）。残留两处无害偏差已如实记录：① AI 写出 3~5 个词表外类名（杂志 pipeline-step/pipeline-arrow、瑞士 col-val/span-13/light——无 CSS 定义即无样式，不破坏任何机制，动效全靠 data-anim 属性选择器驱动）；② 杂志「口径说明」页 AI 用了 class 版 pipeline 标记（容器 class=pipeline + 子层 class=pipeline-step），没接上模板 pipeAdvance 要求的 section 级 data-animate=pipeline + 子层 data-anim=step 接线 → 该页退化为普通级联淡入（步骤一次全部呈现，内容与数字不受影响）。另：`inject_fragment()` 对瑞士做 pipeline→progression 确定性清洗作**纯防御**（prompt 已禁；精确复验——按 #deck~#nav 截取——确认 AI 实际两版都没写过 pipeline，此前一度误判是我自己的合规检查切片没截断、把外壳 JS 兜底代码里的字样算成了 fragment 内容，已纠正），杂志的 pipeline 有完整实装不清洗。单测扩到 ⑰~㉒（词表/配方/extract/结构门三反证/注入位置/mock 路由端到端/护栏不过仍注入外壳/style=None 向后兼容）全绿；pytest 302 passed（3 个既有失败与本次无关，已用 git worktree 纯净 HEAD 复现过）。",
    },
    {
        "version": "v43.260",
        "date": "2026-10-24",
        "features": "**归藏（guizang）双风格入库 AI 设计方向池**（裴哥点名「用归藏做，都 AI、不套用模板」）：从 guizang-ppt-skill 的 references/themes.md + layouts.md（电子杂志×电子墨水）与 themes-swiss.md + layouts-swiss.md（瑞士国际主义）提炼出两套完整视觉规范，写成 `core/guizang_ai.py` 的 `GZ_MAGAZINE` / `GZ_SWISS` 两个设计方向并加入 `DESIGN_DIRECTIONS` 池。AI 按归藏美学**自由设计版式**，不复制 skill 的 template.html；数字仍全部来自 `build_report_data()` 数据字典并过数字护栏（零外链/万元/负号 −/正=多耗负=节约全部硬约束不变）。规范要点：杂志风=5 套预设主题色（墨水经典/靛蓝瓷/森林墨/牛皮纸/沙丘，一份 deck 一套不混搭）+ 衬线大标题 + kicker/meta-row/stat-card/callout/pipeline 编辑元素 + 不对称网格 + 级联淡入；瑞士风=单一锚点色（克莱因蓝/柠檬黄/柠檬绿/安全橙四选一不混搭）+ 200 字重细标题(-0.04em/0.9 行高) + 16 列网格 + 画布卡 5.6vh 5vw 4.4vh 不二次加水平 padding + 直角纯色禁渐变禁圆角禁阴影 + 中文标题按长度降字号分档。CLI 支持方向名快捷映射（`magazine`/`swiss`/`gz-magazine`/`gz-swiss`/`归藏杂志`/`归藏瑞士`）。首轮实测：杂志风一把过（AI 自选靛蓝瓷主题，40,617 字符）；瑞士风首轮破了「单一锚点色」铁律（除克莱因蓝外另定义 --accent-light 柠檬黄、页面上 5 个黄盒）→ 规范补【锚点色唯一性】硬条款（只许一个强调色变量，浅色强调块用同色系 tint 不许换色相）。**第二轮实测再抓「全文英文」废版**（裴哥原话「瑞士风全是英文，看不懂」）：瑞士风的西式设计语言（Inter/Helvetica/Mono + t-cat 标签）把 AI 带成英文仪表盘——中文仅 363 字、占比 18%（Net Deviation / Top Negative Records / Factory Detail 满天飞），而杂志风同批次中文占 91%、通用版 88%，数字还全对。修法三路：① SYSTEM_PROMPT 第 8 条从「中文」升级为显式中文纪律（所有可见文字必须简体中文，禁止英文标题/标签/图例，等宽字体只渲染数字，唯一例外 ZPP011/SAP/ERP/物料编码，并点明「西式版式不影响语言」）；② 两个归藏规范各加【语言】条款；③ **确定性中文门**进 `looks_complete`：汉字 < 600 或汉字占比 < 50% 直接判废，结构失败时给专属修正提示（多成因诊断：script 注入/英文/截断分别给不同 hint）。护栏单测扩到 18 项（⑯ 中文门 + 反证）。语言修复实测生效：重跑后首轮产物汉字 1,144、占比 96%（修前 363/18%），只剩 1 个自算百分比（66.8%）被护栏抓住。因连续 4 跑 3 跑在 420s 被 agnes 读超时打断（修正机会白丢一轮），读超时提至 540s。⚠️ 两个重任务并行会把 agnes 端挤爆（420s 读超时），归藏双风格必须串行生成。",
    },
    {
        "version": "v43.259",
        "date": "2026-10-24",
        "fixes": "**修复归藏报告「替代料」每期都误报为 0 的真缺陷**（`core/guizang_report.py`）：旧逻辑以「偏差原因分析」页存在备注原因==「替代料」的行为前提（`if len(sub)`），但该页自 v43.254 起就把替代料行摘去「替代料明细」单列，备注原因里永远不会有这个类别 → `len(sub)` 恒为 0 → **已经读到的「替代料明细」行数被整体丢弃**，字典每期输出 `substitute={rows:0, over:0, less:0}`，模板版与 AI 版两个入口都跟着写「多耗 0 万 / 少耗 0 万 / 共 0 条 / 本期无替代料使用记录」。改为唯一权威来源取「替代料明细」页（A↔B 配对级，125 行）：rows=明细条数、over/less=净偏差数量正负分向（带符号，正=多耗/负=节约，与全报告口径一致——否则 AI 按惯例给幅值加负号会被护栏误判，实测踩到）、**新增 net=净偏差金额合计（元→万元）**；旧备注原因路径仅在该页缺失时兜底（向后兼容旧工作簿）。实测 10-03~10-23：125 条、多耗 +0.48 / 少耗 −238.76（数量口径，吨/件/个/KG 混计）、净 −7.06 万（修正前 0/0/0）。两个模板的口径提示行同步改为带符号并补净额；AI prompt 必覆盖清单加入「替代料」并要求引用 substitute 真实数字。**同轮加固数字护栏（第 5 次端到端实测 12 个越界逐个数甄别后）**：① 新增没年份月日剥离（`10-31 前补齐` 被切出 `-31`——只剥 `-` 与 `/` 两种日期写法，**绝不剥点号**，否则 `−26.39` 这种真违规会被吞掉，已加反证用例）；② prompt 数字纪律新增第 5 条，点名四类「行文里算数」全违规：多行相加（三条记录合计 −268.84）、求平均（单行 2.38 万）、单位换算（23,800 元→2.38 万）、建议里编目标数（收敛至 −300 万）——第 5 次失败 12 个越界里 9 个是这类。③ **堵「内容藏进 <script>」的真空通过洞（最严重，第 6 次实测）**：AI 把整份报告连同数据字典塞进单个 `<script>` 用 JS 注入 DOM——总字符 35,438 但可见文本仅 82，而护栏只扫可见文本 → 不查就等于全放行（本次侥幸零污染：script 内字典与真字典逐字节一致，但 JS 模板字串里算的数护栏永远看不见）。三层防御：`looks_complete` 新增可见文本下限 3,000 字符（实测正常生成 15,000~17,000）；prompt 输出格式新增第 15 条硬规则（内容必须直接写在 HTML 标签里，`<script>` 只许写交互逻辑且不许出现业务数字）；结构失败时给专属修正提示（区分「截断/围栏」与「藏进 script」两种成因）。",
    },
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
