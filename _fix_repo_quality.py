# -*- coding: utf-8 -*-
"""
ZPP011_V36 仓库质量修复脚本 v2.0
在仓库根目录运行：python _fix_repo_quality.py
修复项：
  1. 移除 BOM 编码（UTF-8 BOM → UTF-8 无 BOM）
  2. 删除 .bak 备份文件
  3. 删除一次性临时脚本
  4. 替换硬编码 Windows 路径为动态路径
"""
import os
import sys
import re

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

def fix_bom():
    """移除所有 Python 文件的 BOM"""
    bom_files = []
    for root, dirs, files in os.walk(REPO_DIR):
        if '.git' in root:
            continue
        for f in files:
            if f.endswith('.py'):
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'rb') as fh:
                        raw = fh.read()
                    if raw[:3] == b'\xef\xbb\xbf':
                        with open(fp, 'wb') as fh:
                            fh.write(raw[3:])
                        bom_files.append(fp)
                except Exception as e:
                    print(f"  [ERROR] {fp}: {e}")
    return bom_files

def remove_bak_files():
    """删除所有 .bak 文件"""
    removed = []
    for root, dirs, files in os.walk(REPO_DIR):
        if '.git' in root:
            continue
        for f in files:
            if '.bak' in f:
                fp = os.path.join(root, f)
                os.remove(fp)
                removed.append(fp)
    return removed

def remove_temp_scripts():
    """删除一次性临时脚本"""
    temp_scripts = [
        '_fix_changelog.py', '_fix_and_add_v391.py', '_fix_and_add_v391_v2.py',
        '_add_changelog_v391.py', '_add_v391.py', '_update_v391_changelog.py',
        '_update_build_datetime.py', '_debug_changelog.py', 'minifix_v1.py',
        'final_verify.py', 'update_analyzer.py', 'implement_ppt_v12.py',
        'implement_s01.py', 'find_order_date_usage.py', 'build_with_backup.py',
    ]
    removed = []
    for name in temp_scripts:
        fp = os.path.join(REPO_DIR, name)
        if os.path.exists(fp):
            os.remove(fp)
            removed.append(fp)
    return removed

def fix_hardcoded_paths():
    """替换硬编码 Windows 路径为动态路径"""
    replacements = {
        # storage.py: 数据目录
        'storage/storage.py': [
            (
                'def _get_app_dir():\n    """返回应用数据目录（优先 E:\\zpp011_dev\\.zpp011_audit，兼容旧版 ~/.zpp011_audit）"""\n    new_dir = r"E:\\zpp011_dev\\.zpp011_audit"\n    old_dir = os.path.join(os.path.expanduser("~"), ".zpp011_audit")\n    os.makedirs(new_dir, exist_ok=True)\n    # 一次性迁移：旧目录存在且新目录数据库不存在时，复制过去\n    old_db = os.path.join(old_dir, "audit_log.db")\n    new_db = os.path.join(new_dir, "audit_log.db")\n    if os.path.exists(old_db) and not os.path.exists(new_db):\n        try:\n            shutil.copy2(old_db, new_db)\n        except Exception:\n            pass  # 迁移失败不影响启动\n    return new_dir',
                'def _get_app_dir():\n    """返回应用数据目录（~/.zpp011_audit）"""\n    app_dir = os.path.join(os.path.expanduser("~"), ".zpp011_audit")\n    os.makedirs(app_dir, exist_ok=True)\n    return app_dir'
            ),
        ],
        # gui/app.py: changelog 路径
        'gui/app.py': [
            (
                "getattr(self, 'workspace_dir', r'E:\\ZPP011_Data')",
                "getattr(self, 'workspace_dir', os.path.dirname(os.path.abspath(__file__)))"
            ),
        ],
        # gui/event_handlers/export_events.py: 导出默认目录
        'gui/event_handlers/export_events.py': [
            (
                'default_dir = r"E:\\zpp011_dev\\ZPP011偏差分析"',
                'default_dir = os.path.join(os.path.expanduser("~"), "ZPP011偏差分析")'
            ),
        ],
        # gui/event_handlers/utils_events.py: 导出默认目录
        'gui/event_handlers/utils_events.py': [
            (
                'default_dir = r"E:\\zpp011_dev\\ZPP011导出文件原数据"',
                'default_dir = os.path.join(os.path.expanduser("~"), "ZPP011导出文件原数据")'
            ),
        ],
        # run_tests.py: 工作目录
        'run_tests.py': [
            (
                "sys.path.insert(0, r'E:\\zpp011_dev\\模块化脚本')",
                "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))"
            ),
            (
                "cwd=r'E:\\zpp011_dev\\模块化脚本',",
                "cwd=os.path.dirname(os.path.abspath(__file__)),"
            ),
        ],
        # tests/s01_regression_test.py: 测试数据路径
        'tests/s01_regression_test.py': [
            (
                "test_excel = r'E:\\zpp011_dev\\模块化脚本\\tests\\s01_test_data.xlsx'",
                "test_excel = os.path.join(os.path.dirname(os.path.abspath(__file__)), 's01_test_data.xlsx')"
            ),
            (
                "latest = file_service.find_latest_file(\"s01_test_data*.xlsx\", r'E:\\zpp011_dev\\模块化脚本\\tests')",
                "latest = file_service.find_latest_file(\"s01_test_data*.xlsx\", os.path.dirname(os.path.abspath(__file__)))"
            ),
            (
                "test_ppt = r'E:\\zpp011_dev\\模块化脚本\\tests\\s01_test_output.pptx'",
                "test_ppt = os.path.join(os.path.dirname(os.path.abspath(__file__)), 's01_test_output.pptx')"
            ),
        ],
    }

    fixed = []
    for rel_path, rules in replacements.items():
        fp = os.path.join(REPO_DIR, rel_path)
        if not os.path.exists(fp):
            continue
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        changed = False
        for old, new in rules:
            if old in content:
                content = content.replace(old, new)
                changed = True
        if changed:
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(content)
            fixed.append(rel_path)
    return fixed

