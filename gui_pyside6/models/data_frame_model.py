# -*- coding: utf-8 -*-
"""
DataFrame Model 和 Proxy Model
支持 pandas DataFrame 与 QTableView 的数据绑定、排序、筛选、编辑等
"""
import numpy as np
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
        self._data_cache = []  # 新增：缓存二维列表
        self._display_columns = []  # 记录列顺序
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
        self._build_cache()  # 新增：构建缓存
        self.endResetModel()
        self.dataChanged.emit()

    def _build_cache(self):
        """将 DataFrame 转换为 Python 原生类型的二维列表，大幅提升 data() 速度"""
        if self._data.empty:
            self._data_cache = []
            self._display_columns = []
            return

        self._display_columns = list(self._data.columns)
        # 逐行转换：将 pandas Series 转为 list，并处理 NaN
        self._data_cache = []
        for idx in range(len(self._data)):
            row = self._data.iloc[idx]
            row_list = []
            for col in self._display_columns:
                val = row[col]
                # 处理缺失值
                if pd.isna(val):
                    row_list.append("")
                else:
                    # 保留原始类型，但确保数值是 Python 原生类型
                    if isinstance(val, (np.integer, np.int64, np.int32)):
                        row_list.append(int(val))
                    elif isinstance(val, (np.floating, np.float64, np.float32)):
                        row_list.append(float(val))
                    else:
                        row_list.append(val)
            self._data_cache.append(row_list)

    def getDataFrame(self) -> pd.DataFrame:
        return self._data

    def rowCount(self, parent=QModelIndex()):
        return len(self._data_cache)

    def columnCount(self, parent=QModelIndex()):
        return len(self._display_columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        
        # 边界检查（使用缓存）
        if row < 0 or row >= len(self._data_cache) or col < 0 or col >= len(self._display_columns):
            return None
        
        # 第一列显示已读/未读图标
        if col == 0:
            if role == Qt.DisplayRole:
                read_val = self._data_cache[row][0]
                return '✅' if read_val else '🔘'
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            elif role == Qt.ToolTipRole:
                read_val = self._data_cache[row][0]
                return '已读' if read_val else '未读'
            return None
        
        # 其余列：从缓存读取
        if role == Qt.DisplayRole or role == Qt.EditRole:
            val = self._data_cache[row][col]
            # 偏差率列：显示时加 % 后缀
            col_name = self._display_columns[col]
            if '偏差率' in col_name and val != "":
                try:
                    return f"{float(val):.2f}%"
                except (ValueError, TypeError):
                    return str(val)
            # 格式化浮点数
            if isinstance(val, float):
                if abs(val) >= 1000:
                    return f"{val:,.2f}"
                return f"{val:.2f}"
            return str(val) if val != "" else ""
        
        elif role == Qt.TextAlignmentRole:
            # 根据缓存中的类型判断对齐方式
            val = self._data_cache[row][col]
            if isinstance(val, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        
        elif role == Qt.BackgroundRole:
            # 预警列上色
            col_name = self._display_columns[col]
            if col_name == '预警':
                val = str(self._data_cache[row][col]).strip()
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
            col_name = self._display_columns[col]
            # 只允许备注列
            if col_name not in ('备注', '备注原因'):
                return False
            try:
                # 更新 DataFrame
                self._data.iloc[row, self._data.columns.get_loc(col_name)] = value
                # 更新缓存
                self._data_cache[row][col] = value
                self.dataChanged.emit(index, index)
                return True
            except Exception:
                return False
        return False
    def _get_deviation_rate(self, row):
        """从缓存中获取当前行的偏差率（百分比数值）"""
        # 查找偏差率列索引
        rate_col = None
        for i, col in enumerate(self._display_columns):
            if col in ('偏差率(%)', '偏差率'):
                rate_col = i
                break
        if rate_col is None:
            return 0.0
        val = self._data_cache[row][rate_col]
        if isinstance(val, (int, float)):
            return float(val)
        # 如果缓存中是带%的字符串（兜底）
        if isinstance(val, str) and '%' in val:
            try:
                return float(val.replace('%', '').strip())
            except:
                return 0.0
        return 0.0

    def _is_warning_column(self, col_name):
        """检查列是否为预警列"""
        return col_name in ('偏差率(%)', '偏差率')


    def sort(self, column, order=Qt.AscendingOrder):
        """排序：支持百分比列数值排序"""
        self.beginResetModel()
        
        # 第0列是状态列，不排序
        if column == 0:
            self.endResetModel()
            return
        
        # 表格列和DataFrame列的映射（第0列是_read）
        actual_col = column  # DataFrame的第0列就是_read，表格第0列也是_read
        if actual_col < 0 or actual_col >= len(self._data.columns):
            self.endResetModel()
            return

        col_name = self._data.columns[actual_col]
        ascending = (order == Qt.AscendingOrder)
        
        print(f"[DEBUG sort] column={column}, actual_col={actual_col}, col_name={col_name!r}, ascending={ascending}")

        # 百分比列特殊处理：去掉%转数字排序
        if '%' in str(col_name):
            # 转换为数值
            numeric_vals = pd.to_numeric(
                self._data[col_name].astype(str).str.replace('%', '').str.strip(),
                errors='coerce'
            )
            # 按数值排序
            sort_key = numeric_vals.argsort(kind='mergesort')
            self._data = self._data.iloc[sort_key].copy()
            if not ascending:
                self._data = self._data.iloc[::-1].copy()
        else:
            self._data = self._data.sort_values(by=col_name, ascending=ascending).copy()

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
        self._alert_threshold = 10.0  # 预警阈值，默认10%

    def sort(self, column, order=Qt.AscendingOrder):
        """代理模型排序：交给父类用 lessThan() 处理"""
        super().sort(column, order)

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

            # 2. 偏差率范围（绝对值>=阈值）
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
                    threshold = getattr(self, '_alert_threshold', 10.0)
                    if abs(rate) < threshold:
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

    def set_alert_threshold(self, threshold):
        """动态设置预警阈值"""
        self._alert_threshold = threshold

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
        col_name = self.sourceModel().headerData(left.column(), Qt.Horizontal)
        try:
            # 去掉 % 和逗号，再尝试数值比较
            left_str = str(left_data).replace('%', '').replace(',', '').strip()
            right_str = str(right_data).replace('%', '').replace(',', '').strip()
            left_num = float(left_str)
            right_num = float(right_str)
            result = left_num < right_num
            print(f"[DEBUG lessThan] col={col_name}, {left_data!r} vs {right_data!r} -> {left_num} < {right_num} = {result}")
            return result
        except (ValueError, TypeError):
            result = str(left_data) < str(right_data)
            print(f"[DEBUG lessThan fallback] col={col_name}, {left_data!r} vs {right_data!r} -> str={result}")
            return result
