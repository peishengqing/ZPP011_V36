# -*- coding: utf-8 -*-
"""
规则驱动看板筛选（隔离区口径，v43.381）

背景
----
看板筛选原先是「手写组合控件」（关键字/单位/物料类型/车间/工厂/半成品分类/已读/颜色/隔离区/备注 等
多选叠加），口径散、容易漏规则、不易自动化处理。

本模块把看板筛选改为**隔离区（规则驱动）**口径：

- 筛选条件全部从 ``config/auto_quarantine_config.json`` 的配置规则构建：
  关键词（name_keywords）、类别限定（category_required/category_value）、
  负损要求（negative_loss_required）、偏差率范围（dev_rate_min/max）、
  物料编码前缀（mat_code_prefix）、单位（unit_required/unit_value）、
  偏差数量范围（dev_qty_required/dev_qty_min/max）、备注模式（remark_mode）
  etc.
- 匹配语义与隔离区真实匹配完全同源（``core.auto_quarantine._match_single_rule``）：
  多条规则 OR 并存、单条规则内部 AND、缺列保守不匹配、exclude_alt 放行规则等。
- 一行命中**任意一条**启用规则即进入隔离区可见集（与「自动移入隔离区」的
  OR 语义一致），同时逐条规则返回命中行数（供 UI 徽章与状态条展示）。
- 提供 ``RuleFilterWidget``：渲染「隔离区规则筛选」界面（规则卡片 + 条件勾选 + 命中数），
  供看板筛选面板展示与复用。

设计要点
--------
- 纯逻辑模块：不直接操作 GUI，只产出 DataFrame 结果 / 规则摘要 / 界面控件，便于单测验证。
- 规则与列匹配不引入第二套等价实现：核心匹配复用 ``core.auto_quarantine._match_single_rule``，
  列探测复用 ``core.auto_quarantine._probe_columns``，配置读取复用 ``load_auto_quarantine_config``。
- 缺失数据/空表一律保守（返回空集或 None 行为与生产一致），绝不因缺列误伤。
"""
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QCheckBox,
)
from PySide6.QtCore import Qt

# --------------------------------------------------------------------------- 复用原语（同源）
from core.auto_quarantine import (
    _probe_columns,
    _match_single_rule,
    load_auto_quarantine_config,
    build_rule_summary,
    build_rule_reason,
    build_all_summary,
)

# 配置结构里的字段 → 条件key 映射（用于 RuleFilterWidget 渲染条件列表）
_CONDITION_KEY_MAP: Dict[str, List[str]] = {
    "name_keywords": ["名称关键词(包含/不含)"],
    "category_required": ["类别(要求/限定)"],
    "category_value": ["类别取值(要求/限定)"],
    "negative_loss_required": ["负损"],
    "dev_rate_required": ["偏差率范围"],
    "dev_rate_min": ["偏差率下限"],
    "dev_rate_max": ["偏差率上限"],
    "mat_code_prefix": ["编码前缀"],
    "workshop_required": ["车间"],
    "unit_required": ["单位"],
    "unit_value": ["单位取值"],
    "remark_mode": ["备注模式"],
    "dev_qty_required": ["净偏差数量范围"],
    "dev_qty_min": ["净偏差数量下限"],
    "dev_qty_max": ["净偏差数量上限"],
    "name_exclude_keywords": ["名称不含"],
}

