# -*- coding: utf-8 -*-
"""
DataFrame Model 和 Proxy Model
支持 pandas DataFrame 与 QTableView 的数据绑定、排序、筛选、编辑等
"""
import pandas as pd
from datetime import datetime
from PySide6.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt, Signal, QModelIndex


class DataFrameModel(QAbstractTableModel):
    """将 pandas DataFrame 适配为 QAbstractTableModel"""
    dataChanged = Signal()

    def __init__(self, data: pd.DataFrame = None):
        super().__init__()
        self._data = pd.DataFrame()
        self._original_data = pd.DataFrame()
        if data is not None:
            self.setDataFrame(data)

    def setDataFrame(self, df: pd.DataFrame):
        self.beginResetModel()
        self._data = df.copy()
        
        # 确保 _read 列存在（用于已读/未读状态）
        if '_read' not in self._data.columns:
            self._data['_read'] = 0  # 默认未读
        
        # 将 _read 列移到第一列
        cols = ['_read'] + [c for c in self._data.columns if c != '_read']
        self._data = self._data[cols]
        
        self._original_data = self._data.copy()
        self.endResetModel()
        self.dataChanged.emit()

    def getDataFrame(self) -> pd.DataFrame:
        return self._data

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        
        # 第一列显示已读/未读图标
        if col == 0:
            if role == Qt.DisplayRole:
                read_val = self._data.iloc[row].get('_read', 0)
                return '✅' if read_val else '🔘'
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            elif role == Qt.ToolTipRole:
                read_val = self._data.iloc[row].get('_read', 0)
                return '已读' if read_val else '未读'
            return None
        
        # 其余列：需要偏移1位（因为第0列是 _read）
        # 找到 _read 列在 DataFrame 中的实际位置
        try:
            read_col_idx = list(self._data.columns).index('_read')
        except ValueError:
            read_col_idx = -1  # _read 列不存在
        
        # 表格列 col 对应 DataFrame 的列 (col 如果 _read 在第0列)
        # 如果 _read 在第0列，那么表格列1 → DataFrame列1，表格列2 → DataFrame列2...
        # 如果 _read 不在第0列，需要动态计算
        if read_col_idx == 0:
            df_col = col  # 不需要偏移
        else:
            # _read 不在第0列，表格列0显示 _read，表格列1显示DataFrame列0...
            df_col = col - 1 if col >= 1 else read_col_idx
        
        if 0 <= row < len(self._data) and 0 <= df_col < len(self._data.columns):
            value = self._data.iloc[row, df_col]
            if role == Qt.DisplayRole or role == Qt.EditRole:
                return str(value) if pd.notna(value) else ""
            elif role == Qt.TextAlignmentRole:
                if pd.api.types.is_numeric_dtype(self._data.dtypes.iloc[col]):
                    return Qt.AlignRight | Qt.AlignVCenter
                return Qt.AlignLeft | Qt.AlignVCenter
            elif role == Qt.BackgroundRole:
                # 预警列上色
                col_name = self._data.columns[col]
                if col_name == '预警':
                    val = str(value).strip()
                    if '🔴' in val or val == '红色预警':
                        return Qt.GlobalColor.red
                    elif '🟡' in val or val == '黄色预警':
                        return Qt.GlobalColor.yellow
                    elif '🟢' in val or val == '绿色预警':
                        return Qt.QColor(144, 238, 144)  # 浅绿
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                # 第一列显示为"状态"
                if section == 0:
                    return "状态"
                # 其余列：需要偏移1位（因为第0列是 _read）
                try:
                    read_col_idx = list(self._data.columns).index('_read')
                except ValueError:
                    read_col_idx = -1
                
                if read_col_idx == 0:
                    # _read 在第0列，不需要偏移
                    if section < len(self._data.columns):
                        return str(self._data.columns[section])
                else:
                    # _read 不在第0列，需要偏移
                    data_cols = [c for c in self._data.columns if c != '_read']
                    if section - 1 < len(data_cols):
                        return str(data_cols[section - 1])
                return str(section)
            else:
                return str(self._data.index[section] + 1)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        col = index.column()
        
        # 第一列（状态列）不可编辑
        if col == 0:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
        
        col_name = self._data.columns[col]
        # 只允许备注列可编辑
        if col_name in ('备注', '备注原因'):
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole:
            row = index.row()
            col = index.column()
            col_name = self._data.columns[col]
            # 只允许备注列
            if col_name not in ('备注', '备注原因'):
                return False
            try:
                self._data.iloc[row, col] = value
                self.dataChanged.emit(index, index)
                return True
            except Exception:
                return False
        return False

    def sort(self, column, order=Qt.AscendingOrder):
        self.beginResetModel()
        # 跳过状态列（column 0 是 _read 列，不可排序）
        if column == 0:
            self.endResetModel()
            return
        # 列索引偏移：表格列1对应DataFrame列0，列2对应列1，以此类推
        actual_col = column - 1
        if actual_col < 0 or actual_col >= len(self._data.columns):
            self.endResetModel()
            return
        col_name = self._data.columns[actual_col]
        ascending = (order == Qt.AscendingOrder)
        self._data = self._data.sort_values(by=col_name, ascending=ascending)
        self.endResetModel()
        self.layoutChanged.emit()


