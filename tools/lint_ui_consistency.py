#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI 一致性检查工具
功能：
1. 扫描 UI 代码中的硬编码十六进制颜色（绕过 tokens）
2. 运行轻量级的对话框构造测试（验证 dialogs 的基础可用性）
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple

# 颜色正则：#RGB、#RRGGBB、#RRGGBBAA
HEX_COLOR_PATTERN = re.compile(r'#[0-9a-fA-F]{3,8}\b')

# 排除目录
EXCLUDE_DIRS = {'build', 'dist', '.git', '__pycache__', 'venv', '.venv', 'node_modules'}

# 对话框路径，用于烟雾测试
DIALOG_FILES = list(Path('gui_pyside6/dialogs').glob('*.py'))

# 忽略注释行（但注意：#开头的可能是一行注释，也可能是 #FFFFFF 这样的色值）
# 需要更精细的判断
def is_comment_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith('#') and not re.search(r'=\s*["\']#', line)

# 需要排除的特定模式（这些是 benign 的使用场景）
EXCLUDE_FILE_PATTERNS = [
    re.compile(r'core[\\/]guizang'),  # guizang 模块的颜色定义是特定需求
    re.compile(r'analysis[\\/]dashboard_html'),  # 这里用常量定义颜色是合理的
    re.compile(r'_archive'),  # 归档文件，不影响
]

EXCLUDE_LINE_PATTERNS = [
    re.compile(r'token.*#', re.IGNORECASE),  # 注释中关于 token 的说明
    re.compile(r'LEGACY_.*#', re.IGNORECASE),  # 临时遗留颜色定义
    re.compile(r'#.*颜色.*说明', re.IGNORECASE),  # 中文注释 about colors
]


def scan_hardcoded_colors(root_dir: str) -> List[Dict[str, any]]:
    """扫描 UI 代码中的硬编码十六进制颜色"""
    violations = []
    root_path = Path(root_dir)

    for py_file in root_path.rglob('*.py'):
        # 跳过排除目录
        if any(excl in str(py_file) for excl in EXCLUDE_DIRS):
            continue

        # 跳过特定文件模式
        if any(p.search(str(py_file)) for p in EXCLUDE_FILE_PATTERNS):
            continue

        with open(py_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line_no, line in enumerate(lines, 1):
            # 跳过纯注释行
            if is_comment_line(line):
                continue

            # 检查是否包含排除模式的行
            if any(p.search(line) for p in EXCLUDE_LINE_PATTERNS):
                continue

            # 找到所有颜色匹配
            matches = HEX_COLOR_PATTERN.findall(line)
            for color in matches:
                # 简单的启发式规则：忽略 rgba/transparent 等
                if 'rgba' in line.lower() or 'transparent' in line.lower():
                    continue

                # 标记为违规
                violations.append({
                    'file': str(py_file.relative_to(root_dir)),
                    'line': line_no,
                    'color': color,
                    'content': line.strip()
                })

    return violations


def run_dialog_smoke_test() -> List[str]:
    """运行对话框的轻量级构造测试（Offscreen）"""
    import sys
    from pathlib import Path

    # 设置 offscreen 平台
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QCoreApplication

        # 初始化 QApplication（需要在导入其他模块之前）
        app = QApplication(sys.argv)
        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

        import importlib
        failures = []

        for dialog_path in DIALOG_FILES:
            try:
                module_name = '.'.join(dialog_path.relative_to(Path.cwd()).with_suffix('').parts)
                # 动态导入模块
                module = importlib.import_module(module_name)

                # 尝试查找包含 QDialog 的子类
                dialog_cls = None
                for name, obj in module.__dict__.items():
                    if (inspect.isclass(obj) and
                        issubclass(obj, QDialog) and
                        obj.__module__ == module_name):
                        dialog_cls = obj
                        break

                if dialog_cls is None:
                    continue  # 没有找到对话框类，跳过

                # 尝试构造一个最小实例（带 parent）
                from PySide6.QtWidgets import QDialog
                # 创建一个 dummy parent（不需要实际窗口）
                dummy_parent = QDialog()
                instance = dialog_cls(dummy_parent)
                # 简单的可视化检查：show 一下（offscreen 环境不会真正显示）
                instance.show()
                instance.close()

            except Exception as e:
                failures.append(f"{dialog_path.name}: {str(e)}")

        return failures

    except Exception as e:
        return [f"初始化 QApplication 失败: {str(e)}"]


def main():
    parser = argparse.ArgumentParser(description='UI 一致性检查工具')
    parser.add_argument('--scan', action='store_true', help='执行硬编码颜色扫描')
    parser.add_argument('--smoke', action='store_true', help='执行对话框烟雾测试')
    parser.add_argument('--all', action='store_true', help='执行所有检查')
    parser.add_argument('--root', default='.', help='项目根目录')

    args = parser.parse_args()

    if not any([args.scan, args.smoke, args.all]):
        parser.print_help()
        return

    # 执行颜色扫描
    if args.scan or args.all:
        print("=" * 60)
        print("硬编码颜色扫描")
        print("=" * 60)
        violations = scan_hardcoded_colors(args.root)
        if violations:
            print(f"发现 {len(violations)} 处硬编码颜色:")
            for v in violations:
                print(f"  {v['file']}:{v['line']}  {v['color']} -> {v['content'][:60]}")
            sys.exit(1)  # 有违规，非零退出
        else:
            print("未发现硬编码颜色")

    # 执行对话框烟雾测试
    if args.smoke or args.all:
        print("\n" + "=" * 60)
        print("对话框构造烟雾测试")
        print("=" * 60)
        try:
            failures = run_dialog_smoke_test()
            if failures:
                print(f"发现 {len(failures)} 个对话框构造失败:")
                for f in failures:
                    print(f"  {f}")

        except Exception as e:
            print(f"测试失败: {e}")

    print("\n检查完成")


if __name__ == '__main__':
    main()
