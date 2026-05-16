# -*- coding: utf-8 -*-
"""
替代料管理模块
支持存储格式：(编码, 名称) 元组，兼容旧格式（纯文本名称）
显示时自动转换为“编码（名称）”
"""

import os
import json
import sys
import pandas as pd

# 默认替代料配对（格式：[(编码, 名称), (编码, 名称)]）
DEFAULT_ALT_PAIRS = [
    (("", "核桃仁头二路"), ("", "核桃仁尖白头二路")),
    (("", "蔓越莓干1/8切片"), ("", "蔓越莓4mm切丁")),
    (("", "184g达利园蛋黄味注心派手包袋(专供)"), ("", "184g达利园蛋黄味注心派手包袋")),
    (("", "25.3g透明原1810"), ("", "22g透明原1810")),
    (("", "250mlx24包豆本豆唯甄原味豆奶覆膜彩箱(对口箱)"), ("", "250mlx24包豆本豆唯甄原味豆奶覆膜彩盒(片箱)")),
    (("", "260gx16包达利园巧克力派水印箱"), ("", "260gx16包达利园巧克力派水印箱(出口)")),
    (("", "260gx16包达利园巧克力派手包袋"), ("", "260gx16包达利园巧克力派手包袋(出口)")),
    (("", "380mlx15瓶乐虎氨基酸功能饮料上光彩箱"), ("", "380mlx15瓶乐虎氨基酸功能饮料预印箱")),
    (("", "POF收缩膜(330x1.2C)"), ("", "90gx2罐可比克薯片POF膜")),
]

def _get_config_path():
    """获取替代料配置文件的绝对路径（优先级：APPDATA → exe目录 → 用户目录）"""
    # 优先级1: APPDATA\ZPP011\config\alt_pairs.json
    appdata = os.environ.get('APPDATA', '')
    if appdata:
        path = os.path.join(appdata, 'ZPP011', 'config', 'alt_pairs.json')
        if os.path.exists(path):
            return path
    # 优先级2: exe同目录
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        path = os.path.join(exe_dir, 'zpp011_alt_pairs.json')
        if os.path.exists(path):
            return path
    # 优先级3: 用户目录备选
    home = os.path.expanduser('~')
    path = os.path.join(home, '.zpp011_audit', 'alt_pairs.json')
    if os.path.exists(path):
        return path
    # 都不存在则返回 APPDATA 路径（用于写入）
    if appdata:
        config_dir = os.path.join(appdata, 'ZPP011', 'config')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'alt_pairs.json')
    # 最终兜底：当前目录
    return os.path.join(os.getcwd(), 'alt_pairs.json')

def _find_code_by_name(name, material_df=None):
    """根据物料名称从物料数据中查找编码（精确匹配优先，模糊包含其次）"""
    if material_df is None or material_df.empty:
        return None
    if '物料名称' not in material_df.columns or '物料编码' not in material_df.columns:
        return None
    # 精确匹配
    matched = material_df[material_df['物料名称'] == name]
    if not matched.empty:
        return matched.iloc[0]['物料编码']
    # 模糊包含匹配
    matched = material_df[material_df['物料名称'].str.contains(name, na=False)]
    if not matched.empty:
        return matched.iloc[0]['物料编码']
    return None

def load_alt_pairs(log_cb=None, material_df=None):
    """
    加载替代料配对
    返回格式：列表，每个元素为 (物料A元组, 物料B元组)
    物料元组：(编码, 名称)
    如果编码为空，则显示时仅显示名称
    """
    config_path = _get_config_path()
    pairs = list(DEFAULT_ALT_PAIRS)
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, list) and len(loaded) > 0:
                pairs = loaded
                if log_cb:
                    log_cb(f"加载替代料配置：{config_path}，共{len(pairs)}对")
        except Exception as e:
            if log_cb:
                log_cb(f"加载替代料配置失败：{e}，使用默认配置")
    
    # 迁移旧格式：将纯字符串转换为 (编码, 名称) 元组
    migrated = False
    new_pairs = []
    for a, b in pairs:
        # 处理 a
        if isinstance(a, str):
            code = _find_code_by_name(a, material_df)
            a_new = (code, a) if code else (None, a)
            migrated = True
        elif isinstance(a, (list, tuple)) and len(a) == 2:
            # 已经是 (code, name) 格式
            a_new = tuple(a)
        else:
            a_new = a
        # 处理 b
        if isinstance(b, str):
            code = _find_code_by_name(b, material_df)
            b_new = (code, b) if code else (None, b)
            migrated = True
        elif isinstance(b, (list, tuple)) and len(b) == 2:
            b_new = tuple(b)
        else:
            b_new = b
        new_pairs.append((a_new, b_new))
    
    if migrated:
        if log_cb:
            log_cb("替代料配置已从旧格式迁移到 (编码, 名称) 格式")
        save_alt_pairs(new_pairs)
        pairs = new_pairs
    
    return pairs

def save_alt_pairs(pairs):
    """
    保存替代料配对
    pairs格式：列表，每个元素为 ( (code1, name1), (code2, name2) )
    保存为 JSON 数组，每个配对是二维数组
    """
    config_path = _get_config_path()
    # 确保目录存在
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    # 转换为可序列化的格式：每个配对用二维数组表示
    serializable = []
    for a, b in pairs:
        # 标准化为 [code, name] 形式
        if isinstance(a, (list, tuple)) and len(a) == 2:
            a_list = list(a)
        elif isinstance(a, str):
            a_list = [None, a]
        else:
            a_list = [None, str(a)]
        if isinstance(b, (list, tuple)) and len(b) == 2:
            b_list = list(b)
        elif isinstance(b, str):
            b_list = [None, b]
        else:
            b_list = [None, str(b)]
        serializable.append([a_list, b_list])
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)

def get_display_text(material_tuple):
    """
    根据物料元组 (编码, 名称) 返回显示文本 "编码（名称）"
    若编码为空，返回名称；若名称为空，返回编码
    """
    if not isinstance(material_tuple, (list, tuple)) or len(material_tuple) < 2:
        return str(material_tuple)
    code, name = material_tuple[0], material_tuple[1]
    if code and str(code) != 'None' and name:
        return f"{code}（{name}）"
    elif name:
        return name
    elif code:
        return str(code)
    else:
        return "?"

# 以下为兼容旧代码的函数接口（可选）
def get_alt_pairs():
    return load_alt_pairs()