def verify():
    """验证修复结果"""
    import ast
    results = {'BOM': 0, 'BAK': 0, 'LARGE': 0, 'HARDCODED': 0, 'SYNTAX': 0}
    for root, dirs, files in os.walk(REPO_DIR):
        if '.git' in root:
            continue
        for f in files:
            fp = os.path.join(root, f)
            if '.bak' in f:
                results['BAK'] += 1
            try:
                if os.path.getsize(fp) > 102400:
                    results['LARGE'] += 1
            except:
                pass
            if not f.endswith('.py'):
                continue
            with open(fp, 'rb') as fh:
                if fh.read(3) == b'\xef\xbb\xbf':
                    results['BOM'] += 1
            try:
                with open(fp, 'r', encoding='utf-8') as fh:
                    ast.parse(fh.read())
            except SyntaxError:
                results['SYNTAX'] += 1
            with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                for line in fh:
                    if re.search(r'[A-Z]:\\\\', line) and 'sys.path' not in line:
                        results['HARDCODED'] += 1
    return results

if __name__ == '__main__':
    print("=" * 60)
    print("  ZPP011_V36 仓库质量修复脚本 v2.0")
    print("=" * 60)

    print("\n[1/4] 移除 BOM 编码...")
    bom = fix_bom()
    print(f"  已修复 {len(bom)} 个文件")

    print("\n[2/4] 删除 .bak 备份文件...")
    bak = remove_bak_files()
    print(f"  已删除 {len(bak)} 个文件")

    print("\n[3/4] 删除一次性临时脚本...")
    tmp = remove_temp_scripts()
    print(f"  已删除 {len(tmp)} 个文件")

    print("\n[4/4] 替换硬编码路径...")
    hc = fix_hardcoded_paths()
    print(f"  已修复 {len(hc)} 个文件")
    for f in hc:
        print(f"    - {f}")

    print("\n--- 验证 ---")
    r = verify()
    all_ok = all(v == 0 for v in r.values())
    for k, v in r.items():
        status = "PASS" if v == 0 else "FAIL"
        print(f"  [{status}] {k}: {v}")

    total = len(bom) + len(bak) + len(tmp) + len(hc)
    print(f"\n{'=' * 60}")
    print(f"  修复完成，共处理 {total} 项")
    print(f"  验证结果: {'ALL CLEAR' if all_ok else '存在问题，请检查'}")
    print(f"{'=' * 60}")
