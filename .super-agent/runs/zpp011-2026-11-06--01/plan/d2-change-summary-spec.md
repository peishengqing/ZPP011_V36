# D2 本地「变更摘要」面板 — 实现方案

> 批次：zpp011-2026-11-06--01 ｜ D2 落地 ｜ 北京时间 2026-11-06
> 总原则（D 红线）：系统只生成、不主动外发；不定时/不事件触发/不 Bot/不邮件/不动画。
> 前置：D1 按需快照已落地（v43.302，commit ca948ae），历史库 `history.sqlite` 已逐次落 unfinished/score 字段。

## 一、目标

在看板/快照页内嵌一个**可折叠、按需渲染**的「变更摘要」面板，替代原先被砍掉的「主动 Bot 推送」。
保留「变更可追溯」，但不制造「推送即结论」误导；阶梯图比文字更直观回答「这个订单入了几次、还差多少」。

## 二、面板结构（GUI 侧）

- 看板对话框顶部（快照条之后）插入 `QGroupBox`：`📊 变更摘要（本期间 · 本地，不推送）`，`setCheckable(True)`、`setChecked(False)`（默认收起）。
- 组内：
  - 「刷新摘要（按需渲染图表）」按钮 —— 点击才计算 + 渲染，不自动刷新、无定时器、无动画。
  - 一段 `QTextBrowser` 文字摘要（Markdown）。
  - 一行三个 `QLabel`（方框占位）：阶梯图 / 进度条 / 趋势线；刷新后载入 PNG。
- 接入位置：neg_loss / pos_loss / semi / alert / deviation_warning 五个看板对话框，复用 `attach_snapshot_bar` 的接入范式。

## 三、变更摘要口径（纯逻辑，core/change_summary.py）

对比「当前实时状态」与「最近一次快照基线」：

- 当前未完结：`core.snapshot.compute_unfinished(main_df)`（沿用 D1 拍板口径，含豁免排除）。
- 基线：扫描 `SNAPSHOT_ROOT` 取最新快照目录的 `unfinished.json` + `score.json` + `meta.json.generated_at`。
- 订单级对比（key = (工厂,订单日期,流程订单)）：
  - `finished_orders` = 基线未完结 − 当前未完结（即「从未完结→完结」）
  - `new_unfinished_orders` = 当前未完结 − 基线未完结（新出现）
  - `still_unfinished` = 交集
- 偏差修改/归因漂移：读 `deviation_history`，`change_time >= 基线生成时刻(iso)`（由快照目录名 `YYYYMMDD-HHMMSS` 推导，避免依赖 meta 字符串格式），取 `data_id<>'X'`。统计笔数 + 涉及订单数。
- 评分卡：当前用 `core.scorecard.compute_scorecard(df)`；变化 = 当前 − 基线 `score.json`。

> 注：「本期间」在本实现中 = 「自最近一次快照以来」。若无历史快照，显示「首次快照/历史为空」，只列当前值与本期偏差修改记录，不报变化。

## 四、三张静态图（core/change_summary.render_charts，matplotlib Agg 离屏）

读 `history.sqlite`（D1 已落）：

1. **未完结订单数阶梯图**：x=快照时间戳，y=该快照 `unfinished_orders`，`step(where="post")`；标题「未完结订单数（阶梯·按快照时间）」；右上角红字标「未完结 X/Y」（取最新快照）。
2. **未完结进度条拼图**：横向堆叠条形 [已完结(total−unfinished) | 未完结]，绿/红配色；比对最近两快照 `unfinished_orders`，若不同则标「今日有变更」(琥珀) 否则「今日无变更」(灰)。
3. **评分卡趋势线**：近 30 天 `coverage_rate` / `drift_rate` / `score_total` 三条折线（缺失值跳过）。

无历史行时对应图返回空路径，面板显示「（暂无数据）」。

## 五、文件级落点

| 文件 | 改动 |
|---|---|
| `core/scorecard.py`（**新增**，纯逻辑无 PyQt） | 复用 data_stability_dialog._fill_score 口径（覆盖率50%/漂移30%/长链20%），纯函数 `compute_scorecard(df) -> dict` |
| `core/change_summary.py`（**新增**，纯逻辑无 PyQt） | `list_snapshots/latest_snapshot_dir/compute_change_summary/render_charts` |
| `gui_pyside6/utils/change_summary_panel.py`（**新增**，PyQt 仅此文件） | `attach_change_summary(dialog)` 折叠面板 + 刷新回调 |
| 五个看板对话框 | import + `attach_change_summary(self)`（紧跟 `attach_snapshot_bar`） |
| `gui_pyside6/utils/snapshot_action.py` | `_collect_score` 改调 `core.scorecard.compute_scorecard(df)`（回填历史库评分，原桩无效） |
| `utils/version_history.py` | 头部升 v43.303 |

## 六、验证（offscreen 独立，非 worker 自报）

1. `core/scorecard.compute_scorecard` 单测：构造带「备注原因」列的主表 + 内存 deviation_history，断言三项子分与总评分在 0–100、权重符合预期。
2. `core/change_summary.compute_change_summary` 单测：造一份当前 df + 一份基线 `unfinished.json`，断言 finished/new/still 订单数精确；无基线时 `has_baseline=False` 不报错。
3. `render_charts` 单测：构造临时 history.sqlite（多行），断言输出 3 个非空 PNG；空历史时返回空路径不抛。
4. py_compile + pyflakes（F821/F401）全绿后 commit + push（附北京时间）。

## 七、验收标准

- [ ] 五个看板出现可折叠「变更摘要」，默认收起，点「刷新」才出内容与图。
- [ ] 文字摘要数字与 D1 快照/当前看板对账一致；无基线时不报变化、不报错。
- [ ] 三张图均为静态 PNG 嵌入，无动画、无自动刷新、无推送。
- [ ] 趋势线读 D1 历史库；首次无历史时优雅降级。
- [ ] py_compile + pyflakes 全绿，已 commit + push。
