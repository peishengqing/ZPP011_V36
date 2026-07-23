# -*- coding: utf-8 -*-
"""
DataFrame Model 和 Proxy Model
支持 pandas DataFrame 与 QTableView 的数据绑定、排序、筛选、编辑等
"""
import numpy as np
import pandas as pd
from datetime import datetime
import hashlib
from PySide6.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt, Signal, QModelIndex
from PySide6.QtGui import QColor

# 自定义角色：标记某行是否属于替代料组（代理模型据此跳过预警色覆盖，保证同组视觉一致）
ALT_GROUP_ROLE = Qt.UserRole + 100


def _make_alt_group_color(group_name: str) -> QColor:
    """根据替代料组名生成稳定的柔和色（同一个组永远同色）。"""
    hue = int(hashlib.md5(group_name.encode('utf-8')).hexdigest(), 16) % 360
    return QColor.fromHsv(hue, 50, 240)


class DataFrameModel(QAbstractTableModel):
    """将 pandas DataFrame 适配为 QAbstractTableModel"""
    dataChanged = Signal()

    def __init__(self, data: pd.DataFrame = None):
        super().__init__()
        self._data = pd.DataFrame()
        self._original_data = pd.DataFrame()
        self._data_cache = []  # 新增：缓存二维列表
        self._display_columns = []  # 记录列顺序
        self._changed_rows = set()  # 审核后变更行（位置索引集合，用于整行红标）
        self._quarantined_rows = set()  # 隔离区行（位置索引集合，用于整行黄标）
        self._substitute_rows = set()  # 替代料/非耗用行（实际=0 且 定额>0，整行浅蓝标）
        self._alt_group_color_list = []  # 替代料组行对应的组色（QColor 或 None）
        self._alert_rows = set()  # 偏差率预警行（|偏差率|>10%，整行浅红标）
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
        """将 DataFrame 转换为 Python 原生类型的二维列表，大幅提升 data() 速度。

        优化：行集合计算和缓存构建均使用向量化/NumPy，避免万行级 Python 循环。
        """
        if self._data.empty:
            self._data_cache = []
            # 空数据也要保留列名，否则 columnCount 返回 0，表格表头会消失
            self._display_columns = list(self._data.columns)
            self._changed_rows = set()
            self._quarantined_rows = set()
            self._substitute_rows = set()
            self._alt_group_color_list = []
            self._alert_rows = set()
            return

        self._display_columns = list(self._data.columns)
        n = len(self._data)

        # 1. 向量化计算特殊行集合（比逐行 iloc 快 1~2 个数量级）
        if '_post_audit_changed' in self._data.columns:
            mask = pd.to_numeric(self._data['_post_audit_changed'], errors='coerce').fillna(0).astype(int) == 1
            self._changed_rows = set(np.where(mask)[0])
        else:
            self._changed_rows = set()

        if '_quarantined' in self._data.columns:
            mask = pd.to_numeric(self._data['_quarantined'], errors='coerce').fillna(0).astype(int) == 1
            self._quarantined_rows = set(np.where(mask)[0])
        else:
            self._quarantined_rows = set()

        # 替代料/非耗用检测：实际≈0 且 定额>0
        _sub_actual_col = None
        for c in ['数量-实际', '实际']:
            if c in self._data.columns:
                _sub_actual_col = c
                break
        _sub_qty_col = None
        for c in ['数量-定额', '定额']:
            if c in self._data.columns:
                _sub_qty_col = c
                break
        if _sub_actual_col and _sub_qty_col:
            a = pd.to_numeric(self._data[_sub_actual_col], errors='coerce').fillna(0.0)
            q = pd.to_numeric(self._data[_sub_qty_col], errors='coerce').fillna(0.0)
            mask = (a.abs() <= 0.001) & (q > 0.001)
            self._substitute_rows = set(np.where(mask)[0])
        else:
            self._substitute_rows = set()

        # 偏差率预警：|偏差率| > 10% 的行整行浅红（与 EnhancedSortProxyModel 行为一致）
        _alert_rate_col = None
        for c in ['偏差率(%)', '偏差率']:
            if c in self._data.columns:
                _alert_rate_col = c
                break
        if _alert_rate_col:
            rates = pd.to_numeric(
                self._data[_alert_rate_col].astype(str).str.replace('%', '').str.strip(),
                errors='coerce').fillna(0.0)
            self._alert_rows = set(np.where(rates.abs() > 10)[0])
        else:
            self._alert_rows = set()

        # 替代料组：按 _替代料组 分组生成稳定柔和色（同组同色，便于一眼归组）
        self._alt_group_color_list = [None] * n
        if '_替代料组' in self._data.columns:
            grp = self._data['_替代料组']
            seen = {}
            for i in range(n):
                g = grp.iat[i]
                if g is None or (isinstance(g, float) and pd.isna(g)) or (isinstance(g, str) and g.strip() == ''):
                    continue
                gs = str(g)
                col = seen.get(gs)
                if col is None:
                    col = _make_alt_group_color(gs)
                    seen[gs] = col
                self._alt_group_color_list[i] = col

        # 2. 批量构建缓存：to_numpy(dtype=object) 一次把 DataFrame 转成 object 数组，
        #    再替换 NaN/None，最后把 numpy scalar 转成 Python 原生类型。
        arr = self._data.to_numpy(dtype=object)
        # 处理缺失值（NaN/None/NaT 统一替换为空字符串）
        na_mask = pd.isna(arr)
        if na_mask.any():
            arr[na_mask] = ""
        # 把 numpy scalar 转成 Python int/float，避免后续显示/比较时依赖 numpy 类型
        def _py_scalar(v):
            if isinstance(v, np.integer):
                return int(v)
            if isinstance(v, np.floating):
                return float(v)
            return v
        self._data_cache = [[_py_scalar(v) for v in row] for row in arr.tolist()]

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
            elif role == Qt.EditRole:
                return None
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            elif role == Qt.ToolTipRole:
                read_val = self._data_cache[row][0]
                return '已读' if read_val else '未读'
            elif role == ALT_GROUP_ROLE:
                if row < len(self._alt_group_color_list):
                    return self._alt_group_color_list[row] is not None
                return False
            # 其余角色（如 BackgroundRole）交给下方统一处理（含替代料组色）


        # 替代料/非耗用行：鼠标悬停显示检测依据与备注原因
        if role == Qt.ToolTipRole and row in self._substitute_rows:
            remark = ''
            for c in ['备注原因', '备注']:
                if c in self._display_columns:
                    try:
                        ridx = self._display_columns.index(c)
                        rv = self._data_cache[row][ridx]
                        remark = '' if rv is None else str(rv)
                    except Exception:
                        remark = ''
                    break
            return f"疑似替代料/非耗用：实际=0，定额>0（偏差率 -100%）\n备注原因：{remark if remark.strip() else '（无）'}"
        
        # 其余列：从缓存读取
        if role == Qt.DisplayRole or role == Qt.EditRole:
            val = self._data_cache[row][col]
            # 偏差率列：显示时加 % 后缀（匹配 偏差率(%)、净偏差率(%)、净偏差率 等）
            col_name = self._display_columns[col]
            if '偏差率' in col_name and val != "":
                try:
                    return f"{float(val):.3f}%"
                except (ValueError, TypeError):
                    return str(val)
            # 格式化浮点数
            if isinstance(val, float):
                if abs(val) >= 1000:
                    return f"{val:,.3f}"
                return f"{val:.3f}"
            return str(val) if val != "" else ""
        
        elif role == Qt.TextAlignmentRole:
            # 根据缓存中的类型判断对齐方式
            val = self._data_cache[row][col]
            if isinstance(val, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        
        elif role == ALT_GROUP_ROLE:
            # 告知代理模型：该行属于替代料组
            if row < len(self._alt_group_color_list):
                return self._alt_group_color_list[row] is not None
            return False

        elif role == Qt.BackgroundRole:
            # 替代料组：同组用同一柔和色，覆盖下面的变更/替代料/预警等标记，保证视觉归组
            if row < len(self._alt_group_color_list):
                gc = self._alt_group_color_list[row]
                if gc is not None:
                    return gc
            # 审核后变更行：整行浅红标记（优先）
            if row in self._changed_rows:
                return QColor(255, 205, 205)
            # 隔离区行：整行浅黄标记
            if row in self._quarantined_rows:
                return QColor(255, 248, 200)
            # 替代料/非耗用行：整行浅蓝标记（实际=0 且 定额>0）
            if row in self._substitute_rows:
                return QColor(205, 230, 255)
            col_name = self._display_columns[col]
            # 偏差率预警行：整行浅红标记（|偏差率| > 10%，预警列本身保留红/黄/绿标记）
            if row in self._alert_rows and col_name != '预警':
                return QColor(255, 200, 200)
            # 预警列上色
            if col_name == '预警':
                val = str(self._data_cache[row][col]).strip()
                if '🔴' in val or val == '红色预警':
                    return Qt.GlobalColor.red
                elif '🟡' in val or val == '黄色预警':
                    return Qt.GlobalColor.yellow
                elif '🟢' in val or val == '绿色预警':
                    return QColor(144, 238, 144)  # 浅绿
        
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
                
                header_text = None
                if read_col_idx == 0:
                    # _read 在第0列，不需要偏移
                    if section < len(self._data.columns):
                        header_text = str(self._data.columns[section])
                else:
                    # _read 不在第0列，需要偏移
                    data_cols = [c for c in self._data.columns if c != '_read']
                    if section - 1 < len(data_cols):
                        header_text = str(data_cols[section - 1])
                if header_text is None:
                    return str(section)
                # 将长表头分成2行显示
                return self._wrap_header(header_text)
            else:
                return str(self._data.index[section] + 1)
        return None

    def _wrap_header(self, text):
        """将长表头文字分成2行，在合适位置插入换行符"""
        if not text or len(text) <= 4:
            return text
        # 已经有括号的，在括号前换行
        if '(' in text and not text.startswith('('):
            idx = text.index('(')
            return text[:idx].rstrip() + '\n' + text[idx:]
        # 含"-"的（如 数量-定额），在"-"前换行
        if '-' in text and not text.startswith('-'):
            idx = text.index('-')
            return text[:idx].rstrip() + '\n' + text[idx:]
        # 含"金额"的较长短名，在"金额"前换行
        if '金额' in text and len(text) > 4:
            idx = text.index('金额')
            if idx > 0:
                return text[:idx].rstrip() + '\n' + text[idx:]
        # 一般长文本，从中间断开
        mid = len(text) // 2
        return text[:mid] + '\n' + text[mid:]

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
            except Exception:
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

        # 重排后必须重建显示缓存（data() 读的是缓存，否则排序后界面不刷新）
        self._build_cache()
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
        self.layoutChanged.emit()

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

            def _to_float_safe(v):
                """安全转浮点数，失败返回0"""
                try:
                    f = float(v)
                    return f if not pd.isna(f) else 0.0
                except (ValueError, TypeError):
                    return 0.0

            # 1. 精确列筛选（工厂、车间、替代料等）
            for col_name, value in self._custom_filters.items():
                if col_name.startswith('_'):   # 特殊筛选条件，稍后处理
                    continue
                if col_name not in df.columns:
                    continue
                row_val = str(row_data.get(col_name, '')).strip()
                if row_val != str(value).strip():
                    return False

            # 1.5 物料编码模糊搜索（支持逗号分隔多值，跨多个编码列 OR 匹配）
            if '_material_code' in self._custom_filters:
                code_cols = self._get_material_code_columns(df)
                if code_cols:
                    raw_query = str(self._custom_filters['_material_code']).lower()
                    queries = [q.strip() for q in raw_query.split(',') if q.strip()]
                    matched = False
                    for q in queries:
                        for col in code_cols:
                            row_val = str(row_data.get(col, '')).lower()
                            if q in row_val:
                                matched = True
                                break
                        if matched:
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

            # 1.7 物料名称模糊搜索（逗号分隔多选，子串匹配 OR）
            if '_material_names' in self._custom_filters:
                raw = self._custom_filters['_material_names']
                if raw:
                    if isinstance(raw, str):
                        queries = [q.strip().lower() for q in raw.split(',') if q.strip()]
                    else:
                        queries = [str(q).lower() for q in raw]
                    if queries:
                        name_col = self._find_material_name_column(df)
                        if name_col:
                            row_name = str(row_data.get(name_col, '')).lower()
                            matched = any(q in row_name for q in queries)
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

            # 3.5 颜色标记筛选（多选 OR：勾选任意颜色即保留匹配行）
            color_keys = [k for k in self._custom_filters if k in (
                '_changed_only', '_quarantined_only', '_substitute_only', '_plain_only')]
            if color_keys:
                # 先判定本行属于哪些颜色类别
                is_changed = row_data.get('_post_audit_changed', 0) == 1
                is_quarantined = row_data.get('_quarantined', 0) == 1

                # 替代料/非耗用判定（实际≈0 且 定额>0）
                is_substitute = False
                sub_actual_col = None
                for c in ['数量-实际', '实际']:
                    if c in df.columns:
                        sub_actual_col = c
                        break
                sub_qty_col = None
                for c in ['数量-定额', '定额']:
                    if c in df.columns:
                        sub_qty_col = c
                        break
                if sub_actual_col and sub_qty_col:
                    a_val = _to_float_safe(row_data.get(sub_actual_col, 0))
                    q_val = _to_float_safe(row_data.get(sub_qty_col, 0))
                    if abs(a_val) <= 0.001 and q_val > 0.001:
                        is_substitute = True

                is_plain = not (is_changed or is_quarantined or is_substitute)

                matched_any = False
                if '_changed_only' in color_keys and is_changed:
                    matched_any = True
                if '_quarantined_only' in color_keys and is_quarantined:
                    matched_any = True
                if '_substitute_only' in color_keys and is_substitute:
                    matched_any = True
                if '_plain_only' in color_keys and is_plain:
                    matched_any = True

                if not matched_any:
                    return False

            # 4. 备注为空
            if '_remark_empty' in self._custom_filters:
                remark_col = self._get_remark_column(df)
                if remark_col:
                    remark = row_data.get(remark_col, '')
                    is_empty = (pd.isna(remark) or str(remark).strip() == '')
                    if self._custom_filters['_remark_empty'] != is_empty:
                        return False

            # 4.1 备注关键词搜索（逗号分隔多选，OR匹配）
            if '_remark_search' in self._custom_filters:
                raw = self._custom_filters['_remark_search']
                if raw:
                    if isinstance(raw, str):
                        queries = [q.strip().lower() for q in raw.split(',') if q.strip()]
                    else:
                        queries = [str(q).lower() for q in raw]
                    if queries:
                        remark_col = self._find_remark_column(df)
                        if remark_col:
                            row_remark = str(row_data.get(remark_col, '')).lower()
                            matched = any(q in row_remark for q in queries)
                            if not matched:
                                return False

            # 4.2 备注不为（排除包含这些关键词的备注，逗号分隔多选，OR匹配）
            if '_remark_not' in self._custom_filters:
                raw = self._custom_filters['_remark_not']
                if raw:
                    if isinstance(raw, str):
                        queries = [q.strip().lower() for q in raw.split(',') if q.strip()]
                    else:
                        queries = [str(q).lower() for q in raw]
                    if queries:
                        remark_col = self._find_remark_column(df)
                        if remark_col:
                            row_remark = str(row_data.get(remark_col, '')).lower()
                            matched = any(q in row_remark for q in queries)
                            if matched:
                                return False

            # 4.5 零值筛选（定额为0 / 实际为0 / 定额/实际为0 / 定额/实际非0）
            if '_zero_qty' in self._custom_filters:
                zero_mode = self._custom_filters['_zero_qty']
                qty_col = None
                for c in ['数量-定额', '定额']:
                    if c in df.columns:
                        qty_col = c
                        break
                actual_col = None
                for c in ['数量-实际', '实际']:
                    if c in df.columns:
                        actual_col = c
                        break

                if zero_mode == '定额为0':
                    if qty_col:
                        val = _to_float_safe(row_data.get(qty_col, 0))
                        if abs(val) > 0.001:
                            return False
                    else:
                        return False  # 没有定额列，无法筛选
                elif zero_mode == '实际为0':
                    if actual_col:
                        val = _to_float_safe(row_data.get(actual_col, 0))
                        if abs(val) > 0.001:
                            return False
                    else:
                        return False
                elif zero_mode == '定额/实际为0':
                    # 定额=0 且 实际=0 才保留
                    qty_val = _to_float_safe(row_data.get(qty_col, 0)) if qty_col else 0.0
                    actual_val = _to_float_safe(row_data.get(actual_col, 0)) if actual_col else 0.0
                    if abs(qty_val) > 0.001 or abs(actual_val) > 0.001:
                        return False
                elif zero_mode == '定额/实际非0':
                    # 定额≠0 且 实际≠0 才保留
                    qty_val = _to_float_safe(row_data.get(qty_col, 0)) if qty_col else 0.0
                    actual_val = _to_float_safe(row_data.get(actual_col, 0)) if actual_col else 0.0
                    if abs(qty_val) <= 0.001 or abs(actual_val) <= 0.001:
                        return False

            # 4.5 偏差数量符号筛选（大于0 / 等于0 / 小于0）
            if '_dev_qty_sign' in self._custom_filters and '偏差数量' in df.columns:
                sign = self._custom_filters['_dev_qty_sign']
                dq = _to_float_safe(row_data.get('偏差数量', 0))
                if sign == 'gt0':
                    if dq <= 0.001:
                        return False
                elif sign == 'eq0':
                    if abs(dq) > 0.001:
                        return False
                elif sign == 'lt0':
                    if dq >= -0.001:
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
        """返回第一个命中的物料编码列（保持向后兼容）"""
        for col in ['物料号', '物料编码', 'code', '组件物料号']:
            if col in df.columns:
                return col
        return None

    def _get_material_code_columns(self, df):
        """返回所有候选的物料编码列（用于跨列模糊匹配）"""
        return [c for c in df.columns if c in ('物料号', '物料编码', 'code', '组件物料号')]

    def _find_material_name_column(self, df):
        for col in ['物料描述', '物料名称', '物料']:
            if col in df.columns:
                return col
        return None

    def _find_remark_column(self, df):
        for col in ['备注原因', '备注']:
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
