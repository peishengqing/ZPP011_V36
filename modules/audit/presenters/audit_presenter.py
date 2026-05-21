# modules/audit/presenters/audit_presenter.py
import threading
from typing import Any, Dict, Optional, List


class AuditPresenter:
    """MVP Presenter 层：业务逻辑、协调 Model 和 View"""

    def __init__(self, model: 'AuditModel', view: 'AuditViewBridge'):
        self.model = model
        self.view = view  # view 是 events.py 中提供的一组回调接口（非完整 View 对象）
        self.running = False
        self.cancel_req = False
        # 其他状态可迁移至此
        self._ai_cancel_flag = None
        self.is_auditing = False

    # ---------- 业务逻辑方法（从 events.py 迁移）----------
    def start_analysis(self, input_file: str, alt_pairs: list,
                     start_date: str = None, end_date: str = None,
                     material_search: str = None,
                     progress_callback=None, cancel_check=None):
        """开始分析（同步，在 worker 线程中调用）
        
        Args:
            input_file: 输入文件路径
            alt_pairs: 替代配对列表
            start_date: 开始日期
            end_date: 结束日期
            material_search: 物料搜索关键词
            progress_callback: 进度回调函数
            cancel_check: 取消检查函数
        
        Returns:
            output_path: 分析输出目录
        
        Raises:
            Exception: 分析失败
        """
        self.view.log("开始分析...", "info")
        self.running = True
        self.cancel_req = False
        
        import tempfile
        import traceback
        import os
        
        _log = os.path.join(os.environ.get('TEMP', '.'), 'zpp011_debug.log')
        
        try:
            with open(_log, 'a', encoding='utf-8') as _f:
                _f.write(f"\n=== {__import__('datetime').datetime.now()} 开始分析 ===\n")
                _f.write(f"input_file={input_file}\n")
            
            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix="zpp011_analysis_")
            self.view.log(f"临时目录: {temp_dir}", "debug")
            
            # 调用 Model 层进行分析
            output_path = self.model.run_analysis(
                input_file=input_file,
                output_dir=temp_dir,
                alt_pairs=alt_pairs,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
                start_date=start_date,
                end_date=end_date,
                material_search=material_search,
            )
            
            with open(_log, 'a', encoding='utf-8') as _f:
                _f.write(f"{__import__('datetime').datetime.now()} 分析完成\n")
            
            self.view.log("分析完成", "success")
            return output_path
        
        except KeyboardInterrupt:
            with open(_log, 'a', encoding='utf-8') as _f:
                _f.write(f"{__import__('datetime').datetime.now()} KeyboardInterrupt\n")
            
            self.view.log("用户取消", "warn")
            self.cancel_req = True
            raise
        
        except Exception as e:
            with open(_log, 'a', encoding='utf-8') as _f:
                _f.write(f"{__import__('datetime').datetime.now()} Exception: {e}\n")
                _f.write(traceback.format_exc() + "\n")
            
            self.view.log(f"分析失败: {e}", "error")
            raise
        
        finally:
            self.running = False

    def request_cancel_analysis(self):
        """请求取消分析"""
        self.cancel_req = True
        self.view.log("取消请求已发送", "warn")

    def filter_audit_data(self, filters: Dict[str, Any]) -> 'pd.DataFrame':
        """筛选审核数据（纯业务逻辑，不操作UI）

        Args:
            filters: dict with keys: stat, color, search, order_date, columns,
                     factory, admin, name, status, dev_rate, is_alt, remark
        Returns:
            Filtered DataFrame
        """
        import pandas as pd
        audit_data = self.view.get_audit_data()
        if audit_data is None or len(audit_data) == 0:
            return audit_data

        df = audit_data.copy()

        # 1) Stat card filter
        stat = filters.get('stat')
        if stat == 'big_dev':
            rc = next((c for c in ['偏差率(%)', '偏差率'] if c in df.columns), None)
            if rc:
                df = df[pd.to_numeric(df[rc], errors='coerce').abs() > 10]
        elif stat == 'no_note':
            rc = next((c for c in ['备注原因', '备注'] if c in df.columns), '备注原因')
            df = df[df[rc].isna() | (df[rc].astype(str).str.strip() == '')]
        elif stat == 'approved':
            rc = next((c for c in ['备注原因', '备注'] if c in df.columns), '备注原因')
            df = df[df[rc].notna() & (df[rc].astype(str).str.strip() != '')]

        # 2) Color filter
        color = filters.get('color')
        if color and color != '全部' and '_priority_label' in df.columns:
            cmap = {'红': '红', '橙': '橙', '黄': '黄', '绿': '绿'}
            df = df[df['_priority_label'] == cmap.get(color, color)]

        # 3) Full-text search
        search = filters.get('search', '').strip()
        if search:
            mask = pd.Series(False, index=df.index)
            for col in df.columns:
                mask |= df[col].astype(str).str.contains(search, case=False, na=False)
            df = df[mask]

        # 4) Date range
        od = filters.get('order_date')
        if od and '订单日期' in df.columns:
            s, e = od
            if s:
                df = df[df['订单日期'].astype(str).str[:10] >= s]
            if e:
                df = df[df['订单日期'].astype(str).str[:10] <= e]

        # 5) Field filters
        col_map = filters.get('columns', {})
        for key, col_name in col_map.items():
            val = filters.get(key)
            if not val or val == '全部' or col_name is None:
                continue
            if key == 'is_alt':
                alt_pairs = self.view.get_alt_pairs()
                descs = set()
                for a, b in alt_pairs:
                    for item in (a, b):
                        if isinstance(item, (list, tuple)) and len(item) >= 3:
                            d = str(item[2]).strip()
                        elif isinstance(item, (list, tuple)):
                            d = str(item[1]).strip() if len(item) > 1 and item[1] else ''
                        else:
                            d = str(item).strip() if item else ''
                        if d and d != 'None':
                            descs.add(d)
                dc = next((c for c in ['组件物料描述', '物料名称'] if c in df.columns), None)
                if dc:
                    if val == '是':
                        df = df[df[dc].astype(str).str.strip().isin(descs)]
                    elif val == '否':
                        df = df[~df[dc].astype(str).str.strip().isin(descs)]
            elif key == 'dev_rate':
                rv = pd.to_numeric(df[col_name], errors='coerce')
                ops = {'>10%': rv > 10, '>20%': rv > 20, '>30%': rv > 30,
                       '绝对值>10%': rv.abs() > 10, '<-10%': rv < -10, '<-20%': rv < -20}
                if val in ops:
                    df = df[ops[val]]
            elif key == 'remark':
                # 备注筛选：动态定位列名，标准化空值后匹配
                remark_col = next(
                    (c for c in ['备注原因', '备注', 'remark'] if c in df.columns), None
                )
                if remark_col is not None:
                    temp = df[remark_col].fillna('').astype(str).str.strip().replace('nan', '')
                    if val == '为空':
                        df = df[temp == '']
                    elif val == '不为空':
                        df = df[temp != '']
                    else:
                        # 精确文本匹配
                        df = df[temp == val]
            else:
                if col_name in df.columns:
                    df = df[df[col_name].astype(str).str.contains(val, case=False, na=False)]


        # 6) AI审核结果筛选（_on_filter_changed 迁移）
        ai_result = filters.get('ai_result')
        if ai_result and ai_result != '全部':
            remark_src_col = next((c for c in ['审核来源', 'audit_source'] if c in df.columns), None)
            if remark_src_col:
                if ai_result == '合格':
                    df = df[df[remark_src_col] == '审核合格']
                elif ai_result == '需改进':
                    df = df[df[remark_src_col] == '审核待改进']
                elif ai_result == 'AI建议':
                    df = df[df[remark_src_col].str.startswith('AI建议', na=False)]
                elif ai_result == '未处理':
                    ai_sources = {'审核合格', '审核待改进', 'AI建议', 'AI建议（小偏差）'}
                    df = df[~(df[remark_src_col].isin(ai_sources) | df[remark_src_col].isna())]


        return df

    def run_ai_audit(self):
        """AI审核：启动异步审核流程（从 events.py 迁移）
        
        调用前由 View 层检查前置条件（is_auditing, audit_data 是否为空）
        返回 (audit_indices, df_to_audit) 供 View 层启动 task_manager
        """
        import pandas as pd
        
        audit_data = self.view.get_audit_data()
        alt_pairs = self.view.get_alt_pairs()
        
        # 确保必要列存在
        for col in ['audit_result', 'AI建议', '备注来源']:
            if col not in audit_data.columns:
                audit_data[col] = ''
        
        # 构建替代料名称集合
        alt_all_descs = set()
        for a, b in alt_pairs:
            for item in (a, b):
                if item:
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        desc = str(item[2]).strip()
                    elif isinstance(item, (list, tuple)) and len(item) == 2:
                        desc = str(item[1]).strip() if item[1] else str(item[0]).strip()
                    else:
                        desc = str(item).strip()
                    if desc and desc != 'None':
                        alt_all_descs.add(desc)
        
        # 自动填充条件
        is_auto_fill = (
            audit_data['组件物料描述'].astype(str).str.contains('透明胶', na=False) |
            audit_data['组件物料号'].astype(str).str.startswith('600')
        )
        is_alt = audit_data['组件物料描述'].astype(str).str.strip().isin(alt_all_descs)
        exclude_sources = ['人工填写', '自动填充', '替代料', 'AI审核合格', 'AI审核待改进', 'AI生成']
        is_already_processed = audit_data['备注来源'].isin(exclude_sources)
        
        to_audit_mask = (
            (audit_data['audit_result'].isna() | (audit_data['audit_result'] == '')) &
            (~is_auto_fill) &
            (~is_alt) &
            (~is_already_processed)
        )
        
        audit_indices = audit_data[to_audit_mask].index.tolist()
        return audit_indices
    
    def ai_audit_worker(self, audit_indices, df_to_audit, ai_client, progress_callback=None):
        """AI审核工作线程函数（同步）
        
        Args:
            audit_indices: 需要审核的行索引列表
            df_to_audit: 审核数据的 DataFrame
            ai_client: AI客户端实例
            progress_callback: 进度回调
        
        Returns:
            list of dict: 审核结果列表
        """
        import pandas as pd
        
        total = len(audit_indices)
        popup_rows = []
        remark_col = next((c for c in ['备注原因', '备注'] if c in df_to_audit.columns), None)
        name_col = next((c for c in ['组件物料描述', '物料名称'] if c in df_to_audit.columns), None)
        rate_col = next((c for c in ['偏差率(%)', '偏差率'] if c in df_to_audit.columns), None)
        
        for seq, idx in enumerate(audit_indices):
            if self._ai_cancel_flag and self._ai_cancel_flag.is_set():
                raise InterruptedError("用户取消了AI审核")
            
            row = df_to_audit.loc[idx]
            remark = row[remark_col] if remark_col else ''
            dev_rate_raw = row[rate_col] if rate_col else 0
            try:
                dev_rate = float(dev_rate_raw or 0)
            except:
                dev_rate = 0.0
            material_desc = str(row[name_col]) if name_col else ''
            
            try:
                result = ai_client.audit(remark, dev_rate)
                audit_result = result.get('result', '需补备注')
                ai_suggestion = result.get('suggestion', '')
            except Exception as ex:
                audit_result = '审核失败'
                ai_suggestion = str(ex)
            
            popup_rows.append({
                'idx': idx,
                '物料': material_desc,
                '偏差率': f"{dev_rate:.1f}%",
                '原备注': str(remark) if not pd.isna(remark) else '',
                'AI建议': ai_suggestion,
                '审核结果': audit_result,
                '_audit_result': audit_result,
                '_ai_suggestion': ai_suggestion,
            })
            
            if progress_callback:
                progress_callback(int((seq + 1) / total * 100))
        
        return popup_rows
    
    def cancel_ai_audit(self):
        """取消当前 AI 审核"""
        if self._ai_cancel_flag is not None:
            self._ai_cancel_flag.set()

    def save_audit_back(self, auditor: str = None):
        """保存审核结果到 Excel 和数据库"""
        self.view.log("保存审核结果...", "info")
        
        # 从 View 获取当前审核数据
        save_df = self.view.get_audit_data().copy()
        
        # 确保必要列存在
        if '审核人' not in save_df.columns and '审核人员' in save_df.columns:
            save_df['审核人'] = save_df['审核人员']
        if '审核意见' not in save_df.columns:
            save_df['审核意见'] = save_df.get('审核意见', '')
        
        try:
            # 调用 Model 层保存到数据库
            self.model.save_audit_to_db(save_df, auditor=auditor, log_cb=self.view.log)
            self.view.log("审核结果已保存到数据库", "success")
            
            # 同时写回 Excel（如果需要）
            output_path = self.view.get_output_path()
            if output_path:
                self.model.write_audit_back_to_excel(save_df, output_path)
                self.view.log("审核结果已写回 Excel", "success")
        
        except Exception as e:
            self.view.log(f"保存失败: {e}", "error")
            raise
    def auto_close(self, df_to_audit, rule_engine_snapshot, progress_callback, cancel_flag):
        """自动结案核心逻辑（委托 AutoCloser.process）"""
        from core.auto_closer import AutoCloser
        return AutoCloser.process(
            df_to_audit, rule_engine_snapshot, progress_callback, cancel_flag
        )

    def generate_ppt(self, excel_path: str, output_path: str):
        """生成PPT报告

        Args:
            excel_path: 分析结果Excel路径
            output_path: PPT输出路径
        """
        self.view.log("正在生成PPT...", "info")
        try:
            from ppt_generator import generate_ppt as _gen_ppt
            _gen_ppt(excel_path, output_path)
            self.view.log("PPT生成完成", "success")
            self.view.show_info("完成", f"PPT已生成: {output_path}")
            return True
        except Exception as e:
            self.view.log(f"PPT生成失败: {e}", "error")
            self.view.show_error("错误", f"PPT生成失败: {e}")
            return False

    def generate_excel(self, output_path: str):
        """生成审核Excel表格

        Args:
            output_path: 输出路径
        """
        self.view.log("正在生成审核Excel...", "info")
        try:
            audit_data = self.view.get_audit_data()
            if audit_data is None or audit_data.empty:
                self.view.show_warning("警告", "没有审核数据可导出")
                return False

            from utils.helpers import standardize_remark
            import openpyxl

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "审核记录"

            # 写入表头
            headers = [c for c in audit_data.columns]
            ws.append(headers)

            # 写入数据
            for _, row in audit_data.iterrows():
                ws.append([row.get(c, '') for c in headers])

            wb.save(output_path)
            self.view.log(f"审核Excel已保存: {output_path}", "success")
            self.view.show_info("完成", f"审核Excel已生成: {output_path}")
            return True
        except Exception as e:
            self.view.log(f"Excel生成失败: {e}", "error")
            self.view.show_error("错误", f"Excel生成失败: {e}")
            return False

    # ... 其他业务逻辑

    def load_audit_data(self, audit_data: 'pd.DataFrame'):
        """从数据库恢复审核数据
        
        Args:
            audit_data: 当前审核数据 DataFrame（用于回填）
        
        Returns:
            restored_count: 恢复的记录数
        """
        self.view.log("从数据库恢复审核数据...", "info")
        
        try:
            # 调用 Model 层恢复数据
            restored_count = self.model.restore_audit_from_db(audit_data, log_cb=self.view.log)
            self.view.log(f"已恢复 {restored_count} 条审核记录", "success")
            return restored_count
        
        except Exception as e:
            self.view.log(f"恢复失败: {e}", "error")
            raise
