from storage import storage
from analysis.analyzer import do_analysis_v2


class AuditModel:
    """MVP Model 层：封装数据访问、分析调用、数据库操作"""

    def __init__(self):
        # storage 是模块，无需实例化，直接保存引用
        self._storage = storage

    def run_analysis(self, input_file, output_dir, alt_pairs,
                     progress_callback=None, cancel_check=None,
                     start_date=None, end_date=None, material_search=None,
                     output_path=None):
        """委托给 analysis.analyzer.do_analysis_v2"""
        return do_analysis_v2(
            input_file, output_dir, alt_pairs,
            progress_callback, cancel_check,
            start_date, end_date, material_search, output_path
        )

    def save_audit_to_db(self, df, auditor=None, log_cb=None):
        """保存审核记录到数据库（保存前强制备份）"""
        self._storage._backup_db()
        self._storage.save_audit_to_db(df, auditor, log_cb)

    def restore_audit_from_db(self, df, log_cb=None):
        """从数据库恢复审核记录"""
        return self._storage.restore_audit_from_db(df, log_cb)

    # ---- 以下方法本阶段暂留空，后续阶段实现 ----
    def load_analysis_result(self, file_path):
        """加载分析结果文件（阶段2实现）"""
        pass

    def write_audit_back_to_excel(self, src_path, audit_data):
        """将审核结果写回 Excel（阶段2实现）"""
        pass
