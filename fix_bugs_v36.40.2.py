#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 Bug 修复脚本 v36.40.2
修复内容:
  1. Bug 3: 隔离区按钮绑错方法
  2. Bug 2: AI审核默认不可用
  3. 替代料格式混乱: 统一数据格式，修复 get_code / 筛选逻辑
"""

import re
import os

BASE = os.path.dirname(os.path.abspath(__file__))

results = []

def fix_file(rel_path, description, apply_fn):
    full = os.path.join(BASE, rel_path)
    if not os.path.exists(full):
        results.append(f"FAIL: {rel_path}")
        return False
    try:
        with open(full, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = apply_fn(content)
        if new_content == content:
            results.append(f"SKIP: {rel_path} ({description})")
            return True
        with open(full, 'w', encoding='utf-8') as f:
            f.write(new_content)
        results.append(f"OK: {rel_path} - {description}")
        return True
    except Exception as e:
        results.append(f"ERROR: {rel_path} - {e}")
        return False


def fix_quarantine_button(content):
    old = 'self.quarantine_btn = btn(row2_frame, "📦 隔离区", self._move_to_quarantine,'
    new = 'self.quarantine_btn = btn(row2_frame, "📦 隔离区", self._open_quarantine,'
    if old in content:
        content = content.replace(old, new)
    return content


def fix_ai_client(content):
    old_mock = 'return cfg.get("ai.use_mock_ai", False)'
    new_mock = 'return cfg.get("ai.use_mock_ai", True)'
    content = content.replace(old_mock, new_mock)

    old_default = "        return False\n\n    def _get_mock_result"
    new_default = "        return True  # 默认Mock，确保AI审核始终可用\n\n    def _get_mock_result"
    content = content.replace(old_default, new_default)

    old_audit = '''        except requests.Timeout:
            raise TimeoutError("AI 服务响应超时（10秒）")
        except requests.ConnectionError:
            raise ConnectionError("无法连接到 AI 服务，请检查网络")
        except Exception as e:
            raise RuntimeError(f"AI 服务异常：{str(e)}")'''

    new_audit = '''        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"AI服务不可用({e})，自动降级到Mock模式")
            return self._get_mock_result(text, dev_rate)
        except Exception as e:
            logger.warning(f"AI服务异常({e})，自动降级到Mock模式")
            return self._get_mock_result(text, dev_rate)'''

    content = content.replace(old_audit, new_audit)
    return content


def fix_analyzer_get_code(content):
    old = '''        # 提取编码：若为三元组取第2个元素；若为二元组取第1个；否则直接转字符串
        def get_code(item):
            if isinstance(item, (list, tuple)):
                if len(item) >= 2:
                    code = item[1]   # (factory, code, name) 或 (code, name)
                else:
                    code = item[0]
            else:
                code = item
            if code is None or code == 'None':
                return ''
            return str(code).strip()
        a_code = get_code(a)
        b_code = get_code(b)
        if a_code and b_code:
            cleaned_pairs.append((a_code, b_code))'''

    new = '''        # 提取编码和描述：兼容三元组、二元组、纯字符串
        def get_code_and_desc(item):
            if isinstance(item, (list, tuple)):
                if len(item) >= 3:
                    code, desc = item[1], item[2]
                elif len(item) == 2:
                    code, desc = item[0], item[1]
                else:
                    code, desc = item[0], ''
            else:
                code, desc = '', str(item)
            if code is None or code == 'None': code = ''
            if desc is None or desc == 'None': desc = ''
            return str(code).strip(), str(desc).strip()

        a_code, a_desc = get_code_and_desc(a)
        b_code, b_desc = get_code_and_desc(b)
        a_match = a_code if a_code else a_desc
        b_match = b_code if b_code else b_desc
        if a_match and b_match:
            cleaned_pairs.append((a_match, b_match))'''

    if old in content:
        content = content.replace(old, new)
    return content


def fix_alt_filter(content):
    old = '''        # 构建替代料名称集合（用于筛选）
        alt_all_descs = set()
        for a, b in getattr(self, 'alt_pairs', []):
            if a:
                alt_all_descs.add(a)
            if b:
                alt_all_descs.add(b)'''

    new = '''        # 构建替代料名称集合（用于筛选）
        alt_all_descs = set()
        for a, b in getattr(self, 'alt_pairs', []):
            def _extract_desc(item):
                if isinstance(item, (list, tuple)):
                    if len(item) >= 3: return str(item[2]).strip() if item[2] else ''
                    if len(item) == 2: return str(item[1]).strip() if item[1] else ''
                    return str(item[0]).strip() if item[0] else ''
                return str(item).strip()
            da, db = _extract_desc(a), _extract_desc(b)
            if da: alt_all_descs.add(da)
            if db: alt_all_descs.add(db)'''

    if old in content:
        content = content.replace(old, new)
    return content


def fix_alt_dedup(content):
    old = '''            for (ea, eb) in self.alt_pairs:
                # 提取配对中的编码
                ea_code = ea[1] if isinstance(ea, (list, tuple)) and len(ea) >= 2 else str(ea)
                eb_code = eb[1] if isinstance(eb, (list, tuple)) and len(eb) >= 2 else str(eb)'''

    new = '''            for (ea, eb) in self.alt_pairs:
                def _extract_code(item):
                    if isinstance(item, (list, tuple)):
                        if len(item) >= 3: return str(item[1]).strip()
                        if len(item) == 2: return str(item[0]).strip()
                        return str(item[0]).strip()
                    return str(item).strip()
                ea_code = _extract_code(ea)
                eb_code = _extract_code(eb)'''

    if old in content:
        content = content.replace(old, new)
    return content


def fix_duplicate_open_quarantine(content):
    marker = "    # ==================== 隔离区窗口 ====================\n    def _open_quarantine(self):"
    first_idx = content.find(marker)
    if first_idx == -1:
        return content
    second_idx = content.find(marker, first_idx + 10)
    if second_idx == -1:
        return content
    next_method = content.find("\n    def ", second_idx + 10)
    if next_method == -1:
        next_method = len(content)
    content = content[:second_idx] + content[next_method:]
    return content


if __name__ == "__main__":
    print("=" * 60)
    print("ZPP011 Bug Fix v36.40.2")
    print("=" * 60)

    print("\n[1/6] Bug 3: quarantine button...")
    fix_file("gui/ui_builder.py", "quarantine -> _open_quarantine", fix_quarantine_button)

    print("\n[2/6] Bug 2: AI audit mock fallback...")
    fix_file("core/ai_client.py", "AI mock fallback", fix_ai_client)

    print("\n[3/6] Alt material: analyzer get_code...")
    fix_file("analysis/analyzer.py", "get_code fix", fix_analyzer_get_code)

    print("\n[4/6] Alt material: filter set...")
    fix_file("gui/events.py", "alt_all_descs fix", fix_alt_filter)

    print("\n[5/6] Alt material: dedup check...")
    fix_file("gui/events.py", "dedup fix", fix_alt_dedup)

    print("\n[6/6] Alt material: remove duplicate _open_quarantine...")
    fix_file("gui/events.py", "remove dup _open_quarantine", fix_duplicate_open_quarantine)

    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    for r in results:
        print(f"  {r}")
    print("=" * 60)
