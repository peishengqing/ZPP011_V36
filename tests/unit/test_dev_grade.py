# -*- coding: utf-8 -*-
"""偏差等级列分档测试（规格 §2.1）：|率|>50 严重 / 10~50 一般 / <10 轻微 / 空 —。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from analysis.excel_builder.sheet5_full import dev_grade


def test_grade_boundaries():
    assert dev_grade(9.99) == "轻微"
    assert dev_grade(10.0) == "一般"    # 10 归一般（含边界）
    assert dev_grade(50.0) == "一般"    # 50 归一般（>50 才严重）
    assert dev_grade(50.01) == "严重"
    assert dev_grade(-100.0) == "严重"  # 钳位标记按绝对值分档（>50 → 严重）
    assert dev_grade(100.0) == "严重"


def test_grade_signed_and_none():
    assert dev_grade(-60.5) == "严重"
    assert dev_grade(0.0) == "轻微"
    assert dev_grade(None) == "—"
    assert dev_grade(float("nan")) == "—"
    assert dev_grade("abc") == "—"
