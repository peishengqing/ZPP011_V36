# -*- coding: utf-8 -*-
"""配置损坏保护回归测试。

背景：ConfigManager 曾在解析失败时直接用默认值覆盖原文件，用户配置不可恢复；
save_alt_pairs 保存失败只写日志就返回，调用方以为已保存。此测试锁定修复后的行为。
"""
import glob
import json
import os

import pytest

from core.config_manager import ConfigManager
from domain.alt_material import alt_manager


def _bad_files(path):
    return glob.glob(path + ".bad_*")


def test_corrupt_config_backed_up_not_destroyed(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"version": "1.0", "broken": ', encoding="utf-8")   # 非法 JSON

    manager = ConfigManager(config_path=cfg)

    assert _bad_files(str(cfg)), "损坏的配置必须留下 .bad_* 备份"
    backup = _bad_files(str(cfg))[0]
    assert "broken" in open(backup, encoding="utf-8").read(), "备份内容应为原始损坏内容"
    # 覆盖后的文件应是可解析的默认配置
    rewritten = json.loads(cfg.read_text(encoding="utf-8"))
    assert rewritten.get("version") == ConfigManager.CURRENT_VERSION


def test_save_is_atomic_and_leaves_no_tmp(tmp_path):
    cfg = tmp_path / "config.json"
    manager = ConfigManager(config_path=cfg)
    manager.config["last_export_dir"] = "D:/out"
    manager._save()

    assert not list(tmp_path.glob("*.tmp")), "原子写不应残留 .tmp 文件"
    assert json.loads(cfg.read_text(encoding="utf-8"))["last_export_dir"] == "D:/out"


def test_alt_save_returns_true_and_writes_valid_json(tmp_path, monkeypatch):
    target = tmp_path / "alt_pairs.json"
    monkeypatch.setattr(alt_manager, "_get_config_path", lambda: str(target))

    ok = alt_manager.save_alt_pairs([(("F", "A1", "甲"), ("F", "B1", "乙"))])

    assert ok is True
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data == [[["F", "A1", "甲"], ["F", "B1", "乙"]]]
    assert not list(tmp_path.glob("*.tmp"))


def test_alt_save_returns_false_when_unwritable(tmp_path, monkeypatch):
    # 用「文件路径 + 子路径」制造不可写场景：os.makedirs 会失败
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / "sub" / "alt_pairs.json"
    monkeypatch.setattr(alt_manager, "_get_config_path", lambda: str(target))

    assert alt_manager.save_alt_pairs([(("F", "A1", "甲"), ("F", "B1", "乙"))]) is False


def test_alt_load_backs_up_corrupt_file(tmp_path, monkeypatch):
    target = tmp_path / "alt_pairs.json"
    target.write_text("{not a list", encoding="utf-8")
    monkeypatch.setattr(alt_manager, "_get_config_path", lambda: str(target))

    pairs = alt_manager.load_alt_pairs()

    assert pairs == list(alt_manager.DEFAULT_ALT_PAIRS)
    assert _bad_files(str(target)), "损坏的替代料配置必须留下 .bad_* 备份"
    assert not target.exists(), "损坏文件应被移走，避免下次保存覆盖前再次读到"
