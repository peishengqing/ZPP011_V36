# -*- coding: utf-8 -*-
"""
PPT 报告控制器（ARC-003 第八刀，v43.205）

负责：PPT 生成、智能 PPT、归藏报告等所有演示文稿相关的逻辑从 MainWindow 切出，
避免 God Object 持续膨胀。

模式：组合式。本控制器持有 MainWindow 引用（self.mw），方法体从 MainWindow
原样搬迁、逻辑零改动；MainWindow 侧保留同名薄壳转发，保证外部既有调用
签名不变。

import 来源说明：原方法体依赖 main_window.py 顶部的 logging / numpy / Qt /
QMessageBox / QFileDialog 等，本模块自行 import 同名对象，行为完全一致。
"""

import os
from datetime import datetime
from PySide6.QtWidgets import QMessageBox, QFileDialog, QProgressDialog
from PySide6.QtCore import Qt

from gui_pyside6.save_guard import precheck_save_path
from gui_pyside6.workers.report_workers import _PptReportWorker


class PptController:
    """PPT 报告控制器（PPT 生成、智能 PPT、归藏报告）"""

    def __init__(self, mw):
        self.mw = mw
        self._ppt_progress = None
        self._ppt_worker = None

    # ═══════════════ PPT 生成主流程 ═══════════════

    def _generate_ppt_report(self):
        """生成 PPT 偏差分析报告（后台线程，完成后弹窗，界面不冻结）。"""
        if self.mw.view_model.df is None or self.mw.view_model.df.empty:
            QMessageBox.warning(self.mw, "提示", "请先完成分析，暂无数据可生成 PPT")
            return
        default_name = f"ZPP011 偏差分析_{datetime.now():%Y%m%d_%H%M}.pptx"
        default_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'ZPP011 分析报告')
        os.makedirs(default_dir, exist_ok=True)
        save_path, _ = QFileDialog.getSaveFileName(
            self.mw, "生成 PPT 报告", os.path.join(default_dir, default_name),
            "PPT files (*.pptx)",
        )
        if not save_path:
            return
        if not save_path.lower().endswith('.pptx'):
            save_path += '.pptx'
        # PPT 生成较慢且在后台线程落盘，先确认目标文件没被 PowerPoint 占着
        save_path = precheck_save_path(self.mw, save_path, what="PPT 报告")
        if not save_path:
            self.mw.log("PPT 生成已取消（目标文件被占用）", "warning")
            return

        # 进度条（非模态，不锁界面；PPT 生成本身不可中断，故不提供取消按钮）
        self._ppt_progress = QProgressDialog("正在生成 PPT 报告...", None, 0, 100, self.mw)
        self._ppt_progress.setWindowTitle("生成中")
        self._ppt_progress.setWindowModality(Qt.NonModal)
        self._ppt_progress.setMinimumDuration(0)
        self._ppt_progress.setCancelButton(None)
        self._ppt_progress.show()

        src_name = None
        ap = getattr(self.mw, 'analysis_params', None)
        if ap and ap.get('output_path'):
            src_name = os.path.basename(ap['output_path'])
        self._ppt_worker = _PptReportWorker(
            self.mw.view_model.df.copy(), save_path, src_name)
        self._ppt_worker.progress.connect(
            lambda p, s: (self._ppt_progress.setValue(p), self._ppt_progress.setLabelText(s))
        )
        self._ppt_worker._log.connect(lambda m, lvl: self.mw.log(m, lvl))
        self._ppt_worker.finished_ok.connect(self._on_ppt_done)
        self._ppt_worker.failed.connect(self._on_ppt_fail)
        self._ppt_worker.start()

    def _on_ppt_done(self, path):
        """PPT 生成完成回调。"""
        if hasattr(self.mw, '_ppt_progress'):
            self.mw._ppt_progress.setValue(100)
            self.mw._ppt_progress.close()
        if QMessageBox.question(
            self.mw, "生成成功",
            f"PPT 报告已生成：\n{path}\n\n是否立即打开？"
        ) == QMessageBox.Yes:
            self._open_file(path)
        self.mw.log(f"已生成 PPT 报告：{path}", "info")

    def _on_ppt_fail(self, err):
        """PPT 生成失败回调。"""
        if hasattr(self.mw, '_ppt_progress'):
            self.mw._ppt_progress.close()
        QMessageBox.critical(self.mw, "错误", f"生成 PPT 失败：{err}")
        self.mw.log(f"生成 PPT 失败：{err}", "error")

    @staticmethod
    def _open_file(filepath):
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

    # ═══════════════ 智能 PPT ═══════════════

    def _resolve_smart_ppt_excel(self):
        """智能 PPT 取数：优先用最近分析生成的完整报告缓存；没有则返回 None（由控制器弹框手选）。"""
        cp = getattr(self.mw, '_full_analysis_cache_path', None)
        if cp and os.path.exists(cp):
            return cp
        ap = getattr(self.mw, 'analysis_output_path', None)
        if ap and os.path.exists(ap):
            return ap
        return None

    def _generate_smart_ppt_simple(self):
        """智能 PPT(试用) — 分厂版 (9 页)。底层 core/ppt_trae.py（TRAE 版式），需完整分析 Excel。"""
        if self.mw.view_model.df is None or self.mw.view_model.df.empty:
            QMessageBox.warning(self.mw, "提示", "请先完成分析，暂无数据可生成 PPT")
            return
        excel_path = self._resolve_smart_ppt_excel()
        self.mw.export_controller.generate_simple_ppt(
            self.mw.view_model.df, excel_path, None, self.mw, log_cb=self.mw.log)

    def _generate_smart_ppt_pro(self):
        """智能 PPT(试用) — 专业版 (20+页)。底层 advanced_ppt_generator_v2，需完整分析 Excel。"""
        if self.mw.view_model.df is None or self.mw.view_model.df.empty:
            QMessageBox.warning(self.mw, "提示", "请先完成分析，暂无数据可生成 PPT")
            return
        excel_path = self._resolve_smart_ppt_excel()
        self.mw.export_controller.generate_advanced_report(
            self.mw.view_model.df, excel_path, None, self.mw, log_cb=self.mw.log)

    # ═══════════════ 归藏报告 ═══════════════

    def _open_guizang_magazine(self):
        """归藏-Magazine（网页版）— 电子杂志风横滑报告。"""
        self._open_guizang("magazine")

    def _open_guizang_swiss(self):
        """归藏-Swiss（网页版）— 瑞士国际主义风横滑报告。同样为动态注入版。"""
        self._open_guizang("swiss")

    def _open_guizang(self, style):
        """打开归藏网页版报告窗（动态注入：从分析结果 Excel 实时算数渲染）。"""
        try:
            from gui_pyside6.dialogs.guizang_dialog import GuizangDialog
            excel_path = self._resolve_smart_ppt_excel()
            if not excel_path:
                excel_path, _ = QFileDialog.getOpenFileName(
                    self.mw, "请选择分析结果 Excel 文件", "", "Excel files (*.xlsx)"
                )
                if not excel_path:
                    return
            dlg = GuizangDialog(style, excel_path, parent=self.mw, main_window=self.mw)
            dlg.exec()
        except Exception as e:  # noqa: BLE001
            self.mw.log(f"打开归藏报告失败：{e}", "error")
            QMessageBox.critical(self.mw, "打开失败", f"无法打开归藏报告：\n{e}")
