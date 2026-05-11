#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" 替代料配对管理 — 配置文件存储在用户目录，支持编码+名称双显示 """

import os
import json
import sys as _sys


# ── 默认替代料配对 ───────────────────────────────────
DEFAULT_ALT_PAIRS = [
    ("10001272", "核桃仁尖白头二路"),
    ("10000430", "核桃仁头二路"),
    ("10000406", "蔓越莓4mm切丁"),
    ("10000405", "蔓越莓干1/8切片"),
    ("20005300", "184g手包袋(专供)"),
    ("20005301", "184g手包袋(普通)"),
]


def _get_config_dir():
    """返回用户配置目录（优先 E:\zpp011_dev\.zpp011_audit，兼容旧版 ~/.zpp011_audit）"""
    new_dir = r"E:\zpp011_dev\.zpp011_audit"
    old_dir = os.path.join(os.path.expanduser("~"), ".zpp011_audit")
    os.makedirs(new_dir, exist_ok=True)
    # 一次性迁移：旧目录存在且新目录配置文件不存在时，复制过去
    old_cfg = os.path.join(old_dir, "alt_pairs.json")
    new_cfg = os.path.join(new_dir, "alt_pairs.json")
    if os.path.exists(old_cfg) and not os.path.exists(new_cfg):
        try:
            import shutil
            shutil.copy2(old_cfg, new_cfg)
        except Exception:
            pass
    return new_dir


def _get_config_path():
    """返回替代料配置文件路径（用户目录）"""
    return os.path.join(_get_config_dir(), "alt_pairs.json")


def _get_old_config_path():
    """返回旧版配置文件路径（exe 同目录）"""
    if getattr(_sys, 'frozen', False):
        base = os.path.dirname(_sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'zpp011_alt_pairs.json')


def save_alt_pairs(alt_pairs, log_cb=None):
    """将配对保存到配置文件"""
    path = _get_config_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(alt_pairs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        if log_cb:
            log_cb(f"保存替代料配置失败：{e}", "error")


def load_alt_pairs(log_cb=None):
    """从配置文件加载配对，失败则返回默认"""
    new_path = _get_config_path()
    old_path = _get_old_config_path()

    # ── 优先从用户目录读取 ──
    if os.path.exists(new_path):
        try:
            with open(new_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            result = _normalize_pairs(data)
            if result:
                return result
        except Exception as e:
            if log_cb:
                log_cb(f"读取替代料配置失败：{e}", "warn")

    # ── 用户目录没有，尝试从旧位置迁移 ──
    if os.path.exists(old_path):
        try:
            with open(old_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            result = _normalize_pairs(data)
            if result:
                # 自动保存到新位置
                save_alt_pairs(result)
                if log_cb:
                    log_cb(f"✅ 已将 {len(result)} 对替代料配置从旧位置迁移到 {new_path}", "success")
                return result
        except Exception as e:
            if log_cb:
                log_cb(f"迁移旧配置失败：{e}", "warn")

    # ── 都没有，返回默认 ──
    return list(DEFAULT_ALT_PAIRS)


def _normalize_pairs(data):
    """
    将各种格式的配对数据统一为 (编码, 名称) 格式
    兼容旧版纯名称格式
    """
    result = []
    for pair in data:
        if isinstance(pair, (list, tuple)):
            if len(pair) == 2:
                a, b = pair
                result.append((str(a).strip(), str(b).strip()))
            elif len(pair) == 3:
                result.append((str(pair[0]).strip(), str(pair[1]).strip()))
    return result if result else None


def get_display_name(code, name, code_to_name_map=None):
    """
    返回替代料的显示名称
    格式：编码（名称） 或 仅有名称
    """
    if code and name and code != name:
        return f"{code}（{name}）"
    elif name:
        return name
    elif code:
        return code
    return "未知"


def build_code_name_map(dataframe, code_col='组件物料号', name_col='组件物料描述'):
    """
    从 DataFrame 构建编码→名称的映射字典
    """
    code_to_name = {}
    if dataframe is not None and not dataframe.empty:
        for _, row in dataframe.iterrows():
            code = str(row.get(code_col, ''))
            name = str(row.get(name_col, ''))
            if code and code != 'nan' and name and name != 'nan':
                code_to_name[code] = name
    return code_to_name
