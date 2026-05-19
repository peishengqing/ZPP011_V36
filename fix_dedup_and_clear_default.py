# -*- coding: utf-8 -*-
"""修复去重逻辑 + 清空内置替代料"""
import os

# 修复1: 去重检查 - 编码为空时用描述匹配
fp1 = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(fp1, 'r', encoding='utf-8') as f:
    content = f.read()

old_dedup = '''            # 去重检查：是否已存在相同配对
            exact_match = False
            conflict = False
            for (ea, eb) in self.alt_pairs:
                def _extract_code(item):
                    if isinstance(item, (list, tuple)):
                        if len(item) >= 3: return str(item[1]).strip()
                        if len(item) == 2: return str(item[0]).strip()
                        return str(item[0]).strip()
                    return str(item).strip()
                ea_code = _extract_code(ea)
                eb_code = _extract_code(eb)
                if (ea_code == a_code and eb_code == b_code) or (ea_code == b_code and eb_code == a_code):
                    exact_match = True
                    break
                if a_code in (ea_code, eb_code) or b_code in (ea_code, eb_code):
                    conflict = True'''

new_dedup = '''            # 去重检查：是否已存在相同配对（编码为空时用描述匹配）
            exact_match = False
            conflict = False
            for (ea, eb) in self.alt_pairs:
                def _extract_code_and_desc(item):
                    if isinstance(item, (list, tuple)):
                        if len(item) >= 3:
                            code = str(item[1]).strip() if item[1] else ''
                            desc = str(item[2]).strip() if item[2] else ''
                            return code if code else desc  # 编码为空用描述
                        if len(item) == 2:
                            code = str(item[0]).strip() if item[0] else ''
                            desc = str(item[1]).strip() if item[1] else ''
                            return code if code else desc
                        return str(item[0]).strip() if item[0] else ''
                    s = str(item).strip()
                    return s if s else ''
                ea_key = _extract_code_and_desc(ea)
                eb_key = _extract_code_and_desc(eb)
                a_key = a_code if a_code else a_name
                b_key = b_code if b_code else b_name
                if (ea_key == a_key and eb_key == b_key) or (ea_key == b_key and eb_key == a_key):
                    exact_match = True
                    break
                if a_key in (ea_key, eb_key) or b_key in (ea_key, eb_key):
                    conflict = True'''

if old_dedup in content:
    content = content.replace(old_dedup, new_dedup)
    with open(fp1, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: Fixed dedup logic (use desc when code is empty)')
else:
    print('SKIP: Dedup pattern not found')

# 修复2: 清空 DEFAULT_ALT_PAIRS
fp2 = r'E:\zpp011_dev\模块化脚本\domain\alt_material\alt_manager.py'
with open(fp2, 'r', encoding='utf-8') as f:
    content2 = f.read()

old_default = '''# 默认替代料配对（格式：[(编码, 名称), (编码, 名称)]）
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
]'''

new_default = '''# 默认替代料配对（格式：[(工厂, 编码, 名称), (工厂, 编码, 名称)]）
# 已清空，后续通过导入功能添加
DEFAULT_ALT_PAIRS = []'''

if old_default in content2:
    content2 = content2.replace(old_default, new_default)
    with open(fp2, 'w', encoding='utf-8') as f:
        f.write(content2)
    print('OK: Cleared DEFAULT_ALT_PAIRS')
else:
    print('SKIP: DEFAULT_ALT_PAIRS pattern not found')

print('Done!')