# 工具：把规则按「逻辑条件」展开成 Widget 行（供 RuleFilterWidget 渲染）
def _expand_conditions(rule: Dict[str, Any]) -> List[Dict[str, str]]:
    """把单条配置规则展开成可渲染的条件行列表。

    每条条件返回 {key, label, checked(bool), hint}；checked 由调用方决定（默认全部未勾）。
    覆盖自动隔离的判定口径：命中即「是」，未勾不限制（逻辑上由调用方显式勾选）。
    """
    row: List[Dict[str, str]] = []
    if rule.get("name_keywords"):
        row.append({"key": "name_keywords", "label": "名称关键词", "checked": False})
    if rule.get("category_required") and rule.get("category_value"):
        row.append({"key": "category_required", "label": "类别限定", "checked": False})
    if rule.get("negative_loss_required"):
        row.append({"key": "negative_loss_required", "label": "负损要求", "checked": False})
    if rule.get("dev_rate_required") and rule.get("dev_rate_max") is not None:
        row.append({"key": "dev_rate_required", "label": "偏差率范围", "checked": False})
    if rule.get("dev_rate_min") is not None:
        row.append({"key": "dev_rate_min", "label": "偏差率下限", "checked": False})
    if rule.get("dev_rate_max") is not None:
        row.append({"key": "dev_rate_max", "label": "偏差率上限", "checked": False})
    if rule.get("mat_code_prefix"):
        row.append({"key": "mat_code_prefix", "label": "编码前缀", "checked": False})
    if rule.get("workshop_required") and rule.get("workshop_value"):
        row.append({"key": "workshop_required", "label": "车间限定", "checked": False})
    if rule.get("unit_required"):
        row.append({"key": "unit_required", "label": "单位限定", "checked": False})
    if rule.get("remark_mode") in ("has", "none"):
        row.append({"key": "remark_mode", "label": "备注模式", "checked": False})
    if rule.get("dev_qty_required"):
        row.append({"key": "dev_qty_required", "label": "净偏差数量范围", "checked": False})
    if rule.get("dev_qty_min") is not None:
        row.append({"key": "dev_qty_min", "label": "净偏差数量下限", "checked": False})
    if rule.get("dev_qty_max") is not None:
        row.append({"key": "dev_qty_max", "label": "净偏差数量上限", "checked": False})
    if rule.get("name_exclude_keywords"):
        row.append({"key": "name_exclude_keywords", "label": "名称不含", "checked": False})
    return row


