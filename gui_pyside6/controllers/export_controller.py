# -*- coding: utf-8 -*-
"""
导出控制器 — 负责表格导出、Excel导出、PPT生成
"""
import os
import traceback
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox, QFileDialog

from gui_pyside6.save_guard import safe_save, friendly_error



def open_file(filepath):
    """跨平台打开文件"""
    import platform
    system = platform.system()
    if system == 'Windows':
        import os
        os.startfile(filepath)
    elif system == 'Darwin':  # macOS
        import subprocess
        subprocess.run(['open', filepath])
    else:  # Linux and others
        import subprocess
        subprocess.run(['xdg-open', filepath])

class ExportController(QObject):
    log_message = Signal(str, str)           # (msg, level)

    def __init__(self, parent=None):
        super().__init__(parent)

    def export_current_table(self, audit_data, parent_widget):
        """导出当前表格（仅当前筛选后的数据）"""
        if audit_data is None or audit_data.empty:
            QMessageBox.warning(parent_widget, "提示", "无数据")
            return False
        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget, "导出当前表格", "偏差明细.xlsx", "Excel files (*.xlsx)"
        )
        if file_path:
            try:
                saved = safe_save(
                    parent_widget, file_path,
                    lambda p: audit_data.to_excel(p, index=False),
                    what="表格",
                )
                if not saved:
                    self.log_message.emit("导出已取消（目标文件被占用）", "warning")
                    return False
                QMessageBox.information(parent_widget, "成功", f"已导出到 {saved}")
                self.log_message.emit(f"已导出当前表格到 {saved}", "info")
                return True
            except Exception as e:
                traceback.print_exc()
                QMessageBox.critical(parent_widget, "错误", friendly_error(file_path, e))
                self.log_message.emit(f"导出失败: {e}", "error")
        return False

    def generate_simple_ppt(self, audit_data, analysis_output_path, output_dir, parent_widget, log_cb=None):
        """生成简明版PPT"""
        if audit_data is None or audit_data.empty:
            QMessageBox.warning(parent_widget, "提示", "无数据，请先完成分析")
            return False

        excel_path = analysis_output_path
        if not excel_path or not os.path.exists(excel_path):
            excel_path, _ = QFileDialog.getOpenFileName(
                parent_widget, "请选择分析结果 Excel 文件", "", "Excel files (*.xlsx)"
            )
            if not excel_path:
                return False

        from core.advanced_ppt_generator_v2 import generate_advanced_report_v2

        if not output_dir:
            output_dir = os.path.expanduser("~/Documents/ZPP011分析报告")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"ZPP011智能报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        )
        try:
            if log_cb:
                log_cb(f"开始生成智能PPT：{excel_path}", "info")
            success = generate_advanced_report_v2(excel_path, output_path, log_cb=log_cb)
            if success:
                if log_cb:
                    log_cb(f"PPT生成成功：{output_path}", "info")
                if QMessageBox.question(
                    parent_widget, "生成成功", f"报告已生成：\n{output_path}\n是否打开？"
                ) == QMessageBox.Yes:
                    open_file(output_path)
                self.log_message.emit(f"PPT生成成功：{output_path}", "info")
                return True
            else:
                QMessageBox.warning(parent_widget, "生成失败", "PPT生成返回失败，请查看日志")
                return False
        except Exception as e:
            traceback.print_exc()
            if log_cb:
                log_cb(f"PPT生成失败: {e}", "error")
            QMessageBox.critical(parent_widget, "错误", f"生成失败: {e}")
            self.log_message.emit(f"PPT生成失败: {e}", "error")
            return False

    def generate_advanced_report(self, audit_data, analysis_output_path, output_dir, parent_widget, log_cb=None):
        """生成专业版详细分析报告（20+页）"""
        if audit_data is None or audit_data.empty:
            QMessageBox.warning(parent_widget, "提示", "无数据，请先完成分析")
            return False

        excel_path = analysis_output_path
        if not excel_path or not os.path.exists(excel_path):
            excel_path, _ = QFileDialog.getOpenFileName(
                parent_widget, "请选择分析结果 Excel 文件", "", "Excel files (*.xlsx)"
            )
            if not excel_path:
                return False

        from core.advanced_ppt_generator_v2 import generate_advanced_report_v2

        if not output_dir:
            output_dir = os.path.expanduser("~/Documents/ZPP011分析报告")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"ZPP011专业报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        )
        try:
            if log_cb:
                log_cb(f"开始生成专业版智能PPT：{excel_path}", "info")
            success = generate_advanced_report_v2(excel_path, output_path, log_cb=log_cb)
            if success:
                if log_cb:
                    log_cb(f"专业版报告生成成功：{output_path}", "info")
                if QMessageBox.question(
                    parent_widget, "生成成功", f"报告已生成：\n{output_path}\n是否打开？"
                ) == QMessageBox.Yes:
                    open_file(output_path)
                self.log_message.emit(f"专业版报告生成成功：{output_path}", "info")
                return True
            else:
                QMessageBox.warning(parent_widget, "生成失败", "专业版报告生成返回失败，请查看日志")
                return False
        except Exception as e:
            traceback.print_exc()
            if log_cb:
                log_cb(f"专业版报告生成失败: {e}", "error")
            QMessageBox.critical(parent_widget, "错误", f"生成失败: {e}")
            self.log_message.emit(f"专业版报告生成失败: {e}", "error")
            return False
