# -*- coding: utf-8 -*-
"""多工厂配置隔离（core/factory_context.py）与规则加载接入的用例。"""
import json

import pytest

from core import factory_context as fc


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def cfgroot(tmp_path, monkeypatch):
    monkeypatch.setenv(fc.ENV_CONFIG_DIR, str(tmp_path))
    monkeypatch.delenv(fc.ENV_FACTORY, raising=False)
    return tmp_path


def _read_rule(name):
    return {"enabled": True,
            "rules": [{"name": name, "enabled": True,
                       "conditions": [{"type": "dev_qty_eq", "params": {"value": 0}}]}]}


# ---------------------------------------------------------------- 解析

def test_default_when_nothing_configured(cfgroot):
    assert fc.current_factory() == "default"
    assert fc.resolve_config("auto_read_rules.json") is None


def test_env_factory_wins(cfgroot, monkeypatch):
    monkeypatch.setenv(fc.ENV_FACTORY, "1101")
    assert fc.current_factory() == "1101"
    assert fc.resolve_config("auto_read_rules.json") is None      # 该厂还没建文件


def test_factory_file_overrides_only_when_present(cfgroot, monkeypatch):
    monkeypatch.setenv(fc.ENV_FACTORY, "1101")
    target = cfgroot / "factories" / "1101" / "auto_read_rules.json"
    _write_json(target, _read_rule("食品厂专用"))
    resolved = fc.resolve_config("auto_read_rules.json")
    assert resolved == str(target)
    # 同厂里没有的文件仍然回退共享
    assert fc.resolve_config("threshold_config.json") is None


def test_state_file_sets_current_factory(cfgroot):
    fc.set_current_factory("1102")
    assert fc.current_factory() == "1102"
    data = json.loads((cfgroot / fc.STATE_FILE).read_text(encoding="utf-8"))
    assert data["current"] == "1102"
    fc.set_current_factory("default")
    assert fc.current_factory() == "default"


@pytest.mark.parametrize("bad", ["", "  ", "..", "a/b", "a\\b", "x" * 60, "工厂\n1"])
def test_illegal_names_rejected(cfgroot, bad):
    with pytest.raises(ValueError):
        fc.set_current_factory(bad)


# ---------------------------------------------------------------- 迁移

def test_migrate_copies_and_respects_existing(cfgroot):
    _write_json(cfgroot / "auto_read_rules.json", _read_rule("共享"))
    report = fc.migrate("auto_read_rules.json", "1101")
    dst = cfgroot / "factories" / "1101" / "auto_read_rules.json"
    assert report["auto_read_rules.json"] == str(dst)
    assert dst.is_file()

    _write_json(dst, _read_rule("厂内改过"))
    again = fc.migrate("auto_read_rules.json", "1101")
    assert "未覆盖" in again["auto_read_rules.json"]
    assert json.loads(dst.read_text(encoding="utf-8"))["rules"][0]["name"] == "厂内改过"

    forced = fc.migrate("auto_read_rules.json", "1101", overwrite=True)
    assert forced["auto_read_rules.json"] == str(dst)
    assert json.loads(dst.read_text(encoding="utf-8"))["rules"][0]["name"] == "共享"


def test_migrate_missing_source_reported(cfgroot):
    report = fc.migrate(["nope.json"], "1101")
    assert "源文件不存在" in report["nope.json"]


def test_migrate_rejects_default_factory(cfgroot):
    with pytest.raises(ValueError):
        fc.migrate("auto_read_rules.json", "default")


def test_list_factories(cfgroot):
    _write_json(cfgroot / "factories" / "1101" / "auto_read_rules.json", _read_rule("A"))
    _write_json(cfgroot / "factories" / "1102" / "threshold_config.json", {})
    names = [f["name"] for f in fc.list_factories()]
    assert names == ["1101", "1102"]
    files = next(f for f in fc.list_factories() if f["name"] == "1101")["files"]
    assert files == ["auto_read_rules.json"]


# ---------------------------------------------------------------- 规则加载接入