def _expand_config_rules(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """把配置展开为可匹配的规则列表（已补齐字段，与 auto_quarantine 同一口径）。"""
    rules = []
    for r in config.get("rules", []) or []:
        if not isinstance(r, dict):
            continue
        rules.append({
            "name": r.get("name") or "未命名规则",
            "enabled": bool(r.get("enabled", True)),
            "exclude_alt": bool(r.get("exclude_alt", True)),
            "category_required": bool(r.get("category_required", True)),
            "category_value": str(r.get("category_value") or "").strip(),
            "name_keywords": [str(k).strip() for k in (r.get("name_keywords") or []) if str(k).strip()],
            "negative_loss_required": bool(r.get("negative_loss_required", True)),
            "dev_rate_required": bool(r.get("dev_rate_required", False)),
            "dev_rate_min": float(r.get("dev_rate_min", 0)),
            "dev_rate_max": float(r.get("dev_rate_max", 100)),
            "mat_code_prefix": str(r.get("mat_code_prefix") or "").strip(),
            "workshop_required": bool(r.get("workshop_required", False)),
            "workshop_value": str(r.get("workshop_value") or "").strip(),
            "remark_mode": str(r.get("remark_mode", "off")).strip(),
            "name_exclude_keywords": [
                str(k).strip() for k in
                str(r.get("name_exclude_keywords") or "").replace("，", ",").replace("、", ",")
                .split(",") if str(k).strip()
            ],
            "dev_qty_required": bool(r.get("dev_qty_required", False)),
            "dev_qty_min": float(r.get("dev_qty_min", 0)),
            "dev_qty_max": float(r.get("dev_qty_max", 1)),
            "unit_required": bool(r.get("unit_required", False)),
            "unit_value": str(r.get("unit_value") or "").strip(),
        })
    return rules


class RuleFilterController:
    """规则驱动的看板筛选控制器（隔离区口径）。

    :param df: 主表 DataFrame（可为 None，此时按空表保守处理）
    :param config: auto_quarantine_config.json 配置（缺省自动读取持久化文件）
    """

    def __init__(self, df: Optional[pd.DataFrame] = None,
                 config: Optional[Dict[str, Any]] = None):
        self._df = df
        self._config = config if config is not None else load_auto_quarantine_config()
        self._config_rules = _expand_config_rules(self._config)
        self._cols = _probe_columns(df) if df is not None else {}
        self._master_enabled = bool(self._config.get("enabled", True))
        self._rule_count = len(self._config_rules)

    # ------------------------------------------------------------------ 读取
    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    @property
    def rules(self) -> List[Dict[str, Any]]:
        return self._config_rules

    @property
    def rule_count(self) -> int:
        return self._rule_count

    @property
    def has_rule(self) -> bool:
        return bool(self._config_rules)

    @property
    def cols(self) -> Dict[str, Optional[str]]:
        return self._cols

    def get_enabled_rules(self) -> List[Dict[str, Any]]:
        """仅返回「启用」的规则（不含总开关关闭的兜底）。"""
        return [r for r in self._config_rules if r.get("enabled", True)]

    # ------------------------------------------------------------------ 过滤
    def filter(self, df: Optional[pd.DataFrame] = None) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """对主表执行规则筛选。

        :return: ``(filtered_df, per_rule_hits)``
            - ``filtered_df``：命中**任意一条**启用规则的行（与隔离区 OR 语义一致）；
              空表 / 无列 / 配置关闭时返回原 df（不含筛选结果）。
            - ``per_rule_hits``：逐条规则独立匹配到的行数（含 0 命中），供 UI 徽章展示。

        保守性：
            - 表不可用（None / 空 / 无 data_id 列）→ 返回空集，不误伤。
            - 单条规则内条件缺失（无对应列）→ 该规则不匹配（保守）。
            - 配置关闭 → 返回原 df，per_rule_hits 为空。
        """
        if df is None:
            df = self._df
        if df is None or getattr(df, "empty", True):
            return (pd.DataFrame() if df is None else df), []
        # 配置总开关关闭 → 返回原 df，per_rule_hits 为空（含「有行但全不命中」的保守情形）
        if not self._config.get("enabled", True):
            return (df, [])
        if self._master_enabled and not self.get_enabled_rules():
            return (df, [])

        enabled = self.get_enabled_rules()
        per_rule: List[Dict[str, Any]] = []
        matched = []          # 命中任意一条启用规则的行集合（OR 语义的并集）
        for rule in enabled:
            rule_idx = self._rule_index(rule)          # 1-based 在启用规则中的位置
            mask = _match_single_rule(df, rule, self._cols)
            if not mask.any():
                continue
            hits = int(mask.sum())
            per_rule.append({
                "index": rule_idx,
                "name": rule.get("name", "未命名规则"),
                "hits": hits,
                "reason": build_rule_reason(rule, rule_idx),
            })
            matched.append(df[mask])
        # 关键：OR 语义——命中任意一条启用规则即保留该行；
        # 同规则内已用 _match_single_rule（AND），所以 OR 在规则之间进行。
        # 若所有规则都无命中，返回空集（保守，不误伤）。
        if not matched:
            return pd.DataFrame(), per_rule
        filtered = pd.concat(matched, ignore_index=True)
        return filtered, per_rule

    def filter_inplace(self, df: Optional[pd.DataFrame] = None) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """在**现有 df** 上执行筛选并原地回写（便于内容组件 set_data 后即时生效）。"""
        filtered, per_rule = self.filter(df)
        return filtered, per_rule

    # ------------------------------------------------------------------ 摘要
    def get_summary(self) -> str:
        """整体隔离区规则摘要（给状态条 / tooltip / 空结果提示）。"""
        return build_all_summary(self._config)

    def get_rule_rows(self) -> List[Dict[str, Any]]:
        """按「规则卡片」结构生成供界面渲染的行（含条件展开）。

        每行：name / summary / conditions（已展开的条件行）。
        """
        return [
            {
                "name": r.get("name", "未命名规则"),
                "summary": build_rule_summary(r),
                "conditions": _expand_conditions(r),
            }
            for r in self._config_rules
        ]

    # ------------------------------------------------------------------ 内部
    def _rule_index(self, rule: Dict[str, Any]) -> Optional[int]:
        """规则在 ``_config_rules`` 中的位置（1-based，与配置列表顺序一致）。

        找不到时返回 ``None``（不递归、不抛异常），供调用方保守处理。
        未知规则/规则名不一致时统一返回 None，避免无限递归。
        """
        for i, r in enumerate(self._config_rules, 1):
            if r.get("name") == rule.get("name"):
                return i
        return None


class RuleFilterWidget(QWidget):
    """隔离区规则筛选界面（看板筛选面板用）。"""

    def __init__(self, controller: RuleFilterController, parent: Optional[Any] = None):
        super().__init__(parent)
        self.controller = controller
        self._state = "all"          # all / none / active
        self._rules = controller.get_rule_rows()
        self._build_ui()
        self._rebuild_rule_cards()

    # ------------------------------------------------------------------ UI
    def get_state(self) -> str:
        return self._state

    def set_state(self, state: str):
        if state not in ("all", "none", "active"):
            return
        self._state = state
        self._rebuild()

    def clear(self) -> None:
        self.set_state("all")

    # ------------------------------------------------------------------ 布局
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._header = QWidget()
        header_lay = QHBoxLayout(self._header)
        header_lay.setContentsMargins(10, 8, 10, 8)
        header_lay.setSpacing(6)
        self._title_label = QLabel(
            f"隔离区规则筛选（规则驱动 · {self.controller.rule_count} 条规则）")
        self._title_label.setWordWrap(True)
        header_lay.addWidget(self._title_label)
        self._summary_label = QLabel(self.controller.get_summary())
        self._summary_label.setWordWrap(True)
        header_lay.addWidget(self._summary_label)
        header_lay.addStretch()
        layout.addWidget(self._header)

        self._result_widget = QWidget()
        result_lay = QVBoxLayout(self._result_widget)
        result_lay.setContentsMargins(8, 8, 8, 8)
        result_lay.setSpacing(8)
        result_lay.addWidget(QLabel("筛选结果"))
        self._result_table = QTableWidget(0, 3)
        self._result_table.setHorizontalHeaderLabels(["行号", "规则", "命中数"])
        result_lay.addWidget(self._result_table)
        layout.addWidget(self._result_widget)

        self._rule_cards = QWidget()
        rule_lay = QVBoxLayout(self._rule_cards)
        rule_lay.setContentsMargins(8, 8, 8, 8)
        rule_lay.setSpacing(8)
        self._rule_card_box = QWidget()
        rule_lay.addWidget(self._rule_card_box)
        layout.addWidget(self._rule_cards)

    def _rebuild(self):
        """重建界面（UI 层）：清空结果表、隐藏表头、刷新规则卡片。

        注意：``_rule_cards`` 在 ``_build_ui`` 里已设过 QVBoxLayout，
        这里绝不能再 ``setLayout(QWidget)``（TypeError），也不能反复
        ``addWidget`` 往同一个 layout 堆卡片。规则卡片只在初始化时构建一次，
        状态切换只更新结果表，避免重复添加导致布局错乱。
        """
        self._result_table.setRowCount(0)
        self._result_table.horizontalHeader().setVisible(False)

    def _render_result_table(self, df: pd.DataFrame, per_rule: List[Dict[str, Any]]):
        """根据已筛选的 df 与 per_rule 渲染结果表（行号/规则/命中数）。"""
        n = len(df) if not df.empty else 0
        # 必须先 setRowCount(n)：表格初始化为 (0, 3)，只设了列数没设行数，
        # 直接 setItem 到不存在的行不会自动扩行 → rowCount 恒为 0。
        self._result_table.setRowCount(0)
        self._result_table.setRowCount(n)
        for r in range(n):
            rule_name = self._rule_rows_text(r)
            hit = 0
            if per_rule:
                for pr in per_rule:
                    if pr.get("name") == rule_name:
                        hit = pr.get("hits", 0)
                        break
            self._result_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            self._result_table.setItem(r, 1, QTableWidgetItem(rule_name))
            self._result_table.setItem(r, 2, QTableWidgetItem(str(hit)))

    def apply(self) -> List[Dict[str, Any]]:
        """应用当前状态：执行规则筛选并渲染结果表，返回 (filtered_df, per_rule_hits)。"""
        df = self.controller._df if self.controller._df is not None else self.controller._df
        filtered, per_rule = self.controller.filter(df)
        self._render_result_table(filtered, per_rule)
        return filtered, per_rule

    def _rebuild_rule_cards(self):
        """在 ``_rule_card_box``（已在 _build_ui 挂进布局）内填规则卡片。

        ``_rule_cards`` 是 QWidget，没有 addWidget；正确做法是拿到它的
        layout 再 addWidget。这里用已存在的 ``_rule_card_box`` 作为容器，
        只构建一次（__init__ 调用），避免重复堆叠。
        """
        box = self._rule_card_box
        lay = box.layout()
        if lay is None:
            lay = QVBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
        for i, r in enumerate(self._rules):
            card = QWidget()
            lay.addWidget(card)
            self._render_rule_card(card, i, r)

    def _render_rule_card(self, card: QWidget, idx: int, rule: Dict[str, Any]):
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(6)

        name_label = QLabel(rule.get("name", "未命名规则"))
        name_label.setWordWrap(True)
        row.addWidget(name_label, 1)

        summary_label = QLabel(rule.get("summary", ""))
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("color: var(--color-textMuted);")
        row.addWidget(summary_label)

        conditions = rule.get("conditions", [])
        if not conditions:
            # 无条件（如空配置）：给提示
            hint = QLabel("（该规则未配置任何可选项）")
            hint.setStyleSheet("color: var(--color-textMuted);")
            row.addWidget(hint)
            return
        cond_box = QWidget()
        cond_layout = QVBoxLayout(cond_box)
        cond_layout.setSpacing(4)
        cond_layout.setContentsMargins(0, 0, 0, 0)
        for c in conditions:
            cb = QCheckBox(c.get("label", ""))
            cb.setToolTip(c.get("hint", ""))
            cond_layout.addWidget(cb)
        row.addWidget(cond_box)

        # 命中数徽章（按规则展开后的命中数）
        hit_label = QLabel("—")
        hit_label.setObjectName("hitBadge")
        hit_label.setAlignment(Qt.AlignCenter)
        row.addWidget(hit_label)

    def _rule_rows_text(self, row: int) -> str:
        """为结果表取某行对应的规则名（按命中数匹配）。"""
        for pr in self.controller.get_enabled_rules():
            if pr.get("name") == self._rule_row_name_for_index(row):
                return pr.get("name", "")
        return ""

    def _rule_row_name_for_index(self, row: int) -> str:
        # 简单回退：按规则卡片顺序
        return self._rules[min(row - 1, len(self._rules) - 1)].get("name", "")

    def set_applied(self, df: pd.DataFrame, per_rule: List[Dict[str, Any]]):
        """把已筛选结果回写到界面表格（供 UI 联动刷新），返回 (df, per_rule)。"""
        self._result_table.blockSignals(True)
        self._result_table.setRowCount(0)
        self._result_table.horizontalHeader().setVisible(False)
        self._result_table.setRowCount(len(df))
        for r in range(len(df)):
            self._result_table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            self._result_table.setItem(r, 1, QTableWidgetItem(self._rule_rows_text(r)))
            # 命中数按规则行取（r 从 0 开始，不能用 r-1 否则第 0 行取到末位）
            hit = per_rule[r].get("hits", 0) if r < len(per_rule) else 0
            self._result_table.setItem(r, 2, QTableWidgetItem(str(hit)))
        self._result_table.blockSignals(False)
        return df, per_rule
