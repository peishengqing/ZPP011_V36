# ZPP011 可视化增强方案

## 现有可视化能力
1. **dashboard_html.py**: 12 张 matplotlib 图 + Chart.js 交互图
2. **DashboardDialog**: GUI 中嵌入的 HTML 看板
3. **NegLossDashboard**: 负损看板
4. **PosLossDashboard**: 正损看板  
5. **SemiDashboard**: 半成品看板

## 可增强的方向

### A. Excel 文件增强
- 主表增加：标准单价、量差、价差、验证列
- 新 Sheet: 量价分解、车间汇总、原因 TOP20、物料画像

### B. PySide6 可视化增强
1. **主窗口集成**:
   - 数据表格中动态展示量价分解结果
   - 量化条、颜色指示可视化偏差构成

2. **新增独立对话框**:
   - 量价分解透视表
   - 车间维度热力图
   - 时间序列趋势图（与 dashboard_html.py 类似）

3. **HTML 看板扩展**:
   - 折叠统计
   - 新增图表：分厂对比、原因拓扑、物料分布等

### C. 新增图表想法
1. **瀑布图**: 总量差→分项量差
2. **桑基图**: 替代料流向导致偏差
3. **词云**: 原因标签云
4. **箱线图**: 各车间偏差分布

## 技术实现
- 主窗口：PySide6 + matplotlib embedding + 自定义delegate
- 数据表格：QTableView + 自定义表格模型 + 条件格式
- HTML看板：将matplotlib输出转为Web友好的Chart.js
- Excel增强：pandas + openpyxl

