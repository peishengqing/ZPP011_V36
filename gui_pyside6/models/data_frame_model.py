# -*- coding: utf-8 -*-
"""
DataFrame Model 和 Proxy Model
支持 pandas DataFrame 与 QTableView 的数据绑定、排序、筛选、编辑等
"""
import numpy as np
import pandas as pd
from datetime import datetime
import hashlib
from PySide6.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt, Signal, QModelIndex, QTimer
from PySide6.QtGui import QColor

# 自定义角色：标记某行是否属于替代料组（代理模型据此跳过预警色覆盖，保证同组视觉一致）
ALT_GROUP_ROLE = Qt.UserRole + 100


def _make_alt_group_color(group_name: str) -> QColor:
    """根据替代料组名生成稳定的柔和色（同一个组永远同色）。"""
    hue = int(hashlib.md5(group_name.encode('utf-8')).hexdigest(), 16) % 360
    return QColor.fromHsv(hue, 50, 240)


class DataFrameModel(QAbstractTableModel):
    """将 pandas DataFrame 适配为 QAbstractTableModel"""
    # 必须与基类 QAbstractItemModel.dataChanged 保持一致（2 参：topLeft, bottomRight），
    # 否则 setData 里 emit(index, index) 会因参数个数不符抛异常被吞掉，导致编辑永远返回 False。
    dataChanged = Signal(QModelIndex, QModelIndex)
    dataRefreshed = Signal()  # 全表刷新广播：替代滥用 dataChanged 发无效索引(QModelIndex())，订阅方重算汇总/失效缓存

    def __init__(self, data: pd.DataFrame = None):
        super().__init__()
        self._data = pd.DataFrame()
        self._original_data = pd.DataFrame()
        self._data_cache = []  # 新增：缓存二维列表
        self._display_columns = []  # 记录列顺序
        self._changed_rows = set()  # 审核后变更行（位置索引集合，用于整行红标）
        self._quarantined_rows = set()  # 隔离区行（位置索引集合，用于整行黄标）
        self._substitute_rows = set()  # 替代料行（是否替代料=是，整行浅蓝标，正常被组色覆盖）
        self._alt_group_color_list = []  # 替代料组行对应的组色（QColor 或 None）
        self._unused_rows = set()  # 未投料行（实际=0 且 定额>0 且 否替代料，整行浅青绿标）
        self._alert_rows = set()  # 偏差率预警行（|偏差率|>=10% 且排除实际=0定额>0，整行浅橙标）
        if data is not None:
            self.setDataFrame(data)

    def setDataFrame(self, df: pd.DataFrame):
        self.beginResetModel()
        self._data = df.copy()

        # 确保 _read 列存在（用于已读/未读状态）
        if '_read' not in self._data.columns:
            self._data['_read'] = 0  # 默认未读
        # 确保 _read_source 列存在（已读来源：auto/manual/''）
        if '_read_source' not in self._data.columns:
            self._data['_read_source'] = ''

        # 将 _read / _read_source 列移到最前（第0列状态、第1列已读来源）
        cols = ['_read', '_read_source'] + [c for c in self._data.columns if c not in ('_read', '_read_source')]
        self._data = self._data[cols]

        self._original_data = self._data.copy()
        self._build_cache()  # 新增：构建缓存
        self.endResetModel()
        # 全表刷新广播：发自定义无参信号，不再发无效索引(QModelIndex())以免触发 Qt 警告
        self.dataRefreshed.emit()

    def mark_quarantine(self, ids, flag: bool):
        """就地更新隔离标记（不整表重置），保留主表滚动/排序/选中等视图状态。

        ids: data_id 字符串集合；flag: True=移入隔离区(1) / False=移出(0)。
        只改对应行的 _quarantined 列并同步黄标缓存，发单行 dataChanged，
        不触发 beginResetModel，故 proxy 筛选、视图滚动、列排序、选中均保留。
        """
        if self._data is None or self._data.empty:
            return
        if 'data_id' not in self._data.columns or '_quarantined' not in self._data.columns:
            return
        id_set = set(str(i) for i in ids)
        mask = self._data['data_id'].astype(str).isin(id_set)
        if not mask.any():
            return
        new_val = 1 if flag else 0
        self._data.loc[mask, '_quarantined'] = new_val
        positions = set(int(p) for p in np.where(mask.values)[0])
        if flag:
            self._quarantined_rows |= positions
        else:
            self._quarantined_rows -= positions
        # 仅发单行 dataChanged（不 beginResetModel），视图状态完全保留
        last_col = max(self.columnCount() - 1, 0)
        for pos in positions:
            self.dataChanged.emit(self.index(pos, 0), self.index(pos, last_col))

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
            self._unused_rows = set()
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

        # 替代料判定：改用分析层已算好的「是否替代料」列（基于替代料表 + 同一订单严格匹配），
        # 不再用纯数值法（实际=0 且 定额>0），后者会把未投料与真替代料混为一谈、染同一颜色。
        # 未投料（实际=0 且 定额>0 且 否替代料）单独成一类，用不同颜色区分。
        _sub_actual_col = next((c for c in ['数量-实际', '实际'] if c in self._data.columns), None)
        _sub_qty_col = next((c for c in ['数量-定额', '定额'] if c in self._data.columns), None)
        _alt_flag_col = '是否替代料' if '是否替代料' in self._data.columns else None

        # no_input：实际≈0 且 定额>0（未投料或替代料，偏差率恒为 -100%）
        if _sub_actual_col and _sub_qty_col:
            a = pd.to_numeric(self._data[_sub_actual_col], errors='coerce').fillna(0.0)
            q = pd.to_numeric(self._data[_sub_qty_col], errors='coerce').fillna(0.0)
            no_input = (a.abs() <= 0.001) & (q > 0.001)
        else:
            no_input = pd.Series(False, index=self._data.index)

        if _alt_flag_col is not None:
            is_alt = self._data[_alt_flag_col].astype(str).str.strip().eq('是')
        else:
            is_alt = pd.Series(False, index=self._data.index)
        # 替代料：有「是否替代料=是」标记（组色优先渲染，浅蓝仅兜底）
        self._substitute_rows = set(np.where(is_alt.values)[0])
        # 未投料：实际=0 定额>0 且 非替代料（没登记在替代料表）
        unused_mask = no_input & (~is_alt)
        self._unused_rows = set(np.where(unused_mask.values)[0])

        # 偏差率预警：|偏差率| >= 10% 的行整行浅橙（与偏差率预警看板阈值一致）
        # 排除「实际=0 且 定额>0」的行：偏差率恒为 -100%，是未真实投料的机械结果，不是真偏差
        _alert_rate_col = next((c for c in ['偏差率(%)', '偏差率'] if c in self._data.columns), None)
        if _alert_rate_col:
            rates = pd.to_numeric(
                self._data[_alert_rate_col].astype(str).str.replace('%', '').str.strip(),
                errors='coerce').fillna(0.0)
            alert_mask = (rates.abs() >= 10) & (~no_input)
            self._alert_rows = set(np.where(alert_mask.values)[0])
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

        # 2. 批量构建缓存：用 pandas 内置 where 按列向量化替换 NaN(比 pd.isna(N×M 数组) 快得多),
        #    然后 values.tolist() 一次性递归转 Python scalar(numpy 已自带 to-Python 转换),
        #    移除冗余的 [[_py_scalar(v) for v in row] for row in arr.tolist()] 嵌套循环
        self._data_cache = self._data.astype(object).where(self._data.notna(), "").values.tolist()

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

        # 第1列：已读来源（auto/manual/''）
        col_name = self._display_columns[col]
        if col_name == '_read_source':
            if role == Qt.DisplayRole:
                v = self._data_cache[row][col]
                if v == 'auto':
                    return '自动'
                if v == 'manual':
                    return '手动'
                return '—'
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            elif role == Qt.ToolTipRole:
                v = self._data_cache[row][col]
                return {'auto': '由自动已读规则标记已读', 'manual': '人工手动标记已读', '—': '未读'}.get(v, '未读')
            # 其余角色交给下方统一处理

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
        
        elif role == Qt.ForegroundRole:
            # 偏差数值列着色（2026-09-30）：正值红、负值绿（与看板红绿语言一致，
            # 中间调在暗/亮主题下都清晰）；0 值与空值保持默认色
            col_name = self._display_columns[col]
            if col_name in ("偏差数量", "偏差率(%)", "偏差金额", "净偏差金额"):
                try:
                    _fv = float(self._data_cache[row][col])
                except (ValueError, TypeError):
                    return None
                if _fv > 0:
                    return QColor(229, 83, 80)   # 正偏差 红
                if _fv < 0:
                    return QColor(102, 187, 106)  # 负偏差 绿
            elif col_name == "偏差区间":
                _iv = str(self._data_cache[row][col])
                if _iv == "正偏差":
                    return QColor(229, 83, 80)
                if _iv == "负偏差":
                    return QColor(102, 187, 106)
                if _iv == "零偏差":
                    return QColor(158, 158, 158)  # 零偏差 灰
            return None

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
            # 替代料/非耗用行：整行浅蓝标记（实际兜底，正常被上面组色覆盖）
            if row in self._substitute_rows:
                return QColor(205, 230, 255)
            # 未投料行：实际=0 且 定额>0 且 非替代料，整行浅青绿标记（与替代料蓝/组色明显区分）
            if row in self._unused_rows:
                return QColor(200, 240, 210)
            col_name = self._display_columns[col]
            # 偏差率预警行：整行浅橙标记（|偏差率| >= 10%，与审核后变更的浅红区分；预警列本身保留红/黄/绿标记）
            if row in self._alert_rows and col_name != '预警':
                return QColor(255, 198, 142)
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
                if section == 1:
                    return "已读来源"
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
        # 模型为只读：所有列（含备注/备注原因）均不可手动编辑，
        # 避免人工改动备注污染已读变更检测基线（备注变动仅来自 SAP 源数据）
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def setData(self, index, value, role=Qt.EditRole):
        # 模型为只读：备注列不再允许手动编辑，避免污染已读变更检测基线
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
        self._value_filters = {}  # 列名 -> 允许显示的展示值集合（Excel式列头成员过滤）
        self._value_keys = {}     # 列名 -> 每行展示值键列表（与 source 行序对齐，加速 filterAcceptsRow）
        self._alert_threshold = 10.0  # 预警阈值，默认10%
        # P2-7 修复：保留排序状态
        self._sort_column = -1
        self._sort_order = Qt.AscendingOrder
        # 筛选计划预计算（2026-10-02 性能）：filterAcceptsRow 原先每行做 pandas
        # df.iloc（17k 行一遍 ≈ 1.3s）+ 逐行列名扫描 + 逐行 pd.to_datetime（≈ 7s），
        # 主线程同步执行即 UI 卡顿。现把每个检查项在「筛选状态/数据版本变化」时
        # 一次性预计算成纯 Python 列表（_plan），逐行判定退化为 O(1) 列表访问。
        self._plan = None
        self._plan_stale = True

    def sort(self, column, order=Qt.AscendingOrder):
        """代理模型排序：保留排序偏好，交给父类用 lessThan() 处理"""
        self._sort_column = column
        self._sort_order = order
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
        self._value_filters.clear()
        self._value_keys.clear()
        self._plan = self._build_plan()
        self._plan_stale = False
        self.invalidateFilter()

    def clearHeaderFilters(self):
        """只清顶部筛选行与列头取值过滤（保留侧边栏 _custom_filters）。

        供「重置筛选」路径用：面板的 _custom_filters 已由 filter_changed 应用过，
        原先 clearFilters() + setCustomFilters() 双清双设会引发多遍全表重筛（17k 行
        一遍 1.3s+），这里无值过滤残留时完全零重筛。"""
        changed = bool(self._filters or self._value_filters or self._value_keys)
        self._filters.clear()
        self._value_filters.clear()
        self._value_keys.clear()
        if changed:
            self.invalidateFilter()

    def getCustomFilters(self):
        """当前自定义筛选条件（浅拷贝），供外部做「叠加/快照」操作。"""
        return dict(self._custom_filters)

    def setValueFilter(self, col_name, allowed_set):
        """Excel式列头成员过滤：allowed_set 为该列允许显示的展示值集合（与表格 DisplayRole
        一致的字符串）。allowed_set 为空 / None 表示清除该列过滤。设置时预计算每行展示键列表
        (_value_keys)，使 filterAcceptsRow 命中判断为 O(1)。"""
        if not allowed_set:
            self._value_filters.pop(col_name, None)
            self._value_keys.pop(col_name, None)
        else:
            sm = self.sourceModel()
            if sm is None or col_name not in getattr(sm, "_display_columns", []):
                return
            ci = sm._display_columns.index(col_name)
            n = sm.rowCount()
            keys = build_display_key_list(sm, ci)  # 向量化（与 DisplayRole 一致）
            if keys is None:
                # 兜底：非 DataFrameModel 源 / 第0列 → 原逐行路径
                keys = []
                for r in range(n):
                    disp = sm.data(sm.index(r, ci), Qt.DisplayRole)
                    keys.append("(空)" if disp in (None, "") else str(disp))
            self._value_filters[col_name] = set(allowed_set)
            self._value_keys[col_name] = keys
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
        same_dict = (self._custom_filters == filters)
        self._custom_filters = dict(filters)
        if same_dict and not self._plan_stale:
            # 同一筛选状态重复下发（如面板信号抖动）：筛选结果不变，跳过重筛与 layoutChanged
            return
        self._plan = self._build_plan()
        self._plan_stale = False
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

        # 再处理侧边栏自定义筛选（筛选计划预计算：逐行只做纯列表访问，不再逐行 pandas iloc）
        if self._custom_filters:
            self._ensure_plan()
            plan = self._plan
            n = plan.get('n', 0)
            if n:
                if source_row >= n or plan.get('reject_all'):
                    return False
                r = source_row

                # 1. 精确列筛选（工厂、车间、替代料等）
                for vals, target in plan.get('exact', ()):
                    if vals[r] != target:
                        return False

                # 2. OR 子串正组（产品码/物料编码/流程订单/物料名称/备注关键词）
                for groups, queries in plan.get('pos_groups', ()):
                    hit = False
                    for ls in groups:
                        v = ls[r]
                        for q in queries:
                            if q in v:
                                hit = True
                                break
                        if hit:
                            break
                    if not hit:
                        return False

                # 3. OR 子串负组（_remark_not：命中任一即拒）
                for groups, queries in plan.get('neg_groups', ()):
                    for ls in groups:
                        v = ls[r]
                        if any(q in v for q in queries):
                            return False

                # 4. 偏差率（NaN 保留：abs(nan) 比较恒 False → 放行，与原逐行行为一致）
                chk = plan.get('rate_abs')
                if chk is not None:
                    rate_list, thr = chk
                    if abs(rate_list[r]) < thr:
                        return False
                chk = plan.get('rate_range')
                if chk is not None:
                    rate_list, range_str = chk
                    rate_v = rate_list[r]
                    abs_rate = abs(rate_v)
                    if range_str == '绝对值>=10%':
                        ok = abs_rate >= 10
                    elif range_str == '>10%':
                        ok = abs_rate > 10
                    elif range_str == '>20%':
                        ok = abs_rate > 20
                    elif range_str == '>30%':
                        ok = abs_rate > 30
                    elif range_str == '<-10%':
                        ok = rate_v < -10
                    elif range_str == '<-20%':
                        ok = rate_v < -20
                    elif range_str == '<-30%':
                        ok = rate_v < -30
                    else:
                        ok = True
                    if not ok:
                        return False

                # 5. 已读状态 / 已读来源 / 隔离区
                chk = plan.get('read_status')
                if chk is not None:
                    mode, read_list = chk
                    if mode == '已读' and read_list[r] != 1:
                        return False
                    if mode == '未读' and read_list[r] != 0:
                        return False
                chk = plan.get('read_source')
                if chk is not None:
                    want, src_list = chk
                    if want == 'auto' and src_list[r] != 'auto':
                        return False
                    if want == 'manual' and src_list[r] != 'manual':
                        return False
                chk = plan.get('quarantined_is')
                if chk is not None:
                    want, q_list = chk
                    is_quar = (q_list[r] == 1)
                    if want == '是' and not is_quar:
                        return False
                    if want == '否' and is_quar:
                        return False

                # 6. 颜色标记（向量化预计算的逐行 key 集合，与 classify_row_color_keys 一致）
                chk = plan.get('color')
                if chk is not None:
                    active_keys, row_sets = chk
                    if not (row_sets[r] & active_keys):
                        return False

                # 7. 单位多选 / 备注为空
                chk = plan.get('units')
                if chk is not None:
                    u_list, u_set = chk
                    if u_list[r] not in u_set:
                        return False
                chk = plan.get('remark_empty')
                if chk is not None:
                    expected, flags = chk
                    if flags[r] != expected:
                        return False

                # 8. 零值 / 偏差数量符号
                chk = plan.get('zero_qty')
                if chk is not None:
                    mode, q_list, a_list = chk
                    if mode == '定额为0':
                        if abs(q_list[r]) > 0.001:
                            return False
                    elif mode == '实际为0':
                        if abs(a_list[r]) > 0.001:
                            return False
                    elif mode == '定额/实际为0':
                        if abs(q_list[r]) > 0.001 or abs(a_list[r]) > 0.001:
                            return False
                    else:  # 定额/实际非0
                        if abs(q_list[r]) <= 0.001 or abs(a_list[r]) <= 0.001:
                            return False
                chk = plan.get('dev_qty_sign')
                if chk is not None:
                    sign, dq_list = chk
                    dv = dq_list[r]
                    if sign == 'gt0' and dv <= 0.001:
                        return False
                    if sign == 'eq0' and abs(dv) > 0.001:
                        return False
                    if sign == 'lt0' and dv >= -0.001:
                        return False

                # 9. 半成品重分类集合
                chk = plan.get('semi_class')
                if chk is not None:
                    sset, semi_list, fac_list = chk
                    row_val = semi_list[r]
                    factory = fac_list[r]
                    matched = False
                    for m in sset:
                        if m == '食品成品半成品':
                            if ((row_val == m) or row_val == '') and '食品' in factory:
                                matched = True
                                break
                        elif m == '饮料成品半成品':
                            if ((row_val == m) or row_val == '') and '饮料' in factory:
                                matched = True
                                break
                        else:
                            if row_val == m:
                                matched = True
                                break
                    if not matched:
                        return False

                # 10. 日期范围（无效日期行：原 except 放行）
                chk = plan.get('date')
                if chk is not None:
                    d_list, start_d, end_d = chk
                    d = d_list[r]
                    if d is not None:
                        if start_d and d < start_d:
                            return False
                        if end_d and d > end_d:
                            return False

        # Excel式列头取值成员过滤（与 _filters/_custom_filters AND 叠加）
        if self._value_filters:
            for col_name, allowed in self._value_filters.items():
                keys = self._value_keys.get(col_name)
                if not keys:
                    continue
                if source_row >= len(keys):
                    continue
                if keys[source_row] not in allowed:
                    return False

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

    def _get_product_code_columns(self, df):
        """返回所有候选的产品物料号码列（成品/母件编码，用于跨列模糊匹配）"""
        return [c for c in df.columns if c in ('产品物料号码', '产品物料号', '产品编码', '成品编码')]

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
        self._mark_plan_stale()  # 阈值参与偏差率/颜色检查的预计算，需重建计划

    # ------------------------------------------------------------------ #
    # 筛选计划（预计算）：把逐行 pandas 访问换成纯 Python 列表 O(1) 判定
    # ------------------------------------------------------------------ #
    def _mark_plan_stale(self):
        self._plan_stale = True

    def _ensure_plan(self):
        if self._plan_stale:
            self._plan = self._build_plan()
            self._plan_stale = False

    def setSourceModel(self, model):
        """挂源模型时把「数据版本变化」接成计划失效信号。

        PySide6 不暴露 QSortFilterProxyModel 的 sourceModelAboutToBeReset 等
        C++ 内部虚函数（无法 override），源模型换数据的可靠路径只有 Qt 信号：
          - modelAboutToBeReset / modelReset：begin/endResetModel（setDataFrame 整表换版）
          - dataChanged：单格就地更新（mark_quarantine 等）
          - rowsInserted / rowsRemoved：行增删
          - dataRefreshed（DataFrameModel 自定义）：全表刷新广播
        全部 → _mark_plan_stale，保证下次筛选 pass 前计划按新数据重建。
        """
        super().setSourceModel(model)
        self._mark_plan_stale()
        if model is None:
            return
        signals = []
        for name in ("modelAboutToBeReset", "modelReset", "dataChanged",
                     "rowsInserted", "rowsRemoved"):
            sig = getattr(model, name, None)
            if sig is not None:
                signals.append(sig)
        if hasattr(model, "dataRefreshed"):
            signals.append(model.dataRefreshed)
        for sig in signals:
            try:
                sig.connect(self._mark_plan_stale)
            except Exception:
                pass

    def _build_plan(self):
        """把当前筛选条件预计算成逐行纯 Python 列表（一次），供 filterAcceptsRow O(1) 访问。

        语义与原逐行实现严格一致（含「列缺失即整列拒绝」等边界行为）：
          - _process_order：查询非空但候选列都不存在 → 所有行拒绝（空列组的 OR 子串恒 False）
          - _zero_qty：「定额为0」缺数量列 / 「实际为0」缺实际列 → 所有行拒绝
          - 偏差率 NaN 行：abs 判定 `abs(nan) < thr` 恒 False → 放行；区间判定 NaN 比较
            恒 False → 拒绝（与 _check_rate_range 对 nan 的行为一致），故 NaN 保留不 fill
        """
        sm = self.sourceModel()
        df = sm.getDataFrame() if sm is not None else None
        cf = self._custom_filters
        if df is None or df.empty:
            return {'n': 0}
        n = len(df)
        cols = df.columns
        plan = {'n': n}

        # 按需取列值缓存（同一计划内复用，避免重复 tolist）
        _cache = {}

        def _raw(col):
            if col not in _cache:
                _cache[col] = df[col].tolist()
            return _cache[col]

        def _str_lower(col):
            key = ('L', col)
            if key not in _cache:
                _cache[key] = [str(v).lower() for v in _raw(col)]
            return _cache[key]

        def _str_strip(col):
            key = ('S', col)
            if key not in _cache:
                _cache[key] = [str(v).strip() for v in _raw(col)]
            return _cache[key]

        def _safe_floats(col):
            """逐行 _to_float_safe 语义：float(v)，NaN/异常 → 0.0"""
            key = ('F', col)
            if key not in _cache:
                _cache[key] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).tolist()
            return _cache[key]

        # 1. 精确列筛选（普通列名，非 _ 前缀）
        exact = []
        for col_name, value in cf.items():
            if col_name.startswith('_') or col_name not in cols:
                continue
            exact.append((_str_strip(col_name), str(value).strip()))
        plan['exact'] = exact

        # 2. OR 子串正组：([各列小写列表], queries)；列组为空时该行恒拒绝（与原一致）
        pos_groups = []

        def _q_lower(rawq):
            return [q.strip().lower() for q in str(rawq).lower().split(',') if q.strip()]

        # 注意：内层必须立即求值成 list（逐行会反复遍历该组），不能用生成器表达式
        pc_cols = [c for c in cols if c in ('产品物料号码', '产品物料号', '产品编码', '成品编码')]
        if '_product_code' in cf and pc_cols:
            pos_groups.append([[_str_lower(c) for c in pc_cols], _q_lower(cf['_product_code'])])
        mc_cols = [c for c in cols if c in ('物料号', '物料编码', 'code', '组件物料号')]
        if '_material_code' in cf and mc_cols:
            pos_groups.append([[_str_lower(c) for c in mc_cols], _q_lower(cf['_material_code'])])
        if '_process_order' in cf:
            po_q = [q.strip().lower() for q in str(cf['_process_order']).split(',') if q.strip()]
            if po_q:
                po_cols = [c for c in ('流程订单', 'process_order') if c in cols]
                pos_groups.append([[_str_lower(c) for c in po_cols], po_q])
        raw_names = cf.get('_material_names')
        if raw_names:
            if isinstance(raw_names, str):
                nq = [q.strip().lower() for q in raw_names.split(',') if q.strip()]
            else:
                nq = [str(q).lower() for q in raw_names]
            if nq:
                name_col = next((c for c in ('物料描述', '物料名称', '物料') if c in cols), None)
                if name_col:
                    pos_groups.append([(_str_lower(name_col),), nq])
        raw_rs = cf.get('_remark_search')
        if raw_rs:
            if isinstance(raw_rs, str):
                rsq = [q.strip().lower() for q in raw_rs.split(',') if q.strip()]
            else:
                rsq = [str(q).lower() for q in raw_rs]
            if rsq:
                rem_col = next((c for c in ('备注原因', '备注') if c in cols), None)
                if rem_col:
                    pos_groups.append([(_str_lower(rem_col),), rsq])
        plan['pos_groups'] = pos_groups

        # 3. OR 子串负组（_remark_not：命中任一即拒；缺备注列则无约束，与原一致）
        neg_groups = []
        raw_not = cf.get('_remark_not')
        if raw_not:
            if isinstance(raw_not, str):
                nq = [q.strip().lower() for q in raw_not.split(',') if q.strip()]
            else:
                nq = [str(q).lower() for q in raw_not]
            if nq:
                rem_col = next((c for c in ('备注原因', '备注') if c in cols), None)
                if rem_col:
                    neg_groups.append([(_str_lower(rem_col),), nq])
        plan['neg_groups'] = neg_groups

        # 4. 偏差率（NaN 保留：abs(nan)<thr 恒 False → 放行；区间判定 NaN → 拒，与原一致）
        rate_col = next((c for c in ('偏差率(%)', '偏差率') if c in cols), None)
        rate_list = None
        if rate_col is not None and ('_dev_rate_abs_ge_10' in cf or '_dev_rate_range' in cf):
            rate_list = pd.to_numeric(
                df[rate_col].astype(str).str.replace('%', ''),
                errors='coerce').tolist()
        if '_dev_rate_abs_ge_10' in cf and rate_list is not None:
            plan['rate_abs'] = (rate_list, self._alert_threshold)
        if '_dev_rate_range' in cf and rate_list is not None:
            plan['rate_range'] = (rate_list, cf['_dev_rate_range'])

        # 5. 已读状态 / 已读来源 / 隔离区（缺列 → 原实现默认 0 / ''，此处同）
        if '_read_status' in cf:
            read_vals = _raw('_read') if '_read' in cols else [0] * n
            plan['read_status'] = (cf['_read_status'], read_vals)
        if '_read_source' in cf:
            src_vals = _raw('_read_source') if '_read_source' in cols else [''] * n
            plan['read_source'] = (cf['_read_source'], src_vals)
        if '_quarantined_is' in cf:
            q_vals = _raw('_quarantined') if '_quarantined' in cols else [0] * n
            plan['quarantined_is'] = (cf['_quarantined_is'], q_vals)

        # 6. 颜色标记（复现 classify_row_color_keys 的向量化判定；仅在有颜色键时构建）
        color_keys = {k for k in cf if k in (
            '_changed_only', '_quarantined_only', '_substitute_only',
            '_unused_only', '_alert_only', '_plain_only')}
        if color_keys:
            idx = df.index
            thr = self._alert_threshold

            def _flag(col):
                if col in cols:
                    return pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int).eq(1)
                return pd.Series(False, index=idx)

            changed = _flag('_post_audit_changed')
            quar = _flag('_quarantined')
            if '是否替代料' in cols:
                sub = df['是否替代料'].astype(str).str.strip().eq('是')
            else:
                sub = pd.Series(False, index=idx)
            act_col = next((c for c in ('数量-实际', '实际') if c in cols), None)
            std_col = next((c for c in ('数量-定额', '定额') if c in cols), None)
            a = pd.to_numeric(df[act_col], errors='coerce').fillna(0.0) if act_col else pd.Series(0.0, index=idx)
            q = pd.to_numeric(df[std_col], errors='coerce').fillna(0.0) if std_col else pd.Series(0.0, index=idx)
            no_input = (a.abs() <= 0.001) & (q > 0.001)
            unused = no_input & (~sub)
            c_rate_col = next((c for c in ('偏差率(%)', '偏差率') if c in cols), None)
            if c_rate_col:
                rv = pd.to_numeric(
                    df[c_rate_col].astype(str).str.replace('%', '').str.strip(),
                    errors='coerce')  # NaN 保留：abs(nan)>=thr 恒 False → 不告警（与原一致）
                alert = (rv.abs() >= thr) & (~no_input) & (~changed) & (~quar)
            else:
                alert = pd.Series(False, index=idx)
            plain = ~(changed | quar | sub | unused | alert)
            ch_v, qu_v, su_v, us_v, al_v, pl_v = (
                m.values for m in (changed, quar, sub, unused, alert, plain))
            row_sets = []
            for i in range(n):
                s = set()
                if ch_v[i]:
                    s.add('_changed_only')
                if qu_v[i]:
                    s.add('_quarantined_only')
                if su_v[i]:
                    s.add('_substitute_only')
                if us_v[i]:
                    s.add('_unused_only')
                if al_v[i]:
                    s.add('_alert_only')
                if pl_v[i]:
                    s.add('_plain_only')
                row_sets.append(s)
            plan['color'] = (color_keys, row_sets)

        # 7. 单位多选（缺列 → 原实现无约束）
        if '_units' in cf:
            unit_col, units_set = cf['_units']
            if unit_col and unit_col in cols:
                plan['units'] = (_str_strip(unit_col), set(units_set))

        # 8. 备注为空
        if '_remark_empty' in cf:
            rem_col = next((c for c in ('备注原因', '备注') if c in cols), None)
            if rem_col:
                flags = (df[rem_col].isna() | df[rem_col].astype(str).str.strip().eq('')).tolist()
                plan['remark_empty'] = (bool(cf['_remark_empty']), flags)

        # 9. 零值筛选（「定额为0」缺数量列 / 「实际为0」缺实际列 → 整列拒绝，与原一致）
        zq_mode = cf.get('_zero_qty')
        if zq_mode:
            qty_col = next((c for c in ('数量-定额', '定额') if c in cols), None)
            actual_col = next((c for c in ('数量-实际', '实际') if c in cols), None)
            q_list = _safe_floats(qty_col) if qty_col else [0.0] * n
            a_list = _safe_floats(actual_col) if actual_col else [0.0] * n
            reject_all = (zq_mode == '定额为0' and qty_col is None) or \
                        (zq_mode == '实际为0' and actual_col is None)
            if reject_all:
                plan['reject_all'] = True
            plan['zero_qty'] = (zq_mode, q_list, a_list)

        # 10. 偏差数量符号（缺「偏差数量」列 → 原实现无约束）
        if '_dev_qty_sign' in cf and '偏差数量' in cols:
            plan['dev_qty_sign'] = (cf['_dev_qty_sign'], _safe_floats('偏差数量'))

        # 11. 半成品重分类集合（缺列 → 原实现无约束；工厂缺列 → 原实现默认 ''）
        sset = cf.get('_semi_class_set')
        if sset:
            if '半成品重分类' in cols:
                fac_list = _str_strip('工厂') if '工厂' in cols else [''] * n
                plan['semi_class'] = (set(sset), _str_strip('半成品重分类'), fac_list)

        # 12. 日期范围（向量化 to_datetime；无效值 → 原 except 放行）
        if '_date_start' in cf or '_date_end' in cf:
            date_col = next((c for c in ('订单日期', '订单开始日期', '日期') if c in cols), None)
            if date_col:
                ts = pd.to_datetime(_raw(date_col), errors='coerce')
                date_list = [d.date() if pd.notna(d) else None for d in ts]
                start_d = end_d = None
                if cf.get('_date_start'):
                    try:
                        start_d = datetime.strptime(cf['_date_start'], "%Y-%m-%d").date()
                    except Exception:
                        start_d = None
                if cf.get('_date_end'):
                    try:
                        end_d = datetime.strptime(cf['_date_end'], "%Y-%m-%d").date()
                    except Exception:
                        end_d = None
                plan['date'] = (date_list, start_d, end_d)
        return plan

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
        # 性能：本函数在排序时被调用 N·logN 次（13904 行约 19 万次），
        # 内部严禁 print / headerData() 等额外调用，否则点列头排序会卡死。
        left_data = self.sourceModel().data(left, Qt.DisplayRole)
        right_data = self.sourceModel().data(right, Qt.DisplayRole)
        try:
            # 去掉 % 和逗号，再尝试数值比较
            left_str = str(left_data).replace('%', '').replace(',', '').strip()
            right_str = str(right_data).replace('%', '').replace(',', '').strip()
            return float(left_str) < float(right_str)
        except (ValueError, TypeError):
            return str(left_data) < str(right_data)

