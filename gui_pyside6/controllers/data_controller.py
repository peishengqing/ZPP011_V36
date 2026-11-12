# -*- coding: utf-8 -*-
"""
数据控制器（ARC-003 新增）
负责：文件导入/导出、数据加载、工厂切换等数据相关操作
"""

import os
import pandas as pd
from PySide6.QtWidgets import QFileDialog, QMessageBox
from gui_pyside6.workers.report_workers import _FileReadWorker
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel

class DataController:
    """数据操作控制器"""

    def __init__(self, mw):
        self.mw = mw
        self._file_worker = None
        self._cached_input_df = None
        self._cached_input_mtime = None
        self._current_input_file = None
        self._monitor_dir = r"E:\ZPP011 导出文件原数据"
        self._monitor_enabled = True
        self._monitor_timer = None
        self._monitor_last_size = {}
        self._monitor_loaded = set()
        self._monitor_pending = set()
        self._monitor_current_key = None
        self._monitor_auto_loading = False
        self._monitor_delay_ms = 5000
        self._monitor_busy_retry = 6
        self._monitor_busy_interval = 3000
        self._monitor_pending = set()
        self._monitor_current_key = None
        self._monitor_auto_loading = False
        self._expired_q_cache = {}
        self._expired_q_notified = set()

    def select_input_file(self, default_dir=r"E:\ZPP011 导出文件原数据"):
        """选择输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.mw, "选择 SAP Excel 文件", default_dir, "Excel files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        self._current_input_file = os.path.normpath(file_path)
        self.mw.input_file_edit.setText(self._current_input_file)
        self.mw.input_file_edit.setToolTip(file_path)

        if hasattr(self.mw, 'preview_label'):
            self.mw.preview_label.setText("正在读取文件…")

        self._file_worker = _FileReadWorker(file_path)
        self._file_worker.loaded.connect(lambda df, fp=file_path: self._on_file_loaded(df, fp))
        self._file_worker.failed.connect(self._on_file_failed)
        self._file_worker.start()

    def _on_file_loaded(self, df, file_path):
        """文件加载成功回调"""
        try:
            # 清零已读计数
            self.mw._auto_read_count = 0
            self.mw._manual_read_count = 0
            self.mw._update_read_counter()

            # 分析时间标签重置
            if hasattr(self.mw, "_analysis_time_label"):
                self.mw._analysis_time_label.setText("分析：—")

            # 缓存 DataFrame 和文件签名
            self._cached_input_df = df
            self._cached_input_mtime = self._file_mtime_signature(file_path)

            # 持久化物料名称
            self._persist_material_names(df)

            # 更新预览统计
            self._set_preview(self._format_preview_stats(df))
        except Exception as e:
            self._set_preview(f"读取失败：{e}")
        finally:
            if self._file_worker is not None:
                self._file_worker.deleteLater()
                self._file_worker = None

    def _set_preview(self, text):
        """写「数据预览」文字，并顺手把左栏那一项展开。

        只在统计真正落地（或明确读失败）那一刻展开；「正在读取文件…」那种占位
        文案走 preview_label.setText 原路，不动面板——否则选完文件先弹一块空壳。
        """
        label = getattr(self.mw, 'preview_label', None)
        if label is None:
            return
        label.setText(text)
        comp = getattr(self.mw, 'left_panel_component', None)
        if comp is not None:
            comp.open_data_preview()

    def _file_mtime_signature(self, path):
        """取源文件的「修改时间 + 大小」作为变更指纹"""
        if not path:
            return None
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except (OSError, ValueError):
            return None

    def _persist_material_names(self, df):
        """从 DataFrame 中保存物料编码 → 名称映射"""
        code_key = next((c for c in ('物料编码', '组件物料号', '物料号') if c in df.columns), None)
        name_key = next((c for c in ('物料名称', '组件物料描述', '物料描述') if c in df.columns), None)
        if not code_key or not name_key:
            return

        from gui_pyside6.dialogs.material_profile_dialog import normalize_text
        mapping = {}
        for code, nm in zip(df[code_key], df[name_key]):
            c = normalize_text(code)
            n = normalize_text(nm)
            if c and n:
                mapping[c] = n

        if mapping:
            from core.read_status import upsert_material_names
            upsert_material_names(mapping)

    def _format_preview_stats(self, df):
        """生成数据预览统计文字"""
        factory_col = None
        for cand in ['工厂名称', '工厂', 'plant']:
            if cand in df.columns:
                factory_col = cand
                break

        total_cols = len(df.columns)
        hidden_count = sum(1 for c in df.columns if c in self.mw._hidden_column_names)
        visible_cols = total_cols - hidden_count

        # 剔除 0 宽列
        model = self.mw.table_view.model() if hasattr(self.mw, 'table_view') else None
        if model is not None:
            try:
                for col in range(model.columnCount()):
                    if self.mw.table_view.columnWidth(col) <= 1:
                        visible_cols -= 1
            except Exception:
                pass

        lines = [f"总行数：{len(df)} 行"]
        if factory_col:
            food = int((df[factory_col].astype(str).str.contains('食品')).sum())
            drink = int((df[factory_col].astype(str).str.contains('饮料')).sum())
            other = len(df) - food - drink
            lines.append(f"食品厂：{food} 行")
            lines.append(f"饮料厂：{drink} 行")
            if other > 0:
                lines.append(f"其他：{other} 行")
        lines.append(f"列数：{visible_cols} 列")
        return "\n".join(lines)

    def _on_file_failed(self, msg):
        """文件加载失败回调"""
        self._set_preview(f"读取失败：{msg}")
        if self._file_worker is not None:
            self._file_worker.deleteLater()
            self._file_worker = None

    def select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self.mw, "选择输出目录")
        if dir_path:
            self.mw.output_dir_edit.setText(dir_path)
            self.mw.output_dir_edit.setToolTip(dir_path)

    def open_output_dir(self):
        """打开输出目录"""
        dir_path = self.mw.output_dir_edit.text()
        if not dir_path:
            dir_path = os.path.expanduser("~/Documents/ZPP011 分析报告")
        if os.path.exists(dir_path):
            from gui_pyside6.utils.file_launcher import open_path
            open_path(dir_path)
        else:
            QMessageBox.warning(self.mw, "提示", "输出目录不存在")

    def drop_stale_input_cache(self):
        """检查输入缓存是否过期，若过期则丢弃并返回 True"""
        if self._cached_input_df is None:
            return False
        cur = self._file_mtime_signature(self._current_input_file)
        old = self._cached_input_mtime
        if old is not None and cur is not None and cur == old:
            return False
        self._cached_input_df = None
        self._cached_input_mtime = None
        try:
            self.mw.log("[分析] 源文件已修改，丢弃旧缓存并重新读取", "info")
        except Exception:
            pass
        return True

    def _on_factory_changed(self, factory_name):
        """工厂切换：应用选中工厂的数据到主表（v43.316 真身自 MainWindow 迁入）。"""
        if not factory_name:
            return
        if factory_name == '全部':
            # 显示全部工厂数据
            all_data = self.mw.analysis_controller.factory_data.get('全部')
            if all_data is None:
                # 合并所有工厂数据
                all_parts = []
                for f, g in self.mw.analysis_controller.factory_data.items():
                    all_parts.append(g)
                if all_parts:
                    all_data = pd.concat(all_parts, ignore_index=True)
                    self.mw.analysis_controller.factory_data['全部'] = all_data
            df = all_data
        else:
            df = self.mw.analysis_controller.factory_data.get(factory_name)
        if df is not None:
            # 后台线程已预处理过（带 _read 列）→ 直接复用，避免主线程再跑 31s 卡顿；
            # 仅在拿到原始 dev_df（无 _read 列）时才在主线程预处理（兜底）。
            if '_read' in df.columns:
                processed_df = df
            else:
                processed_df = self.mw.data_service.preprocess_audit_data(df)
            if self.mw.source_model is None:
                self.mw.source_model = DataFrameModel()
                self.mw.proxy_model = AuditProxyModel()
                self.mw.proxy_model.setDynamicSortFilter(False)  # 同上，关闭重过滤风暴
                self.mw.proxy_model.setSourceModel(self.mw.source_model)
                self.mw.table_view.setModel(self.mw.proxy_model)
                self.mw.proxy_model.layoutChanged.connect(self.mw._update_mark_stats)
                self.mw.source_model.dataChanged.connect(self.mw._update_mark_stats)
                self.mw.source_model.dataRefreshed.connect(self.mw._update_mark_stats)
                self.mw.source_model.modelReset.connect(self.mw._update_mark_stats)
            try:
                self.mw.source_model.setDataFrame(processed_df)
            except Exception as _e:
                import traceback as _tb
                _tb.print_exc()
                raise
            self.mw._apply_column_visibility_by_name()
            self.mw._schedule_unread_summary()
            self.mw.view_model.df = processed_df
            self.mw._update_summary()
            self.mw.filter_panel.update_options(processed_df)
            self.mw.statusBar().showMessage(f"已切换到工厂：{factory_name}", 2000)
        else:
            self.mw.statusBar().showMessage(f"工厂 {factory_name} 数据为空", 2000)

    def on_data_changed(self, df: pd.DataFrame) -> None:
        """更新显示的数据"""
        if df is None:
            self.mw.data_view_model = None
            self.mw.data_view_model.data_loaded.emit()  # 刷新视图
            return

        # 应用 DataViewModel 转换
        from gui_pyside6.models.data_frame_model import DataFrameModel
        if not hasattr(self.mw, 'data_view_model') or self.mw.data_view_model is None:
            self.mw.data_view_model = DataFrameModel()

        self.mw.data_view_model.setDataFrame(df)
        self.mw.table_view.setModel(self.mw.data_view_model)

        # 更新概览 KPI 带（v43.349 修正：StatsCardsWidget 的方法叫 refresh，
        # 这里写的是 update_stats —— 每次应用筛选都会在控制台抛一条
        # AttributeError，带上的数字从来不跟着变）
        if hasattr(self.mw, 'stats_cards'):
            self.mw.stats_cards.refresh(df)

    def get_original_data(self) -> pd.DataFrame:
        """获取原始数据（未筛选）"""
        if self._cached_input_df is not None:
            return self._cached_input_df
        return None

    # Additional data-related methods...

