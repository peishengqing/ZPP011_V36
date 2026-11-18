# -*- coding: utf-8 -*-
"""
看板列顺序配置管理（v43.393）

为各看板保存/恢复用户拖拽后的列顺序。每个看板用英文 key 标识，
配置统一落盘 %APPDATA%\\ZPP011\\board_layouts.json：
    { "unfed": ["订单日期", "流程订单", ...], "neg_loss": [...] }

设计要点：
- 保存时机 = 用户拖动列头（sectionMoved 信号），不在每次渲染后回写，
  避免把「刚 setDataFrame 的默认顺序」覆盖掉已保存的自定义顺序。
- 恢复时机 = 每次 setDataFrame 之后（_after_render），用 visualIndex/moveSection
  在视觉索引层搬移；保存里没有的新增列按当前顺序殿后，已删除列忽略。
- 原子写：先写 .tmp 再 os.replace，防止写一半被读。
"""

import os
import json

BOARD_CONFIG_DIR = os.environ.get("ZPP011_CONFIG_DIR") or os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"), "ZPP011")
BOARD_CONFIG_PATH = os.path.join(BOARD_CONFIG_DIR, "board_layouts.json")


class BoardLayoutManager:
    """各看板列顺序持久化（v43.393）。JSON 结构：{board_key: [列名,...]}"""

    @staticmethod
    def _read_all():
        try:
            if os.path.exists(BOARD_CONFIG_PATH):
                with open(BOARD_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    @staticmethod
    def _write_all(data):
        try:
            os.makedirs(BOARD_CONFIG_DIR, exist_ok=True)
            tmp = BOARD_CONFIG_PATH + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, BOARD_CONFIG_PATH)
        except Exception:
            pass

    @classmethod
    def load_board_order(cls, board_key):
        """取某看板保存的列名顺序；无保存记录返回 None。"""
        if not board_key:
            return None
        order = cls._read_all().get(board_key)
        return list(order) if isinstance(order, list) and order else None

    @classmethod
    def save_board_order(cls, board_key, col_names):
        """保存某看板当前列名顺序（读-改-写，不影响其它看板条目）。"""
        if not board_key or not col_names:
            return
        data = cls._read_all()
        data[board_key] = list(col_names)
        cls._write_all(data)

    @staticmethod
    def current_column_order(table_view):
        """读 QTableView/QTableWidget 当前视觉顺序的列名列表。

        必须按 header.visualIndex 排序遍历：逻辑列号恒等于 DataFrame 列序，
        不随用户拖动变化；直接按 0..n-1 遍历会把「初始顺序」存盘（冒烟实踩）。
        """
        model = table_view.model()
        if model is None:
            return []
        header = table_view.horizontalHeader()
        names = []
        for col in sorted(range(model.columnCount()),
                          key=lambda c: header.visualIndex(c)):
            hdr = model.headerData(col, header.orientation())
            if hdr:
                names.append(str(hdr).replace('\n', ''))
        return names

    @staticmethod
    def restore_column_order(table_view, saved_order):
        """按保存的列名顺序重排任意 QTableView/QTableWidget 的列。

        - saved 中仍存在的列按 saved 顺序排在前；
        - 保存后新增的列按当前视觉顺序殿后（不会丢列）；
        - saved 里已不存在的列忽略。
        """
        if not saved_order:
            return
        model = table_view.model()
        if model is None:
            return
        header = table_view.horizontalHeader()
        n = model.columnCount()
        if n == 0:
            return
        name_of = {}
        for col in range(n):
            hdr = model.headerData(col, header.orientation())
            if hdr:
                name_of[col] = str(hdr).replace('\n', '')
        present = set(name_of.values())
        wanted = [nm for nm in saved_order if nm in present]
        if not wanted:
            return
        wanted_set = set(wanted)
        # 当前视觉顺序的 logical 列号（小→大）
        vis_cols = sorted(range(n), key=lambda c: header.visualIndex(c))
        rest = [name_of[c] for c in vis_cols if name_of[c] not in wanted_set]
        target_names = wanted + rest
        # logical 列号 → 列名（重名取首个）
        name_to_logical = {}
        for c, nm in name_of.items():
            name_to_logical.setdefault(nm, c)
        # 从左往右：把目标列从它当前视觉位置搬到位置 i；i 之前已就位不受影响。
        # 搬移期间屏蔽表头信号：防止 moveSection 触发 sectionMoved 反向写盘，
        # 把恢复过程中的中间状态当成用户拖拽存下来。
        name_to_logical = {}
        for c, nm in name_of.items():
            name_to_logical.setdefault(nm, c)
        header.blockSignals(True)
        try:
            for i, nm in enumerate(target_names):
                logical = name_to_logical.get(nm)
                if logical is None:
                    continue
                vi = header.visualIndex(logical)
                if vi != i:
                    header.moveSection(vi, i)
        finally:
            header.blockSignals(False)
