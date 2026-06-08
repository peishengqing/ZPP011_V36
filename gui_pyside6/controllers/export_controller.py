# -*- coding: utf-8 -*-
"""
导出控制器 — 负责表格导出、Excel导出、PPT生成
"""
import os
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox, QFileDialog


class ExportController(QObject):
    log_message = Signal(str)

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
                audit_data.to_excel(file_path, index=False)
                QMessageBox.information(parent_widget, "成功", f"已导出到 {file_path}")
                self.log_message.emit(f"已导出当前表格到 {file_path}", "info")
                return True
            except Exception as e:
                QMessageBox.critical(parent_widget, "错误", f"导出失败: {e}")
                self.log_message.emit(f"导出失败: {e}", "error")
        return False

    def export_full_excel(self, audit_data, current_input_file, analysis_params, parent_widget):
        """导出完整Excel（可选择多Sheet完整报告）"""
        try:
            if audit_data is None or audit_data.empty:
                QMessageBox.warning(parent_widget, "提示", "无数据，请先进行分析")
                return False

            default_name = f"ZPP011偏差分析最终版_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            save_path, _ = QFileDialog.getSaveFileName(
                parent_widget, "保存完整Excel文件", default_name, "Excel files (*.xlsx)"
            )
            if not save_path:
                return False

            # 如果有分析参数，询问是否生成完整多Sheet
            if analysis_params and current_input_file:
                reply = QMessageBox.question(
                    parent_widget, "导出选项",
                    "是否生成完整多Sheet分析报告（含汇总统计、预警颜色等）？\n\n"
                    "点击「是」→ 生成完整多Sheet Excel（需重新分析，较慢）\n"
                    "点击「否」→ 仅导出当前表格数据（快速）",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    return self._export_full_analysis_excel(save_path, analysis_params, parent_widget)

            # 仅导出当前表格数据
            try:
                audit_data.to_excel(save_path, sheet_name='完整偏差明细', index=False)
                QMessageBox.information(parent_widget, "成功", f"已导出到 {save_path}")
                self.log_message.emit(f"已导出完整Excel到 {save_path}", "info")
                return True
            except Exception as e:
                QMessageBox.critical(parent_widget, "错误", f"导出失败: {e}")
                self.log_message.emit(f"导出失败: {e}", "error")
                return False
        except Exception as e:
            error_msg = f"导出完整Excel失败: {e}"
            self.log_message.emit(error_msg, "error")
            QMessageBox.critical(parent_widget, "导出失败",
                 f"导出完整Excel过程中发生错误：\n{e}\n\n请检查磁盘空间或文件是否被占用。")
            return False
    def _export_full_analysis_excel(self, save_path, analysis_params, parent_widget):
        """使用缓存的分析参数重新生成完整多Sheet Excel"""
        try:
            progress_dlg = QProgressDialog("正在重新分析生成完整报告...", "取消", 0, 100, parent_widget)
            progress_dlg.setWindowTitle("导出中")
            progress_dlg.setWindowModality(Qt.WindowModal)
            progress_dlg.show()

            from analysis.analyzer import do_analysis_v2
            result = do_analysis_v2(
                input_file=analysis_params['input_file'],
                output_dir=None,
                alt_pairs=analysis_params['alt_pairs'],
                progress_callback=lambda step_idx, step_name, percent: progress_dlg.setValue(percent),
                cancel_check=lambda *args: progress_dlg.wasCanceled(),
                start_date=analysis_params.get('start_date'),
                end_date=analysis_params.get('end_date'),
                material_search=analysis_params.get('material_search'),
                output_path=save_path,
                enable_net_offset=True,
                return_dataframe=False,
            )
            progress_dlg.close()
            QMessageBox.information(
                parent_widget, "成功",
                f"完整分析报告已导出到\n{save_path}\n\n"
                "包含Sheet:\n"
                "📋 分析说明 · 汇总统计(带预警颜色)\n"
                "完整偏差明细 · 替代料明细 · 无备注预警\n"
                "中间地带明细 · 异常预警 · 偏差金额分析\n"
                "偏差原因汇总 · 偏差原因分析 · 趋势分析"
            )
            self.log_message.emit(f"已导出完整分析报告到 {save_path}", "info")
            return True
        except Exception as e:
            QMessageBox.critical(parent_widget, "错误", f"导出完整报告失败: {e}")
            self.log_message.emit(f"导出完整报告失败: {e}", "error")
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
                    os.startfile(output_path)
                self.log_message.emit(f"PPT生成成功：{output_path}", "info")
                return True
            else:
                QMessageBox.warning(parent_widget, "生成失败", "PPT生成返回失败，请查看日志")
                return False
        except Exception as e:
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
                    os.startfile(output_path)
                self.log_message.emit(f"专业版报告生成成功：{output_path}", "info")
                return True
            else:
                QMessageBox.warning(parent_widget, "生成失败", "专业版报告生成返回失败，请查看日志")
                return False
        except Exception as e:
            if log_cb:
                log_cb(f"专业版报告生成失败: {e}", "error")
            QMessageBox.critical(parent_widget, "错误", f"生成失败: {e}")
            self.log_message.emit(f"专业版报告生成失败: {e}", "error")
            return False