def classify_row_color_keys(row_data, df, threshold=10.0):
    """返回该行命中的颜色标记 key 集合，与主表行背景色/偏差率预警看板判定完全一致。

    颜色类别：
      _changed_only     审核后变更
      _quarantined_only 隔离区
      _substitute_only  替代料
      _unused_only      未投料（实际=0 定额>0 且非替代料）
      _alert_only       偏差率预警（|偏差率|>=threshold 且非未投料/非被覆盖行）
      _plain_only       无标记（五类皆非）
    """
    def _to_float_safe(v):
        try:
            f = float(v)
            return f if not pd.isna(f) else 0.0
        except (ValueError, TypeError):
            return 0.0

    is_changed = row_data.get('_post_audit_changed', 0) == 1
    is_quarantined = row_data.get('_quarantined', 0) == 1

    # 替代料：分析层「是否替代料」列（替代料表 + 同一订单），不再纯数值判定
    is_substitute = (str(row_data.get('是否替代料', '')).strip() == '是') if '是否替代料' in df.columns else False

    a_val = 0.0
    q_val = 0.0
    for c in ['数量-实际', '实际']:
        if c in df.columns:
            a_val = _to_float_safe(row_data.get(c, 0))
            break
    for c in ['数量-定额', '定额']:
        if c in df.columns:
            q_val = _to_float_safe(row_data.get(c, 0))
            break
    no_input = (abs(a_val) <= 0.001) and (q_val > 0.001)

    # 未投料：实际=0 定额>0 且 非替代料
    is_unused = no_input and not is_substitute

    is_alert = False
    alert_rate_col = None
    for c in ['偏差率(%)', '偏差率']:
        if c in df.columns:
            alert_rate_col = c
            break
    if alert_rate_col:
        rv_raw = row_data.get(alert_rate_col, 0)
        try:
            rv = float(str(rv_raw).replace('%', '').strip())
        except (ValueError, TypeError):
            rv = 0.0
        if abs(rv) >= threshold and not no_input and not (is_changed or is_quarantined):
            is_alert = True

    is_plain = not (is_changed or is_quarantined or is_substitute or is_unused or is_alert)

    keys = set()
    if is_changed:
        keys.add('_changed_only')
    if is_quarantined:
        keys.add('_quarantined_only')
    if is_substitute:
        keys.add('_substitute_only')
    if is_unused:
        keys.add('_unused_only')
    if is_alert:
        keys.add('_alert_only')
    if is_plain:
        keys.add('_plain_only')
    return keys


