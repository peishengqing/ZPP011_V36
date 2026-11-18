# -*- coding: utf-8 -*-
"""多工厂配置隔离（第一阶段：只读解析 + 显式迁移）。

问题
----
`config/auto_read_rules.json`、`auto_quarantine_config.json`、`threshold_config.json`
都是**全局单份**。饮料厂（1102）和食品厂（1101）的物料类型、单位习惯并不一样，
一套规则同时套两个厂，只能取“两边都能接受”的保守参数，或者干脆不带工厂条件。

本模块给出的机制
----------------
配置文件可按工厂分目录存放：``config/factories/<工厂>/<文件名>``。
**存在即覆盖，不存在就回退到 config/ 下的共享文件** —— 所以默认行为与现在完全
一致（没有 factories 目录时不产生任何影响），可以只给某个厂单独拎出来一份。

    config/
      auto_read_rules.json            ← 共享默认（两个厂都用）
      factories/
        1101/auto_read_rules.json     ← 只覆盖食品厂这一份
        1102/threshold_config.json    ← 只覆盖饮料厂阈值

工厂的确定顺序：环境变量 ``ZPP011_FACTORY`` → ``config/factory.json`` →
``default``（即不隔离）。

命令行
------
    python -m core.factory_context --show
    python -m core.factory_context --list
    python -m core.factory_context --use 1101
    python -m core.factory_context --migrate auto_read_rules.json --factory 1101

边界
----
只做“路径选择 + 拷贝文件”，不改任何规则内容，也不碰计算逻辑。
audit.db（已读快照 / 隔离记录）仍按用户单库，不按工厂拆分 —— 那张表带 data_id，
天然不串厂；真要拆属于第二阶段。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

ENV_FACTORY = "ZPP011_FACTORY"
ENV_CONFIG_DIR = "ZPP011_CONFIG_DIR"
STATE_FILE = "factory.json"
FACTORIES_DIRNAME = "factories"
DEFAULT_FACTORY = "default"

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAFE = re.compile(r"^[0-9A-Za-z_\-\u4e00-\u9fa5]{1,40}$")


def config_root():
    """配置根目录：测试/部署可用 ZPP011_CONFIG_DIR 覆盖。"""
    env = os.environ.get(ENV_CONFIG_DIR)
    if env:
        return os.path.abspath(env)
    return os.path.join(_ROOT, "config")


def _sanitize(name):
    name = (name or "").strip()
    if not name or name in (".", "..") or not _SAFE.match(name):
        return None
    return name


def factory_dir(factory=None):
    """某工厂的配置目录（不保证存在）。"""
    name = _sanitize(factory or current_factory()) or DEFAULT_FACTORY
    return os.path.join(config_root(), FACTORIES_DIRNAME, name)


def current_factory():
    """当前工厂名；未配置时为 default（表示不做隔离）。"""
    env = _sanitize(os.environ.get(ENV_FACTORY))
    if env:
        return env
    state = os.path.join(config_root(), STATE_FILE)
    try:
        with open(state, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            name = _sanitize(str(data.get("current", "")))
            if name:
                return name
    except (OSError, ValueError):
        pass
    return DEFAULT_FACTORY


def resolve_config(filename, factory=None):
    """返回该工厂的配置文件路径；无覆盖时返回 None（调用方沿用原路径）。

    只做存在性判断，不创建目录、不写文件。
    """
    name = _sanitize(factory or current_factory())
    if not name or name == DEFAULT_FACTORY:
        return None
    path = os.path.join(factory_dir(name), filename)
    return path if os.path.isfile(path) else None


def write_target(filename, factory=None):
    """保存时应写入的路径：有活动工厂则写进该厂目录（调用方负责建目录），否则 None。

    与 :func:`resolve_config` 的区别：读是“有则覆盖、无则回退”，写是“隔离后就
    只写自己那份”，否则一保存就把共享配置污染成某个厂的参数。
    """
    name = _sanitize(factory or current_factory())
    if not name or name == DEFAULT_FACTORY:
        return None
    return os.path.join(factory_dir(name), filename)


def list_factories():
    """列出已有配置目录的工厂：[{'name','path','files'}]。"""
    base = os.path.join(config_root(), FACTORIES_DIRNAME)
    result = []
    if not os.path.isdir(base):
        return result
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if not os.path.isdir(path):
            continue
        files = sorted(f for f in os.listdir(path) if f.lower().endswith(".json"))
        result.append({"name": name, "path": path, "files": files})
    return result


def set_current_factory(name):
    """写 config/factory.json（原子替换）。name=default 表示恢复共享配置。"""
    name = _sanitize(name)
    if not name:
        raise ValueError(f"工厂名不合法: {name!r}")
    root = config_root()
    os.makedirs(root, exist_ok=True)
    target = os.path.join(root, STATE_FILE)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"current": name}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)
    return target


def migrate(filenames, factory, overwrite=False):
    """把共享配置复制一份到 config/factories/<factory>/ 下，作为该厂的起点。

    filenames 可为 str 或 list；返回 {文件名: 目标路径 或 跳过原因}。
    """
    name = _sanitize(factory)
    if not name or name == DEFAULT_FACTORY:
        raise ValueError("migrate 需要一个具体工厂名（不能是 default）")
    dest_dir = factory_dir(name)
    os.makedirs(dest_dir, exist_ok=True)
    if isinstance(filenames, str):
        filenames = [filenames]

    report = {}
    for fn in filenames:
        src = os.path.join(config_root(), fn)
        dst = os.path.join(dest_dir, fn)
        if not os.path.isfile(src):
            report[fn] = f"源文件不存在: {src}"
            continue
        if os.path.exists(dst) and not overwrite:
            report[fn] = f"已存在，未覆盖: {dst}"
            continue
        shutil.copy2(src, dst)
        report[fn] = dst
    return report


def identify(display_name):
    """把界面上的工厂写法归一成配置命名空间（1101 / 1102）。

    现场同一工厂可能写作「1101」「1101食品」「云南达利-食品厂」；认不出就返回 None，
    调用方不应该把不确定的名字写进配置。
    """
    text = str(display_name or "").strip()
    if not text:
        return None
    if "食品" in text or text.startswith("1101"):
        return "1101"
    if "饮料" in text or text.startswith("1102"):
        return "1102"
    return None


def remember_factory(display_name):
    """记住用户选中的工厂（认不出或是「全部」就不写）。返回写入的工厂名或 None。"""
    name = identify(display_name)
    if not name:
        return None
    try:
        set_current_factory(name)
        return name
    except Exception:
        return None


def preferred_factory():
    """启动时想恢复的工厂名；未配置时返回 None。"""
    name = current_factory()
    return None if name == DEFAULT_FACTORY else name


def pick_startup_factory(keys):
    """从数据里实际存在的工厂键中挑出「上次看的那个」；挑不到返回 None。

    数据里的写法可能是 1101 / 1101食品 / 云南达利-食品厂，所以按包含关系匹配。
    """
    pref = preferred_factory()
    if not pref:
        return None
    for key in keys or []:
        if str(key) == pref or pref in str(key):
            return key
    return None


def describe():
    name = current_factory()
    return {
        "config_root": config_root(),
        "current": name,
        "isolated": name != DEFAULT_FACTORY,
        "factory_dir": factory_dir(name),
        "known": [f["name"] for f in list_factories()],
        "env_factory": os.environ.get(ENV_FACTORY) or "",
    }


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="多工厂配置隔离（只读解析 / 显式迁移）")
    ap.add_argument("--show", action="store_true", help="显示当前工厂与配置根")
    ap.add_argument("--list", action="store_true", help="列出已建配置的工厂")
    ap.add_argument("--use", metavar="FACTORY", help="切换当前工厂（写 config/factory.json）")
    ap.add_argument("--migrate", nargs="+", metavar="FILE",
                    help="把共享配置复制到工厂目录，作为该厂起点")
    ap.add_argument("--factory", help="配合 --migrate 使用的工厂名")
    ap.add_argument("--force", action="store_true", help="migrate 时覆盖已存在文件")
    args = ap.parse_args(argv)

    if args.use:
        print(f"[切换] {set_current_factory(args.use)} → {args.use}")
    if args.migrate:
        target = args.factory or current_factory()
        for fn, res in migrate(args.migrate, target, overwrite=args.force).items():
            print(f"[迁移] {fn}: {res}")
    if args.list or not (args.show or args.use or args.migrate):
        known = list_factories()
        if not known:
            print("[列表] 尚未建立任何工厂配置目录（全部使用共享配置）")
        for item in known:
            print(f"[列表] {item['name']}: {len(item['files'])} 个文件")
    if args.show or not (args.list or args.use or args.migrate):
        info = describe()
        print(f"[当前] 工厂={info['current']}  隔离={info['isolated']}")
        print(f"[路径] 配置根={info['config_root']}")
        print(f"[路径] 工厂目录={info['factory_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