def test_auto_read_rules_uses_factory_file(cfgroot, monkeypatch):
    from core.auto_read_rules import load_auto_read_rules_config

    _write_json(cfgroot / "auto_read_rules.json", _read_rule("共享规则"))
    monkeypatch.setenv(fc.ENV_FACTORY, "1101")
    _write_json(cfgroot / "factories" / "1101" / "auto_read_rules.json",
                _read_rule("食品厂规则"))

    assert load_auto_read_rules_config()["rules"][0]["name"] == "食品厂规则"
    monkeypatch.delenv(fc.ENV_FACTORY)
    assert load_auto_read_rules_config()["rules"][0]["name"] == "共享规则"


def test_auto_read_rules_saves_into_factory_dir(cfgroot, monkeypatch):
    from core.auto_read_rules import load_auto_read_rules_config, save_auto_read_rules_config

    monkeypatch.setenv(fc.ENV_FACTORY, "1101")
    save_auto_read_rules_config(_read_rule("新存"))
    assert (cfgroot / "factories" / "1101" / "auto_read_rules.json").is_file()
    assert not (cfgroot / "auto_read_rules.json").exists()       # 共享配置不被污染
    assert load_auto_read_rules_config()["rules"][0]["name"] == "新存"


def test_auto_quarantine_falls_back_to_shared(cfgroot, monkeypatch):
    from core.auto_quarantine import load_auto_quarantine_config

    _write_json(cfgroot / "auto_quarantine_config.json",
                {"enabled": True, "rules": [{"name": "共享隔离", "conditions": []}]})
    monkeypatch.setenv(fc.ENV_FACTORY, "1102")
    assert load_auto_quarantine_config()["rules"][0]["name"] == "共享隔离"


def test_threshold_config_reads_factory_override(cfgroot, monkeypatch):
    from core.threshold_config import load_threshold_config

    _write_json(cfgroot / "threshold_config.json", {"alert_dev_rate_pct": 10.0})
    monkeypatch.setenv(fc.ENV_FACTORY, "1102")
    _write_json(cfgroot / "factories" / "1102" / "threshold_config.json",
                {"alert_dev_rate_pct": 33.0})
    assert load_threshold_config()["alert_dev_rate_pct"] == 33.0


def test_describe_reports_isolation_state(cfgroot, monkeypatch):
    monkeypatch.setenv(fc.ENV_FACTORY, "1101")
    info = fc.describe()
    assert info["current"] == "1101"
    assert info["isolated"] is True
    assert info["env_factory"] == "1101"


# ---------------------------------------------------------------- 界面工厂名 → 配置命名空间

@pytest.mark.parametrize("display,expected", [
    ("1101", "1101"), ("1101食品", "1101"), ("云南达利-食品厂", "1101"),
    ("1102", "1102"), ("饮料厂", "1102"), ("云南达利-饮料厂", "1102"),
    ("全部", None), ("", None), (None, None), ("其他工厂", None),
])
def test_identify_factory_names(display, expected):
    assert fc.identify(display) == expected


def test_remember_factory_只记住视图_不动规则命名空间(cfgroot):
    assert fc.preferred_factory() is None
    assert fc.remember_factory("云南达利-饮料厂") == "1102"
    # 视图偏好写进 ui_state.json
    assert (cfgroot / fc.UI_STATE_FILE).is_file()
    assert fc.preferred_factory() == "1102"
    # 关键：不再把配置命名空间切到 1102，规则仍读共享
    assert fc.current_factory() == "default"
    assert fc.resolve_config("auto_read_rules.json") is None


def test_remember_factory_ignores_unknown_and_all(cfgroot):
    assert fc.remember_factory("某新厂") is None
    assert fc.current_factory() == "default"
    # 选「全部」= 清掉视图偏好，下次启动回到全部
    assert fc.remember_factory("1101食品") == "1101"
    assert fc.remember_factory("全部") is None
    assert fc.preferred_factory() is None


def test_pick_startup_factory_matches_display_variants(cfgroot):
    fc.remember_factory("1101食品")
    keys = ["全部", "1102", "1101食品"]
    assert fc.pick_startup_factory(keys) == "1101食品"
    assert fc.pick_startup_factory(["全部", "1102"]) is None
    assert fc.pick_startup_factory([]) is None


def test_pick_startup_factory_without_preference(cfgroot):
    assert fc.pick_startup_factory(["全部", "1101"]) is None
