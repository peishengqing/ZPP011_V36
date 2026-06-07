# -*- coding: utf-8 -*-
"""
ZPP011 健康检查对话框
轻量级实现，无额外依赖（不需要 psutil）
"""
import sys
import os
import shutil
import platform
import importlib

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class HealthCheckDialog(QDialog):
    """健康检查面板，检查运行环境、依赖、配置、磁盘空间等"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统健康检查")
        self.setMinimumSize(700, 500)
        self._setup_ui()
        self._run_checks()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("🔍 ZPP011 系统健康检查")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.text)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.copy_btn = QPushButton("复制到剪贴板")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _run_checks(self):
        lines = []
        lines.append("=" * 60)
        lines.append("  ZPP011 系统健康检查报告")
        lines.append(f"  生成时间：{self._now()}")
        lines.append("=" * 60)
        lines.append("")

        # 1. 系统信息
        lines += self._check_system()

        # 2. Python 环境
        lines += self._check_python()

        # 3. 关键依赖
        lines += self._check_dependencies()

        # 4. 项目模块
        lines += self._check_project_modules()

        # 5. 磁盘空间
        lines += self._check_disk_space()

        # 6. 配置与数据目录
        lines += self._check_directories()

        # 7. 输出目录可写性
        lines += self._check_output_writable()

        lines.append("")
        lines.append("=" * 60)
        lines.append("  检查完成")
        lines.append("=" * 60)

        self.text.setText("\n".join(lines))

    def _check_system(self):
        lines = ["", "--- 系统信息 ---"]
        lines.append(f"  操作系统：{platform.system()} {platform.release()}")
        lines.append(f"  机器名：  {platform.node()}")
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.kernel32.GetComputerNameW(ctypes.byref(buf), ctypes.byref(ctypes.c_int(256)))
            lines.append(f"  用户名：  {os.getlogin()}")
        except Exception:
            pass
        lines.append("")
        return lines

    def _check_python(self):
        lines = ["--- Python 环境 ---"]
        lines.append(f"  Python 版本：{sys.version.split()[0]}")
        lines.append(f"  可执行文件：{sys.executable}")
        lines.append(f"  工作目录：  {os.getcwd()}")
        lines.append("")
        return lines

    def _check_dependencies(self):
        lines = ["--- 关键依赖检查 ---"]
        deps = [
            ("pandas", "数据处理"),
            ("openpyxl", "Excel 读写"),
            ("PySide6", "GUI 框架"),
            ("pptx", "PPT 生成"),
            ("matplotlib", "图表生成（可选）"),
            ("numpy", "数值计算"),
        ]
        for mod_name, desc in deps:
            ok, ver = self._try_import(mod_name)
            if ok:
                lines.append(f"  ✅ {mod_name:<18} v{ver:<12} ({desc})")
            else:
                if mod_name == "matplotlib":
                    lines.append(f"  ⚠️ {mod_name:<18} {'未安装':<12} ({desc})")
                else:
                    lines.append(f"  ❌ {mod_name:<18} {'未安装':<12} ({desc})")
        lines.append("")
        return lines

    def _check_project_modules(self):
        lines = ["--- 项目模块检查 ---"]
        # 正确的模块路径！
        project_modules = [
            ("analysis.analyzer", "分析引擎"),
            ("analysis.net_offset", "净偏差计算"),
            ("ppt_generator", "PPT生成器"),
            ("core.rule_engine", "规则引擎"),
            ("gui_pyside6.models.workers", "工作线程"),
            ("gui_pyside6.models.data_frame_model", "数据模型"),
            ("gui_pyside6.widgets.filter_panel", "筛选面板"),
        ]
        for mod, desc in project_modules:
            try:
                importlib.import_module(mod)
                lines.append(f"  ✅ {mod} ({desc})")
            except Exception as e:
                lines.append(f"  ❌ {mod} →  {e}")
        lines.append("")
        return lines

    def _check_disk_space(self):
        lines = ["--- 磁盘空间 ---"]
        try:
            work_dir = os.getcwd()
            disk = shutil.disk_usage(work_dir)
            free_gb = disk.free / (1024 ** 3)
            total_gb = disk.total / (1024 ** 3)
            used_pct = (disk.used / disk.total) * 100
            lines.append(f"  工作目录磁盘：{work_dir[:2]}")
            lines.append(f"  总容量：    {total_gb:.1f} GB")
            lines.append(f"  剩余空间：  {free_gb:.1f} GB")
            lines.append(f"  使用率：    {used_pct:.1f}%")
            if free_gb < 1:
                lines.append("  ⚠️ 剩余空间不足 1GB，请及时清理！")
            elif free_gb < 5:
                lines.append("  ⚠️ 剩余空间不足 5GB，建议清理。")
            else:
                lines.append("  ✅ 磁盘空间充足")
        except Exception as e:
            lines.append(f"  检查失败：{e}")
        lines.append("")
        return lines

    def _check_directories(self):
        lines = ["--- 配置与数据目录 ---"]
        paths = [
            ("用户文档目录", os.path.expanduser("~/Documents")),
            ("ZPP011 输出目录", os.path.expanduser("~/Documents/ZPP011分析报告")),
            (".workbuddy 配置", os.path.expanduser("~/.workbuddy")),
        ]
        for label, path in paths:
            if os.path.exists(path):
                try:
                    nfiles = sum([len(files) for _, _, files in os.walk(path)][:10])
                    lines.append(f"  ✅ {label}：{path}（存在，约 {nfiles} 个文件）")
                except Exception:
                    lines.append(f"  ✅ {label}：{path}（存在）")
            else:
                lines.append(f"  ⚠️ {label}：{path}（不存在，将自动创建）")
        lines.append("")
        return lines

    def _check_output_writable(self):
        lines = ["--- 输出目录可写性 ---"]
        output_dir = os.path.expanduser("~/Documents/ZPP011分析报告")
        try:
            os.makedirs(output_dir, exist_ok=True)
            test_file = os.path.join(output_dir, "_health_check_test.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            lines.append(f"  ✅ 输出目录可写：{output_dir}")
        except Exception as e:
            lines.append(f"  ❌ 输出目录不可写：{e}")
        lines.append("")
        return lines

    @staticmethod
    def _try_import(mod_name):
        try:
            mod = importlib.import_module(mod_name)
            ver = getattr(mod, "__version__", "unknown")
            return True, str(ver)
        except Exception:
            return False, "N/A"

    @staticmethod
    def _now():
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _copy_to_clipboard(self):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        QMessageBox.information(self, "已复制", "健康检查报告已复制到剪贴板")
