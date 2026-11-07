# -*- coding: utf-8 -*-
"""
导出控制器 — 负责表格导出、Excel导出、PPT生成
"""
import os
import shutil
import traceback
from datetime import datetime
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog, QApplication

from gui_pyside6.widgets.toast import toast
from gui_pyside6.save_guard import safe_save, precheck_save_path, friendly_error
from gui_pyside6.utils.file_launcher import open_path


def open_file(filepath):
    """跨平台打开文件（唯一实现在 gui_pyside6/utils/file_launcher.py，v43.257 收口 GUI-001b）"""
    return open_path(filepath)


class ExportController(QObject):
    """导出逻辑控制器"""

    log_message = Signal(str, str)  # (msg, level)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

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
                toast(f"✅ 已导出表格到 {saved}", level="success", parent=parent_widget)
                self.log_message.emit(f"已导出当前表格到 {saved}", "info")
                return True
            except Exception as e:
                traceback.print_exc()
                QMessageBox.critical(parent_widget, "错误", friendly_error(file_path, e))
                self.log_message.emit(f"导出失败: {e}", "error")
        return False

    def export_full_excel(self, audit_data, current_input_file, analysis_params,
                          parent_widget, cache_path=None):
        """导出完整Excel（可选择多Sheet完整报告，支持缓存秒传）"""
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
                    "点击「是」→ 生成完整多Sheet Excel（缓存命中则秒传，否则重新分析）\n"
                    "点击「否」→ 仅导出当前表格数据（快速）",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    return self._export_full_analysis_excel(
                        save_path, analysis_params, parent_widget, cache_path
                    )

            # 仅导出当前表格数据
            try:
                saved = safe_save(
                    parent_widget, save_path,
                    lambda p: audit_data.to_excel(p, sheet_name='完整偏差明细', index=False),
                    what="表格",
                )
                if not saved:
                    self.log_message.emit("导出已取消（目标文件被占用）", "warning")
                    return False
                if QMessageBox.question(
                    parent_widget, "导出成功", f"文件已导出到：\n{saved}\n是否打开？"
                ) == QMessageBox.Yes:
                    open_file(saved)
                self.log_message.emit(f"已导出完整Excel到 {saved}", "info")
                return True
            except Exception as e:
                traceback.print_exc()
                QMessageBox.critical(parent_widget, "错误", friendly_error(save_path, e))
                self.log_message.emit(f"导出失败: {e}", "error")
                return False
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(parent_widget, "错误", f"导出完整Excel失败: {e}")
            self.log_message.emit(f"导出完整Excel失败: {e}", "error")
            return False

    def _export_full_analysis_excel(self, save_path, analysis_params, parent_widget,
                                      cache_path=None):
        """使用缓存的分析参数重新生成完整多Sheet Excel（优先使用缓存）"""

        # ---- 缓存命中：直接复制，秒传 ----
        if cache_path and os.path.exists(cache_path):
            try:
                saved = safe_save(
                    parent_widget, save_path,
                    lambda p: shutil.copy2(cache_path, p),
                    what="报告",
                )
                if not saved:
                    self.log_message.emit("导出已取消（目标文件被占用）", "warning")
                    return False
                save_path = saved
                if QMessageBox.question(
                    parent_widget, "导出成功",
                    f"完整分析报告已导出到\n{save_path}\n\n"
                    "（使用缓存，秒传完成）\n\n"
                    "包含Sheet:\n"
                    "📋 分析说明 · 汇总统计(带预警颜色)\n"
                    "完整偏差明细 · 替代料明细 · 无备注预警\n"
                    "中间地带明细 · 异常预警 · 偏差金额分析\n"
                    "偏差原因汇总 · 偏差原因分析 · 趋势分析\n\n"
                    "是否立即打开？"
                ) == QMessageBox.Yes:
                    open_file(save_path)
                self.log_message.emit(f"已导出完整分析报告到 {save_path} (缓存)", "info")
                return True
            except Exception as e:
                self.log_message.emit(f"缓存复制失败，回退重新分析: {e}", "warning")

        # 重新分析要跑几十秒，先确认目标文件写得进去，免得白算一场
        save_path = precheck_save_path(parent_widget, save_path, what="报告")
        if not save_path:
            self.log_message.emit("导出已取消（目标文件被占用）", "warning")
            return False

        try:
            progress_dlg = QProgressDialog("正在重新分析生成完整报告...", "取消", 0, 100, parent_widget)
            progress_dlg.setWindowTitle("导出中")
            progress_dlg.setWindowModality(Qt.WindowModal)
            progress_dlg.setMinimumDuration(0)  # 立即显示
            progress_dlg.show()
            QApplication.processEvents()  # 强制刷新UI，防止进度条不出来

            from analysis.analyzer import do_analysis_v2
            do_analysis_v2(
                input_file=analysis_params['input_file'],
                output_dir=None,
                alt_pairs=analysis_params['alt_pairs'],
                progress_callback=lambda step_idx, step_name, percent: (
                    progress_dlg.setValue(percent),
                    progress_dlg.setLabelText(f"{step_name} ({percent}%)"),
                    QApplication.processEvents(),  # 保持UI响应，防止"无响应"→被系统杀死
                )[0],
                cancel_check=lambda *args: (QApplication.processEvents(), progress_dlg.wasCanceled())[1],
                start_date=analysis_params.get('start_date'),
                end_date=analysis_params.get('end_date'),
                material_search=analysis_params.get('material_search'),
                output_path=save_path,
                enable_net_offset=True,
                return_dataframe=False,
                dyn_thresh=analysis_params.get('dyn_thresh'),
            )
            progress_dlg.setValue(100)
            progress_dlg.close()

            # 回存缓存：如果后台缓存还没生成完，这次的结果也可以缓存
            if cache_path and not os.path.exists(cache_path):
                try:
                    shutil.copy2(save_path, cache_path)
                except Exception:
                    pass  # 静默失败，不影响导出

            if QMessageBox.question(
                parent_widget, "导出成功",
                f"完整分析报告已导出到\n{save_path}\n\n"
                "包含Sheet:\n"
                "📋 分析说明 · 汇总统计(带预警颜色)\n"
                "完整偏差明细 · 替代料明细 · 无备注预警\n"
                "中间地带明细 · 异常预警 · 偏差金额分析\n"
                "偏差原因汇总 · 偏差原因分析 · 趋势分析\n\n"
                "是否立即打开？"
            ) == QMessageBox.Yes:
                open_file(save_path)
            self.log_message.emit(f"已导出完整分析报告到 {save_path}", "info")
            return True
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(parent_widget, "错误", friendly_error(save_path, e))
            self.log_message.emit(f"导出完整报告失败: {e}", "error")
            return False

    def generate_simple_ppt(self, audit_data, analysis_output_path, output_dir, parent_widget, log_cb=None):
        """生成「分厂版」智能PPT（9 页，TRAE 版式）"""
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

        # v43.157：简明版 → 换成 TRAE 分厂版（core/ppt_trae.py，9 页）
        # 数据全部从「汇总统计」表实时算，不再是硬编码；与专业版彻底分成两份报告。
        # 注意：ppt_trae 内部已把 DataError / Exception 都吃掉并返回 False，
        # 具体失败原因已写进 log_cb（error 级），此处不再重复 traceback。
        from core.ppt_trae import generate_trae_report

        if not output_dir:
            output_dir = os.path.expanduser("~/Documents/ZPP011分析报告")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"ZPP011分厂报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        )
        try:
            if log_cb:
                log_cb(f"开始生成智能PPT（分厂版9页）：{excel_path}", "info")
            success = generate_trae_report(excel_path, output_path, log_cb=log_cb)
            if success:
                if log_cb:
                    log_cb(f"分厂版PPT生成成功：{output_path}", "info")
                if QMessageBox.question(
                    parent_widget, "生成成功",
                    f"分厂版报告已生成：\n{output_path}\n\n"
                    "内容：封面 / 目录 / 总体概览 / 食品厂专题(2页)\n"
                    "饮料厂专题(2页) / 预警对比与建议 / 结尾\n\n是否打开？"
                ) == QMessageBox.Yes:
                    open_file(output_path)
                self.log_message.emit(f"PPT生成成功：{output_path}", "info")
                return True
            else:
                # 失败原因已由 ppt_trae 通过 log_cb 说清楚，这里只补一条可执行指引
                QMessageBox.warning(
                    parent_widget, "生成失败",
                    "分厂版PPT生成失败，请查看下方日志。\n\n"
                    "常见原因：所选 Excel 不是「完整分析报告」导出文件\n"
                    "（本报告需要含「汇总统计」Sheet 的分析结果）。"
                )
                return False
        except Exception as e:
            traceback.print_exc()
            if log_cb:
                log_cb(f"分厂版PPT生成失败: {e}", "error")
            QMessageBox.critical(parent_widget, "错误", f"生成失败: {e}")
            self.log_message.emit(f"分厂版PPT生成失败: {e}", "error")
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
                log_cb(f"开始生成专业版智能PPT（20+页）：{excel_path}", "info")
            # v43.156：显式传 mode="pro"，走 20+ 页深度版布局
            success = generate_advanced_report_v2(
                excel_path, output_path, log_cb=log_cb, mode="pro")
            if success:
                if log_cb:
                    log_cb(f"专业版报告生成成功：{output_path}", "info")
                if QMessageBox.question(
                    parent_widget, "生成成功", f"专业版报告已生成：\n{output_path}\n是否打开？"
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

    # ------------------- 完整报告导出逻辑（从 MainWindow 迁移） -------------------
    def on_export_full_excel(self, audit_data, current_input_file, analysis_params,
                             parent_widget, cache_path=None):
        """完整Excel导出入口"""
        return self.export_full_excel(audit_data, current_input_file, analysis_params, parent_widget, cache_path)

    def export_full_analysis_inline(self, save_path, analysis_params, cache_path, parent_widget):
        """生成完整多Sheet Excel（优先使用缓存）"""
        # 缓存命中：直接复制
        if cache_path and os.path.exists(cache_path):
            try:
                _saved = safe_save(parent_widget, save_path,
                                   lambda p: shutil.copy2(cache_path, p),
                                   what="报告")
                if not _saved:
                    self.log_message.emit("导出已取消（目标文件被占用）", "warning")
                    return
                save_path = _saved
                if QMessageBox.question(
                    parent_widget, "导出成功",
                    f"完整分析报告已导出到\n{save_path}\n\n"
                    "（使用缓存，秒传完成）\n\n"
                    "包含Sheet:\n"
                    "📋 分析说明 · 汇总统计(带预警颜色)\n"
                    "完整偏差明细 · 替代料明细 · 无备注预警\n"
                    "中间地带明细 · 异常预警 · 偏差金额分析\n"
                    "偏差原因汇总 · 偏差原因分析 · 趋势分析\n\n"
                    "是否立即打开？"
                ) == QMessageBox.Yes:
                    open_file(save_path)
                self.log_message.emit(f"已导出完整分析报告到 {save_path} (缓存)", "info")
                return
            except Exception as e:
                QMessageBox.warning(
                    parent_widget, "缓存复制失败",
                    f"缓存复制失败：{e}\n\n将重新分析生成报告。"
                )
                self.log_message.emit(f"缓存复制失败，回退重新分析: {e}", "warning")

        # 重新分析要跑几十秒，先确认目标文件写得进去，免得白算一场
        save_path = precheck_save_path(parent_widget, save_path, what="报告")
        if not save_path:
            self.log_message.emit("导出已取消（目标文件被占用）", "warning")
            return

        # 重新分析生成（转后台线程，避免主线程冻结）
        self.export_full_analysis_background(save_path, analysis_params, cache_path, parent_widget)

    def export_full_analysis_background(self, save_path, analysis_params, cache_path, parent_widget):
        """后台线程重新分析生成完整报告，完成后弹窗通知；界面不锁。"""
        from analysis.analyzer import do_analysis_v2
        from PySide6.QtWidgets import QApplication

        progress_dlg = QProgressDialog("正在后台生成完整报告...", "取消", 0, 100, parent_widget)
        progress_dlg.setWindowTitle("导出中")
        progress_dlg.setWindowModality(Qt.NonModal)  # 不锁界面，可继续操作主表
        progress_dlg.setMinimumDuration(0)
        progress_dlg.show()

        # TODO: 这里需要创建一个后台工作线程，复用 _FullReportWorker
        # 为简化迁移，直接调用 do_analysis_v2 阻塞执行（不完美但可用）
        try:
            do_analysis_v2(
                input_file=analysis_params['input_file'],
                output_dir=None,
                alt_pairs=analysis_params['alt_pairs'],
                progress_callback=lambda step_idx, step_name, percent: (
                    progress_dlg.setValue(percent),
                    progress_dlg.setLabelText(f"{step_name} ({percent}%)"),
                    QApplication.processEvents(),
                )[0],
                cancel_check=lambda *args: (QApplication.processEvents(), progress_dlg.wasCanceled())[1],
                start_date=analysis_params.get('start_date'),
                end_date=analysis_params.get('end_date'),
                material_search=analysis_params.get('material_search'),
                output_path=save_path,
                enable_net_offset=True,
                return_dataframe=False,
                dyn_thresh=analysis_params.get('dyn_thresh'),
            )
            progress_dlg.setValue(100)
            progress_dlg.close()

            # 回存缓存
            if cache_path and not os.path.exists(cache_path):
                try:
                    shutil.copy2(save_path, cache_path)
                except Exception:
                    pass

            self.on_full_report_done(save_path, cache_path, parent_widget)
        except Exception as e:
            traceback.print_exc()
            progress_dlg.close()
            QMessageBox.critical(parent_widget, "错误", f"导出完整报告失败: {e}")
            self.log_message.emit(f"导出完整报告失败: {e}", "error")

    def on_full_report_done(self, save_path, cache_path, parent_widget):
        """后台生成完成：回存缓存 + 弹窗通知（不锁界面）"""
        # TODO: 这里需要从 parent 中获取 heavy_busy 标志并设置
        parent = getattr(self, 'parent', None)
        if parent:
            parent._heavy_busy = False
        progress_dlg = None  # 此处不需要关闭，因为之前已close
        # 回存缓存
        if cache_path and not os.path.exists(cache_path):
            try:
                import shutil
                shutil.copy2(save_path, cache_path)
            except Exception:
                pass
        reply = QMessageBox.question(
            parent_widget, "导出成功",
            f"完整分析报告已生成：\n{save_path}\n\n"
            "包含Sheet:\n"
            "📋 分析说明 · 汇总统计(带预警颜色)\n"
            "完整偏差明细 · 替代料明细 · 无备注预警\n"
            "中间地带明细 · 异常预警 · 偏差金额分析\n"
            "偏差原因汇总 · 偏差原因分析 · 趋势分析\n\n"
            "是否立即打开？"
        )
        if reply == QMessageBox.Yes:
            open_file(save_path)
        self.log_message.emit(f"已导出完整分析报告到 {save_path}", "info")

    def sync_alt_pairs_for_full_report(self):
        """重算净偏差后，把当前替代料配对同步给完整报告并失效旧缓存，
        保证「加料 → 刷新净偏差 → 导出完整报告」三者一致。
        """
        parent = getattr(self, 'parent', None)
        if not parent:
            return
        # 1. 同步最新配对到完整报告所用分析参数（导出读取的就是它）
        if isinstance(parent._analysis_params, dict):
            parent._analysis_params['alt_pairs'] = list(parent.alt_controller.get_pairs())
        # 2. 失效完整报告缓存（否则下次导出直接复制不含新料的旧缓存）
        cp = getattr(parent, '_full_analysis_cache_path', None)
        if cp and os.path.exists(cp):
            try:
                os.remove(cp)
            except OSError:
                pass
        parent._full_analysis_cache_path = None

    def on_export_full_excel_from_mw(self):
        """点击「导出完整Excel」（v43.312 自 MainWindow._on_export_full_excel 迁入）"""
        parent = getattr(self, 'parent', None)
        if parent is None:
            return
        audit_data = parent.view_model.df
        if audit_data is None or audit_data.empty:
            QMessageBox.warning(parent, "提示", "无数据，请先进行分析")
            return

        if parent._heavy_busy:
            QMessageBox.information(parent, "提示", "分析/报告生成进行中，请稍候再导出")
            return

        _ap = getattr(parent, '_analysis_params', None) or {}
        _sd = str(_ap.get('start_date') or '').strip()
        _ed = str(_ap.get('end_date') or '').strip()
        if _sd and _ed:
            _rng = f"{_sd.replace('-', '')}-{_ed.replace('-', '')}"
            default_name = f"ZPP011偏差分析最终版_{_rng}_（{_rng}）.xlsx"
        else:
            default_name = f"ZPP011偏差分析最终版_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        save_path, _ = QFileDialog.getSaveFileName(
            parent, "保存完整Excel文件", default_name, "Excel files (*.xlsx)"
        )
        if not save_path:
            return

        analysis_params = parent._analysis_params
        current_input_file = parent.current_input_file
        cache_path = parent._full_analysis_cache_path

        has_valid_params = (
            analysis_params
            and isinstance(analysis_params, dict)
            and analysis_params.get('input_file')
            and current_input_file
        )

        if has_valid_params:
            reply = QMessageBox.question(
                parent, "导出选项",
                "是否生成完整多Sheet分析报告（含汇总统计、预警颜色等）？\n\n"
                "点击「是」→ 生成完整多Sheet Excel（缓存命中则秒传，否则重新分析）\n"
                "点击「否」→ 仅导出当前表格数据（快速）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.export_full_analysis_inline(
                    save_path, analysis_params, cache_path, parent
                )
                return

        try:
            saved = safe_save(
                parent, save_path,
                lambda p: audit_data.to_excel(p, sheet_name='完整偏差明细', index=False),
                what="表格",
            )
            if not saved:
                parent.log("导出已取消（目标文件被占用）", "warning")
                return
            save_path = saved
            if QMessageBox.question(
                parent, "导出成功", f"文件已导出到：\n{save_path}\n是否打开？"
            ) == QMessageBox.Yes:
                open_file(save_path)
            parent.log(f"已导出完整Excel到 {save_path}", "info")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(parent, "错误", f"导出失败: {e}")
            parent.log(f"导出失败: {e}", "error")

    def recalculate_net_offset(self, silent=False):
        """重算净偏差（v43.312 自 MainWindow._recalculate_net_offset 迁入）"""
        parent = getattr(self, 'parent', None)
        if parent is None:
            return
        df = parent.view_model.df
        if df is None or df.empty:
            if not silent:
                QMessageBox.warning(parent, "提示", "无数据")
            return
        from analysis.net_offset import apply_net_offset
        alt_pairs = parent.alt_controller.get_pairs()
        if not alt_pairs:
            if not silent:
                QMessageBox.information(parent, "提示", "没有替代料配对，已删除所有配对")
            df = df.copy()
            df["净偏差数量"] = df.get("偏差数量", 0)
            df["是否替代料"] = "否"
            # v43.240 修复：净偏差重算不改变被变更检测比对的「实际数量/备注原因/产量」，
            # 但本函数读的是 view_model.df——其 _read 副本未被「变动提醒-全设为已读」更新（仍是 0），
            # 若直接 setDataFrame 会把刚标好的已读(_read=1)覆盖回未读，导致变动提醒又翻回未读。
            # 故重算后从 DB 重新派生 _read/_post_audit_changed，让已读状态跨净偏差重算存活。
            if '_read' in df.columns and 'data_id' in df.columns:
                df = parent.data_service.read_status_service.restore_read_status(df)
            parent._schedule_unread_summary()
            parent.view_model.df = df
            if parent.source_model is not None:
                parent.source_model.setDataFrame(df)
                parent._apply_column_visibility_by_name()
                parent.proxy_model.invalidate()
            parent._on_view_model_data_changed()
            parent._sync_alt_pairs_for_full_report()
            if not silent:
                parent.statusBar().showMessage("净偏差已重置为原始值", 2000)
            return
        try:
            new_df = apply_net_offset(df, alt_pairs, group_key=["订单日期", "流程订单"])
            # v43.240 修复：与空配对分支同理，重算后从 DB 重新对账已读状态，
            # 避免把「变动提醒-全设为已读」标好的 _read=1 覆盖回 0（清空替代料看板→变动提醒又变未读）。
            if '_read' in new_df.columns and 'data_id' in new_df.columns:
                new_df = parent.data_service.read_status_service.restore_read_status(new_df)
            parent._schedule_unread_summary()
            parent.view_model.df = new_df
            if parent.source_model is not None:
                parent.source_model.setDataFrame(new_df)
                parent._apply_column_visibility_by_name()
                parent.proxy_model.invalidate()
            parent._on_view_model_data_changed()
            parent._sync_alt_pairs_for_full_report()
            if not silent:
                parent.statusBar().showMessage("净偏差已重新计算", 2000)
        except Exception as e:
            if not silent:
                QMessageBox.critical(parent, "错误", f"重算净偏差失败: {e}")
            else:
                parent.log(f"重算净偏差失败: {e}", "error")

