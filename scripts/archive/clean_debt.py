# -*- coding: utf-8 -*-
import os
import re

def scan_debt(root_dir: str = ".") -> list[str]:
    debt = []
    total_feedback = 0
    total_print = 0

    print("=" * 60)
    print("[INFO] ZPP011 技术债务扫描器")
    print("=" * 60)

    for root, _, files in os.walk(root_dir):
        if any(skip in root for skip in ["venv", "dist", "build", "tests", ".git"]):
            continue
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    file_feedback = 0
                    file_print = 0
                    line_matches = []
                    for line_num, line_content in enumerate(lines, 1):
                        if "@with_feedback" in line_content and "def with_feedback" not in line_content:
                            line_matches.append(f"  [WARN] 行 {line_num}: @with_feedback 残留")
                            file_feedback += 1
                            total_feedback += 1
                        if "print(" in line_content and "logger" not in line_content and "except" not in line_content:
                            if not line_content.strip().startswith("#"):
                                line_matches.append(f"  [WARN] 行 {line_num}: 调试 print 语句")
                                file_print += 1
                                total_print += 1
                    if file_feedback > 0 or file_print > 0:
                        debt.append(f"\n[WARN] {file_path}:")
                        debt.extend(line_matches)
                except Exception as e:
                    debt.append(f"\n[ERROR] 无法读取 {file_path}: {str(e)}")

    print(f"\n[INFO] 共发现 {total_feedback} 处 @with_feedback 残留")
    print(f"[INFO] 共发现 {total_print} 处 调试 print 语句")
    print("=" * 60)

    if total_feedback == 0 and total_print == 0:
        print("[OK] 技术债务已全部清理完毕！")
        return []

    with open("debt_list.txt", "w", encoding="utf-8") as f:
        f.write("ZPP011 技术债务清单\n" + "=" * 60 + "\n")
        f.write("\n".join(debt))
        f.write(f"\n\n总计：{total_feedback} 处 @with_feedback，{total_print} 处 print\n")
    print("[OK] 详细清单已写入 debt_list.txt")
    return debt

if __name__ == "__main__":
    scan_debt()
