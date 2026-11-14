# -*- coding: utf-8 -*-
"""
路径配置（v36 抽取）
"""

import os

# 基础路径（config目录的父目录即项目根目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 输出目录
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# 确保目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


# SAP 导出原数据目录的兜底默认值（历史上散落在各处的硬编码值，统一收口到这里）。
# 换机器/换盘时，改 config/config.yaml 的 data.dir 即可，无需再动代码。
DEFAULT_DATA_DIR = r"E:\ZPP011导出文件原数据"


def get_data_dir():
    """返回 SAP 导出原数据目录（监控目录 / 打开文件默认目录的唯一来源）。

    优先读 config/config.yaml 的 ``data.dir``；缺失、为空或读取异常时回退
    ``DEFAULT_DATA_DIR``。延迟 import config_loader 以规避 config↔core 循环依赖。
    """
    try:
        from core.config_loader import config
        val = config.get("data.dir")
        if val and str(val).strip():
            return os.path.normpath(str(val).strip())
    except Exception:
        pass
    return DEFAULT_DATA_DIR


def set_data_dir(new_dir):
    """把 SAP 数据目录写回 config/config.yaml 的 ``data.dir``，并热更新内存配置。

    逐行替换、只动 ``data:`` 段下的 ``dir:`` 那一行，保留文件里其余中文注释
    （全量 yaml.dump 会把注释冲掉）。写盘用「临时文件 + 原子替换」，中途崩溃
    不会留下半截文件。返回 True=成功；找不到 data: 段时追加到文件末尾再写。
    """
    import re
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(base_dir, "config", "config.yaml")
    new_dir = os.path.normpath(str(new_dir).strip())
    quoted = "'" + new_dir.replace("'", "''") + "'"
    new_line = "  dir: " + quoted

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    out, in_data, replaced = [], False, False
    for ln in lines:
        stripped = ln.strip()
        # 进入/离开 data 段：以"行首非空格且含冒号"判定顶层键
        if ln and not ln[0].isspace() and ":" in ln:
            in_data = stripped.split(":", 1)[0].strip() == "data"
        if in_data and not replaced and re.match(r"^\s+dir\s*:", ln):
            out.append(new_line + "\n")
            replaced = True
            continue
        out.append(ln)

    if not replaced:
        # 没有 data.dir 行：有 data: 段就在其后插入，否则整段追加到末尾
        if any(re.match(r"^data\s*:", l) for l in out):
            for i, l in enumerate(out):
                if re.match(r"^data\s*:", l):
                    out.insert(i + 1, new_line + "\n")
                    break
        else:
            if out and out[-1].strip():
                out.append("\n")
            out.append("data:\n")
            out.append(new_line + "\n")

    tmp = cfg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(out)
    os.replace(tmp, cfg_path)

    # 热更新内存配置，使本会话内 get_data_dir() 立即反映新值
    try:
        from core.config_loader import config
        config.reload()
    except Exception:
        pass
    return True