class AuditProxyModel(QSortFilterProxyModel):
    """代理模型，支持列筛选和排序
    新增：自定义筛选（偏差率范围、备注为空等）
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters = {}       # 列索引 -> 筛选文本（顶部筛选行，保留兼容）
        self._custom_filters = {}  # 自定义筛选条件（侧边栏）

    def sort(self, column, order=Qt.AscendingOrder):
        """将排序请求转发给源模型"""
        src = self.sourceModel()
        if src:
            src.sort(column, order)
        # 刷新筛选（保持筛选条件不丢失）
        self.invalidateFilter()

    # ------------------------------------------------------------------ #
    # 顶部筛选行接口（保留兼容）
    # ------------------------------------------------------------------ #
    def setFilter(self, column, text):
        if text:
            self._filters[column] = text.lower()
        else:
            self._filters.pop(column, None)
        self.invalidateFilter()

    def clearFilters(self):
        self._filters.clear()
        self._custom_filters.clear()
        self.invalidateFilter()

    # ------------------------------------------------------------------ #
    # 侧边栏自定义筛选接口
    # ------------------------------------------------------------------ #
    def setCustomFilters(self, filters: dict):
        """设置侧边栏筛选条件
        filters 字典格式：
          - 普通列筛选：{列名: 值}（精确匹配）
          - 特殊筛选：{'_dev_rate_range': '>10%', '_remark_empty': True/False}
        """
        self._custom_filters = filters
        self.invalidateFilter()

    # ------------------------------------------------------------------ #
    # 核心过滤逻辑
    # ------------------------------------------------------------------ #
    def filterAcceptsRow(self, source_row, source_parent):
        # 先处理顶部筛选行（子串匹配，保留原有行为）
        if self._filters:
            source_model = self.sourceModel()
            for col, filter_text in self._filters.items():
                index = source_model.index(source_row, col)
                value = source_model.data(index, Qt.DisplayRole)
                if filter_text not in str(value).lower():
                    return False

        # 再处理侧边栏自定义筛选
        if self._custom_filters:
            source_model = self.sourceModel()
            df = source_model.getDataFrame()
            if df is None or df.empty:
                return True
            row_data = df.iloc[source_row]

            # 1. 精确列筛选（工厂、车间、替代料等）
            for col_name, value in self._custom_filters.items():
                if col_name.startswith('_'):   # 特殊筛选条件，稍后处理
                    continue
                if col_name not in df.columns:
                    continue
                row_val = str(row_data.get(col_name, '')).strip()
                if row_val != str(value).strip():
                    return False

            # 1.5 物料编码模糊搜索（支持逗号分隔多值，OR匹配）
            if '_material_code' in self._custom_filters:
                code_col = self._get_material_code_column(df)
                if code_col:
                    raw_query = str(self._custom_filters['_material_code']).lower()
                    row_code = str(row_data.get(code_col, '')).lower()
                    # 按逗号分隔，每个值为一个独立条件（OR关系）
                    queries = [q.strip() for q in raw_query.split(',') if q.strip()]
                    matched = False
                    for q in queries:
                        if q in row_code:
                            matched = True
                            break
                    if not matched:
                        return False

            # 1.6 流程订单模糊搜索
            if '_process_order' in self._custom_filters:
                order_query = str(self._custom_filters['_process_order']).lower()
                matched = False
                for col_name in ['流程订单', 'process_order']:
                    if col_name in df.columns:
                        row_val = str(row_data.get(col_name, '')).lower()
                        if order_query in row_val:
                            matched = True
                            break
                if not matched:
                    return False

            # 2. 偏差率范围（绝对值>=10%）
            if '_dev_rate_abs_ge_10' in self._custom_filters:
                rate_col = self._get_rate_column(df)
                if rate_col:
                    rate_raw = row_data.get(rate_col, 0)
                    try:
                        if isinstance(rate_raw, str):
                            rate = float(rate_raw.replace('%', ''))
                        else:
                            rate = float(rate_raw)
                    except (ValueError, TypeError):
                        rate = 0
                    if abs(rate) < 10:
                        return False

            if '_dev_rate_range' in self._custom_filters:
                rate_col = self._get_rate_column(df)
                if rate_col:
                    rate_raw = row_data.get(rate_col, 0)
                    range_str = self._custom_filters['_dev_rate_range']
                    if not self._check_rate_range(rate_raw, range_str):
                        return False

            # 3. 已读/未读
            if '_read_status' in self._custom_filters:
                status = self._custom_filters['_read_status']
                read_val = row_data.get('_read', 0)
                if status == '已读' and read_val != 1:
                    return False
                if status == '未读' and read_val != 0:
                    return False

            # 4. 备注为空
            if '_remark_empty' in self._custom_filters:
                remark_col = self._get_remark_column(df)
                if remark_col:
                    remark = row_data.get(remark_col, '')
                    is_empty = (pd.isna(remark) or str(remark).strip() == '')
                    if self._custom_filters['_remark_empty'] != is_empty:
                        return False

            # 4. 日期范围
            if '_date_start' in self._custom_filters or '_date_end' in self._custom_filters:
                date_col = self._get_date_column(df)
                if date_col:
                    row_date = row_data.get(date_col)
                    try:
                        row_date = pd.to_datetime(row_date).date()
                        start = self._custom_filters.get('_date_start')
                        if start:
                            start_date = datetime.strptime(start, "%Y-%m-%d").date()
                            if row_date < start_date:
                                return False
                        end = self._custom_filters.get('_date_end')
                        if end:
                            end_date = datetime.strptime(end, "%Y-%m-%d").date()
                            if row_date > end_date:
                                return False
                    except Exception:
                        pass

        return True

    # ------------------------------------------------------------------ #
    # 辅助方法
    # ------------------------------------------------------------------ #
    def _get_rate_column(self, df):
        for col in ['偏差率(%)', '偏差率']:
            if col in df.columns:
                return col
        return None

    def _get_remark_column(self, df):
        for col in ['备注原因', '备注']:
            if col in df.columns:
                return col
        return None

    def _get_date_column(self, df):
        for col in ['订单日期', '订单开始日期', '日期']:
            if col in df.columns:
                return col
        return None

    def _get_material_code_column(self, df):
        for col in ['物料号', '物料编码', 'code', '组件物料号']:
            if col in df.columns:
                return col
        return None

    def _check_rate_range(self, rate_raw, range_str):
        try:
            if isinstance(rate_raw, str):
                rate = float(rate_raw.replace('%', ''))
            else:
                rate = float(rate_raw)
        except (ValueError, TypeError):
            rate = 0
        abs_rate = abs(rate)
        if range_str == '绝对值>=10%':
            return abs_rate >= 10
        elif range_str == '>10%':
            return abs_rate > 10
        elif range_str == '>20%':
            return abs_rate > 20
        elif range_str == '>30%':
            return abs_rate > 30
        elif range_str == '<-10%':
            return rate < -10
        elif range_str == '<-20%':
            return rate < -20
        elif range_str == '<-30%':
            return rate < -30
        return True

    # ------------------------------------------------------------------ #
    # 排序
    # ------------------------------------------------------------------ #
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        # 垂直表头始终显示顺序行号 1,2,3...（不受排序/筛选影响）
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(section + 1)
        return super().headerData(section, orientation, role)

    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, Qt.DisplayRole)
        right_data = self.sourceModel().data(right, Qt.DisplayRole)
        try:
            left_num = float(left_data)
            right_num = float(right_data)
            return left_num < right_num
        except (ValueError, TypeError):
            return str(left_data) < str(right_data)