def build_display_key_list(sm, col_index):
    """批量生成某列的展示值键列表（与表格 DisplayRole + 「(空)」占位 完全一致）。

    性能（2026-10-02）：原实现逐行 sm.data()（C++↔Python 桥 + QModelIndex，
    1.7万行 ≈ 0.15s，漏斗确定/弹层打开时的卡顿点）。现直接读 DataFrameModel 的
    _data_cache 列缓存 + 与 data() 完全相同的格式化规则纯 Python 向量化处理
    （≈ 0.02s）。源模型非 DataFrameModel / 第0列（已读图标）时返回 None，
    调用方回退原逐行路径。
    """
    cache = getattr(sm, "_data_cache", None)
    display_cols = getattr(sm, "_display_columns", None)
    if cache is None or display_cols is None or col_index >= len(display_cols):
        return None
    if col_index == 0:
        return None  # 第0列是已读图标（✅/🔘），极少作为筛选列，走逐行兜底
    n = len(cache)
    col = display_cols[col_index]
    col_vals = [row[col_index] for row in cache]
    if col == '_read_source':
        # 与 data() 一致：auto→自动 / manual→手动 / 其他→—
        keys = [
            "自动" if v == "auto" else ("手动" if v == "manual" else "—")
            for v in col_vals
        ]
    elif '偏差率' in col:
        # 与 data() 一致：非空值加 % 后缀（.3f），格式失败原样字符串
        def _fmt_rate(v):
            if v == "":
                return ""
            try:
                return f"{float(v):.3f}%"
            except (ValueError, TypeError):
                return str(v)
        keys = [_fmt_rate(v) for v in col_vals]
    else:
        # 与 data() 一致：float 千分位/.3f；其他原样；空值 → ""
        def _fmt_plain(v):
            if isinstance(v, float):
                if abs(v) >= 1000:
                    return f"{v:,.3f}"
                return f"{v:.3f}"
            return str(v) if v != "" else ""
        keys = [_fmt_plain(v) for v in col_vals]
    return ["(空)" if k in (None, "") else str(k) for k in keys]