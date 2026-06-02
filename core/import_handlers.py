# -*- coding: utf-8 -*-
"""
模板导入核心逻辑（替代料配对、规则）
（已整合 Trae 审计建议：事务回滚、原子保存）
"""
import os
import json
import shutil
import tempfile


def atomic_save_json(data, file_path):
    """原子保存 JSON 数据到文件"""
    try:
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        raise ValueError(f"数据无法序列化为 JSON: {e}")
    dir_name = os.path.dirname(file_path) or '.'
    fd, tmp_path = tempfile.mkstemp(suffix='.json', dir=dir_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json_str)
    except Exception as e:
        os.close(fd)
        os.remove(tmp_path)
        raise IOError(f"写入临时文件失败: {e}")
    backup_path = file_path + ".backup"
    has_backup = False
    if os.path.exists(file_path):
        shutil.copy2(file_path, backup_path)
        has_backup = True
    try:
        os.replace(tmp_path, file_path)
    except Exception as e:
        if has_backup and os.path.exists(backup_path):
            shutil.copy2(backup_path, file_path)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise IOError(f"原子替换失败: {e}")
    if has_backup and os.path.exists(backup_path):
        os.remove(backup_path)


def import_alt_pairs_from_excel(parsed_data, current_pairs, overwrite=False):
    """
    返回新的配对列表（不直接修改传入的 current_pairs）
    交由调用方决定何时修改内存和保存文件，实现事务性。
    """
    # 1. 构建新配对
    new_pairs = []
    for item in parsed_data:
        factory = item.get('工厂名称', '').strip()
        code_a = item.get('物料A编码', '').strip()
        name_a = item.get('物料A名称', '').strip()
        code_b = item.get('物料B编码', '').strip()
        name_b = item.get('物料B名称', '').strip()
        if not factory or not code_a or not code_b:
            continue
        pair = ((factory, code_a, name_a), (factory, code_b, name_b))
        new_pairs.append(pair)

    # 2. 根据模式计算结果集
    if overwrite:
        result_pairs = new_pairs
    else:
        # 去重：使用 (工厂, 编码A, 编码B) 作为唯一标识
        existing_set = set()
        for p in current_pairs:
            existing_set.add((p[0][0], p[0][1], p[1][1]))
        result_pairs = list(current_pairs)
        for p in new_pairs:
            key = (p[0][0], p[0][1], p[1][1])
            if key not in existing_set:
                result_pairs.append(p)
                existing_set.add(key)
    return result_pairs


def import_rules_from_excel(parsed_data, rules_path, overwrite=False):
    """导入规则，直接写入文件（内部已使用原子保存）"""
    # 读取现有规则
    if os.path.exists(rules_path) and not overwrite:
        with open(rules_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
            rules = existing.get('rules', [])
    else:
        rules = []

    # 转换 parsed_data 为规则字典
    new_rules = []
    for item in parsed_data:
        rule = {
            'name': item['name'],
            'condition': item['condition'],
            'action': item['action'],
            'enabled': item['enabled']
        }
        if item['action'] == 'set_color':
            rule['color'] = item.get('color', '#ffcccc')
        elif item['action'] == 'set_remark':
            rule['remark_text'] = item.get('remark_text', '')
        elif item['action'] == 'set_status':
            rule['status'] = item.get('status', '需补备注')
        new_rules.append(rule)

    # 合并规则（基于名称去重）
    if overwrite:
        final_rules = new_rules
    else:
        existing_names = {r.get('name') for r in rules}
        final_rules = list(rules)
        for r in new_rules:
            if r['name'] not in existing_names:
                final_rules.append(r)
                existing_names.add(r['name'])

    atomic_save_json({'rules': final_rules}, rules_path)