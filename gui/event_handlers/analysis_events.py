# -*- coding: utf-8 -*-
"""数据分析、加载、进度控制事件"""

import tkinter as tk
from tkinter import messagebox
import os, threading, time
import pandas as pd
from widgets import C, STEPS
from core.decorators import with_feedback
from analysis.analyzer import do_analysis_v2
from openpyxl import load_workbook
from storage import storage
import traceback
import calendar


class AnalysisEvents:
    """数据分析、加载、进度控制事件"""
    def start_analysis(self):





        try:
            if self.running:





                return











            path = self.input_file.get()











            if not path or not os.path.exists(path):





                messagebox.showerror("错误", "请先选择有效的输入文件！")











                return











            self.running = True











            self.cancel_req = False











            self.run_btn.configure(state="disabled", text="⏳ 分析中...")











            self.cancel_btn.configure(state="normal")











            self.open_btn.configure(state="disabled")











            self.status_lbl.configure(text="分析中...", fg=C['warn'])











            self.log_text.configure(state="normal")











            self.log_text.delete("1.0", "end")











            self.log_text.configure(state="disabled")











            self.progress_var.set(0)











            self._current_step = -1











            for i in self.step_frames:





                self._set_step(i, False)











            self.start_time = time.time()











            self._update_timer()











            t = threading.Thread(target=self._analysis_thread, daemon=True)












        except Exception as e:
            import traceback
            traceback.print_exc()
            from tkinter import messagebox
            messagebox.showerror("错误", f"分析启动失败: {e}")
            self.running = False
            try:
                self.run_btn.configure(state="normal", text="▶  开始分析")
            except:
                pass
        t.start()

















    def _analysis_thread(self):





        """分析线程（委托给 Presenter）"""





        try:





            self.output_path = self.audit_presenter.start_analysis(





                input_file=self.input_file.get(),





                alt_pairs=self.alt_pairs,





                start_date=self.start_date.get() or None,





                end_date=self.end_date.get() or None,





                material_search=self.material_search.get() or None,





                progress_callback=self._on_progress,





                cancel_check=lambda: self.cancel_req,





            )





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), self._on_done)





        except KeyboardInterrupt:





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), self._on_cancel)





        except Exception as e:





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), lambda e=e: self._on_error(str(e)))
            import traceback
            traceback.print_exc()





        except BaseException as e:





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), lambda e=e: self._on_error(f"BaseException: {e}"))





    def _on_progress(self, step_idx, step_name, percent):





        if self.cancel_req:





            return











        self._current_step = step_idx











        import time as _t











        now = _t.strftime("%H:%M:%S")











        def update():





            self.progress_var.set(percent)





            self.progress_lbl.configure(text=f"{step_name}  {percent:.0f}%", fg=C['accent'])





            self._set_step(step_idx)





            self.log(f"[{now}] [{step_idx + 1}/{len(STEPS)}] {step_name} {percent:.0f}%", "step")





            self.root.update_idletasks()





        self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), update)

















    def _update_timer(self):





        if not self.running or not self.start_time:





            return











        elapsed = int(time.time() - self.start_time)











        m, s = elapsed // 60, elapsed % 60











        prog = self.progress_var.get()











        if prog > 5:





            total = int(elapsed / (prog / 100))











            rem = max(0, total - elapsed)











            rm, rs = rem // 60, rem % 60











            self.timer_lbl.configure(





                text=f"⏱ {m:02d}:{s:02d}  |  剩余 ~{rm:02d}:{rs:02d}",





                fg=C['warn'])











        else:





            self.timer_lbl.configure(





                text=f"⏱ {m:02d}:{s:02d}",





                fg=C['text_dim'])











        self.timer_id = self.root.after(self.config.get('analysis.cleanup_delay_ms', 1000), self._update_timer)

















    def request_cancel(self):





        if self.running:





            self.cancel_req = True











            self.cancel_btn.configure(state="disabled", text="取消中...")











            self.log("⚠ 用户请求取消...", "warn")

















    def _on_done(self):





        self.running = False





        self.log(f"🔍 _on_done: output_path = {getattr(self, 'output_path', 'NOT_SET')}", "info")











        # 如果 output_path 为 None，尝试自动查找最新的输出文件





        if not self.output_path:





            try:





                import glob as _glob





                out_dir = self.output_dir.get()





                if not out_dir or not os.path.isdir(out_dir):





                    out_dir = os.path.dirname(self.input_file.get()) if self.input_file.get() else os.path.expanduser('~/Desktop')





                pattern = os.path.join(out_dir, 'ZPP011偏差分析最终版_*.xlsx')





                files = _glob.glob(pattern)





                if files:





                    latest_file = max(files, key=os.path.getmtime)





                    self.output_path = latest_file





                    self.log(f"🔍 自动找到输出文件：{os.path.basename(latest_file)}", "info")





            except Exception as _e:





                self.log(f"🔍 自动查找输出文件失败：{_e}", "warn")











        if self.timer_id:





            self.root.after_cancel(self.timer_id)











        total = int(time.time() - self.start_time)











        m, s = total // 60, total % 60











        self.timer_lbl.configure(text=f"✅ {m:02d}:{s:02d} 完成", fg=C['green'])











        self.run_btn.configure(state="normal", text="▶ 重新分析")











        self.cancel_btn.configure(state="disabled")











        self.open_btn.configure(state="normal")











        self.progress_var.set(100)











        self.progress_lbl.configure(text="✅ 完成 (100%)", fg=C['green'])











        _basename = os.path.basename(self.output_path) if self.output_path else '未知文件'





        self.status_lbl.configure(





            text=f"完成 — {_basename}",





            fg=C['green'])











        for i in self.step_frames:





            self._set_step(i, True)











        self.log(f"\n✅ 分析完成！总用时 {m:02d}:{s:02d}", "success")











        self.status_lbl.configure(text="完成 — 数据已就绪，可加载审核", fg=C['green'])











        # ✅ 新增：自动加载审核数据，联动统计卡片（从分析结果文件加载）





        self._analysis_output_path = self.output_path  # 保存路径供加载使用





        self.log("🔄 准备加载审核数据...", "info")





        self.root.after(self.config.get('analysis.cleanup_delay_ms', 100), lambda: self._load_audit_data_from_output(self._analysis_output_path))





        self.root.after(self.config.get('analysis.cleanup_delay_ms', 200), self._run_pre_check)











        # 加载完成后删除自动生成的Excel（用户需要时可手动点击"生成Excel"按钮）





        self.root.after(self.config.get('analysis.cleanup_delay_ms', 500), self._cleanup_auto_excel)











        # ✅ 启用"加载审核数据"按钮，让用户手动加载





        if hasattr(self, 'load_audit_btn'):





            self.load_audit_btn.configure(state="normal")





            self.log("✅ 已启用「加载审核数据」按钮", "info")











    def _cleanup_auto_excel(self):





        """删除分析自动生成的Excel文件，用户需要时可手动生成"""





        try:





            if self._analysis_output_path and os.path.exists(self._analysis_output_path):





                fname = os.path.basename(self._analysis_output_path)





                os.remove(self._analysis_output_path)





                self.log(f"🗑️ 已清理自动生成文件: {fname}（需要时可点击「生成Excel」按钮）", "info")





                self._analysis_output_path = None





        except Exception as e:





            self.log(f"清理文件失败: {e}", "warn")

















    def _on_cancel(self):





        self.running = False





        if self.timer_id:





            self.root.after_cancel(self.timer_id)





        self.run_btn.configure(state="normal", text="▶ 开始分析")





        self.cancel_btn.configure(state="disabled")





        self.status_lbl.configure(text="已取消", fg=C['warn'])





        self.log("\n⚠ 分析已取消", "warn")

















    def _on_error(self, msg):





        self.running = False





        if self.timer_id:





            self.root.after_cancel(self.timer_id)





        self.run_btn.configure(state="normal", text="▶ 开始分析")





        self.cancel_btn.configure(state="disabled")





        self.status_lbl.configure(text="出错", fg=C['danger'])





        self.log(f"\n❌ 错误：{msg}", "error")





        messagebox.showerror("分析出错", msg)

















    @with_feedback("数据加载成功", "数据加载失败")





    def _load_audit_data(self):





        path = self.input_file.get()





        if not path or not os.path.exists(path):





            messagebox.showwarning("提示", "请先选择输入文件")





            return





        try:





            df = pd.read_excel(path, sheet_name='Data')





            df['偏差率(%)'] = pd.to_numeric(df['偏差率(%)'], errors='coerce').fillna(0)





            # 用 openpyxl 读取真实 Excel 行号（避免 pandas 跳过空行导致偏移）





            try:





                from openpyxl import load_workbook





                _wb2 = load_workbook(path, read_only=True, data_only=True)





                _ws2 = _wb2['Data']





                _real_rows2 = []





                _rn2 = 0





                for _row2 in _ws2:





                    _rn2 += 1





                    if _rn2 == 1:





                        continue





                    _real_rows2.append(_rn2)





                _wb2.close()





                if len(_real_rows2) == len(df):





                    df['excel_row'] = _real_rows2





                else:





                    df['excel_row'] = df.index + 2





            except Exception:





                df['excel_row'] = df.index + 2





            





            # 日期范围过滤（如果用户输入了日期）





            start_date_str = self.start_date.get().strip()





            end_date_str = self.end_date.get().strip()





            





            if start_date_str or end_date_str:





                if '订单开始日期' in df.columns:





                    df['订单开始日期'] = pd.to_datetime(df['订单开始日期'], errors='coerce')





                    if start_date_str:





                        try:





                            start_dt = pd.to_datetime(start_date_str)





                            df = df[df['订单开始日期'] >= start_dt]





                            self.log(f"已按开始日期 {start_date_str} 过滤", "info")





                        except:





                            pass





                    if end_date_str:





                        try:





                            end_dt = pd.to_datetime(end_date_str)





                            df = df[df['订单开始日期'] <= end_dt]





                            self.log(f"已按结束日期 {end_date_str} 过滤", "info")





                        except:





                            pass





            





            total = len(df)





            high_dev = df[df['偏差率(%)'].abs() > self.config.get('audit.high_deviation_threshold', 10)]





            need_note = high_dev[high_dev['备注原因'].isna()]





            ok_note = high_dev[high_dev['备注原因'].notna()]





            





            # ── P1#11：计算偏差金额 ─────────────────────────────





            df['数量-定额'] = pd.to_numeric(df['数量-定额'], errors='coerce').fillna(0)





            df['数量-实际'] = pd.to_numeric(df['数量-实际'], errors='coerce').fillna(0)





            df['金额-实际(含税)'] = pd.to_numeric(df['金额-实际(含税)'], errors='coerce').fillna(0)





            # 计算含税单价（避开除以0）





            df['_unit_price'] = 0.0





            mask = df['数量-实际'] != 0





            df.loc[mask, '_unit_price'] = df.loc[mask, '金额-实际(含税)'] / df.loc[mask, '数量-实际']





            # 偏差金额 = (实际 - 定额) × 含税单价





            df['偏差金额'] = ((df['数量-实际'] - df['数量-定额']) * df['_unit_price']).round(2)





            # 删除临时列





            df.drop(columns=['_unit_price'], inplace=True)





            





            # 更新统计卡片





            self.audit_stat_labels['total'].configure(text=str(total))





            self.audit_stat_labels['high_dev'].configure(text=str(len(high_dev)))





            self.audit_stat_labels['need_note'].configure(text=str(len(need_note)))





            self.audit_stat_labels['ok_note'].configure(text=str(len(ok_note)))





            





            self.audit_data = high_dev.copy()





            # 映射订单日期列（Data sheet 用"订单开始日期"，统一为"订单日期"）





            if '订单开始日期' in self.audit_data.columns:





                self.audit_data['订单日期'] = pd.to_datetime(self.audit_data['订单开始日期'], errors='coerce').dt.strftime('%Y-%m-%d')





            elif '订单日期' not in self.audit_data.columns:





                self.audit_data['订单日期'] = ''





            self._update_filter_options()





            self._refresh_audit_tree(self.audit_data)





            





            self.audit_tree.tag_configure('need_note', background='#fff0e0', foreground='#b04000')





            self.audit_tree.tag_configure('ok_note',   background='#e8f5e9', foreground='#1a6b1a')





            self.audit_tree.tag_configure('ai_gen',    background='#fce4ec', foreground='#880e4f')





            self.audit_ai_btn.configure(state="normal")





            self.audit_export_btn.configure(state="normal")





            # 同时启用偏差明细表的按钮





            if hasattr(self, 'unified_ai_btn'):





                self.unified_ai_btn.configure(state="normal")





            if hasattr(self, 'unified_export_btn'):





                self.unified_export_btn.configure(state="normal")





            if hasattr(self, 'cleanup_btn'):





                self.cleanup_btn.configure(state="normal")





            if hasattr(self, 'save_audit_btn'):





                self.save_audit_btn.configure(state="normal")





            self._apply_row_colors()





            # P0-B4：恢复审核记录（从数据库）





            self.audit_presenter.load_audit_data(self.audit_data)





            self.log(f"智能审核：加载完成 | 共{total}条 | 偏差>10%共{len(high_dev)}条 | 需补备注{len(need_note)}条", "success")





        except Exception as e:





            messagebox.showerror("错误", f"加载数据失败：{e}")





            self.log(f"加载审核数据失败：{e}", "error")

















    def _load_audit_data_from_output_click(self, event=None):





        """按钮点击事件：加载审核数据（包装函数，忽略event参数）"""





        self._load_audit_data_from_output()

















    @with_feedback("", "加载数据失败")





    @with_feedback("数据加载成功", "数据加载失败")





    def _load_audit_data_from_output(self, file_path=None):





        """分析完成后：异步从输出目录加载偏差明细到审核表格"""





        try:





            # 显示进度条





            if hasattr(self, 'progress_bar'):





                self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)





                self.progress_bar.start(10)





            if hasattr(self, 'set_status'):





                self.set_status("正在加载数据，请稍候...")











            # Capture UI values for worker (no UI access in worker)





            self._pending_output_dir = self.output_dir.get() if hasattr(self, 'output_dir') else None





            self.task_manager.run(





                lambda: self._load_data_worker(file_path),





                callback=self._on_load_done,





                error_callback=self._on_load_error





            )





        except Exception as e:





            if hasattr(self, 'progress_bar'):





                self.progress_bar.stop()





                self.progress_bar.pack_forget()





            self.log(f"[ERROR] _on_load_done异常: {e}", "error")





            import traceback





            self.log(traceback.format_exc()[-600:], "error")











    def _load_data_worker(self, file_path=None):





        """纯数据处理：查找文件、读取、清洗、构建audit_df（禁止UI操作）"""





        import pandas as pd





        import glob as _glob











        # 1. 确定输出目录





        if not file_path:





            out_dir = None





            # output_dir 和 input_file 是 UI 变量，在launcher中获取





            if hasattr(self, '_pending_output_dir'):





                out_dir = self._pending_output_dir





            if not out_dir or not os.path.isdir(out_dir):





                out_dir = os.path.expanduser('~/Desktop')





        else:





            out_dir = None











        # 2. 找文件





        if file_path:





            latest_file = file_path





        else:





            pattern = os.path.join(out_dir, 'ZPP011偏差分析最终版_*.xlsx')





            files = _glob.glob(pattern)





            if not files:





                raise FileNotFoundError("未找到任何分析结果文件")





            latest_file = max(files, key=os.path.getmtime)











        # 3. 读取





        dev_df = pd.read_excel(latest_file, sheet_name='完整偏差明细')





        if dev_df.empty:





            raise ValueError("偏差明细工作表为空")











        # 4. 解析偏差率





        def parse_rate(v):





            if isinstance(v, str):





                return float(v.replace('%','').replace('＞','>').replace('>','')) / 100





            return abs(float(v)) if pd.notna(v) else 0





        dev_df['偏差率数值'] = dev_df['偏差率'].apply(parse_rate)











        # 5. 构建 audit_df





        audit_df = dev_df.copy()





        # 修正原表行号：优先使用 analyzer 计算的 _excel_row（openpyxl真实行号）





        if '_excel_row' in dev_df.columns:





            audit_df['excel_row'] = dev_df['_excel_row'].apply(lambda x: int(x) if pd.notna(x) else 0)





            audit_df['原表行号'] = dev_df['_excel_row']  # 同步修正显示列





        elif '原表行号' in dev_df.columns:





            audit_df['excel_row'] = dev_df['原表行号'].apply(lambda x: int(x) if pd.notna(x) else 0)





        else:





            audit_df['excel_row'] = range(2, len(audit_df) + 2)





            audit_df['原表行号'] = audit_df['excel_row']





        audit_df['组件物料号'] = audit_df.get('物料编码', '')





        audit_df['组件物料描述'] = audit_df.get('物料名称', '')





        audit_df['工厂名称'] = audit_df.get('工厂', '')





        audit_df['生产管理员描述'] = audit_df.get('车间', '')





        audit_df['数量-定额'] = audit_df.get('定额', 0)





        audit_df['数量-实际'] = audit_df.get('实际', 0)





        audit_df['偏差率(%)'] = audit_df['偏差率数值'] * 100





        audit_df['备注原因'] = audit_df.get('备注', '')











        # 调试：对比 订单300354378+物料10000000 的数据





        mask_debug = (audit_df.get('流程订单', '').astype(str) == '300354378') & (audit_df.get('组件物料号', '').astype(str) == '10000000')





        if mask_debug.any():





            d = audit_df[mask_debug].iloc[0]





            self._debug_row = d





            debug_info = f"[DEBUG] 订单300354378+物料10000000: "





            debug_info += f"excel_row={d.get('excel_row')}, "





            debug_info += f"定额={d.get('定额')}, 实际={d.get('实际')}, "





            debug_info += f"数量-定额={d.get('数量-定额')}, 数量-实际={d.get('数量-实际')}, "





            debug_info += f"物料编码={d.get('物料编码')}, 物料名称={d.get('物料名称')}"





            with open(os.path.join(os.path.expanduser('~'), 'Desktop', 'zpp011_debug.txt'), 'a', encoding='utf-8') as f:





                f.write(debug_info + '\n')





        else:





            self._debug_row = None











        # 偏差金额计算





        if '偏差金额' not in audit_df.columns or pd.to_numeric(audit_df['偏差金额'], errors='coerce').abs().max() == 0:





            if '金额-实际(含税)' in dev_df.columns and '数量-实际' in dev_df.columns:





                audit_df['_unit_price'] = 0.0





                m = (dev_df['数量-实际'] != 0) & dev_df['数量-实际'].notna()





                audit_df.loc[m, '_unit_price'] = dev_df.loc[m, '金额-实际(含税)'] / dev_df.loc[m, '数量-实际']





                if '数量-定额' in dev_df.columns:





                    audit_df['数量偏差'] = dev_df['数量-实际'] - dev_df['数量-定额']





                else:





                    audit_df['数量偏差'] = 0.0





                audit_df['偏差金额'] = (audit_df['数量偏差'] * audit_df['_unit_price']).round(2)





                audit_df.drop(columns=['_unit_price'], inplace=True, errors='ignore')





            else:





                audit_df['偏差金额'] = 0.0





        else:





            audit_df['偏差金额'] = pd.to_numeric(audit_df['偏差金额'], errors='coerce').fillna(0).round(2)











        # 订单列查找





        order_col = None





        for possible in ['流程订单', '订单号', '订单编号', '订单号码', '订单No', 'Order No', '生产订单']:





            if possible in audit_df.columns:





                order_col = possible





                break





            if possible in dev_df.columns:





                order_col = possible





                break





        if order_col is None:





            audit_df['流程订单'] = ''





        elif order_col != '流程订单':





            audit_df['流程订单'] = audit_df[order_col]











        # 生成唯一ID





        audit_df['_uid'] = (





            audit_df['订单日期'].astype(str).str[:10] + '_' +





            audit_df['流程订单'].astype(str) + '_' +





            audit_df['组件物料号'].astype(str)





        )





        if '备注来源' not in audit_df.columns:





            audit_df['备注来源'] = ''





        if '原备注' not in audit_df.columns:





            audit_df['原备注'] = audit_df.get('备注原因', '')





        if 'AI建议' not in audit_df.columns:





            audit_df['AI建议'] = ''





        if 'audit_result' not in audit_df.columns:





            audit_df['audit_result'] = ''











        return audit_df











    def _on_load_done(self, result_df):





        """异步加载成功回调：处理所有UI更新"""





        try:





            self.audit_data = result_df

            # 如果启用了新筛选栏，更新下拉选项
            if hasattr(self, "filter_panel") and self.filter_panel:
                self.filter_panel.update_options(self.audit_data)












            # 确保数值列为数值类型（防止字符串导致比较错误）





            for col in ["偏差率(%)", "材料偏差", "数量-定额", "数量-实际", "偏差金额"]:





                if col in self.audit_data.columns:





                    self.audit_data[col] = pd.to_numeric(self.audit_data[col], errors="coerce").fillna(0)











            self._full_dev_df = result_df.copy()





            self.log(f"[DEBUG] _on_load_done: {len(self.audit_data)}行", "info")





            # 调试：打印前5行 excel_row 和 原表行号





            if 'excel_row' in self.audit_data.columns:





                self.log(f"[DEBUG] excel_row 前5行: {self.audit_data['excel_row'].head().tolist()}", "debug")





            if '原表行号' in self.audit_data.columns:





                self.log(f"[DEBUG] 原表行号 前5行: {self.audit_data['原表行号'].head().tolist()}", "debug")





            # 调试：打印 订单300354378+物料10000000 的数据





            mask = (self.audit_data.get('流程订单', '').astype(str) == '300354378') & (self.audit_data.get('组件物料号', '').astype(str) == '10000000')





            if mask.any():





                debug_row = self.audit_data[mask].iloc[0]





                self.log(f"[DEBUG] 订单300354378+物料10000000: excel_row={debug_row.get('excel_row')}, 定额={debug_row.get('数量-定额')}, 实际={debug_row.get('数量-实际')}", "debug")











            # 更新筛选选项和行颜色





            self._update_filter_options()





            self._apply_row_colors()





            if hasattr(self, '_update_trend_display'):





                self._update_trend_display()











            # 统计卡片





            total = len(result_df)





            high_dev = len(result_df[result_df['偏差率(%)'] > 10]) if '偏差率(%)' in result_df.columns else 0





            no_note = len(result_df[result_df['备注原因'].isna() | (result_df['备注原因'] == '')]) if '备注原因' in result_df.columns else 0





            approved_note = result_df['备注来源'].isin(['AI审核合格','AI审核待改进','AI生成']).sum() if '备注来源' in result_df.columns else 0











            if hasattr(self, 'audit_stat_labels'):





                for k, v in [('total', total), ('high_dev', high_dev),





                               ('need_note', no_note), ('ok_note', approved_note)]:





                    if k in self.audit_stat_labels:





                        self.audit_stat_labels[k].configure(text=str(v))





            if hasattr(self, 'unified_result_lbl'):





                self.unified_result_lbl.configure(





                    text=f"已加载 {total} 条 | 偏差>10%: {high_dev} | 需补备注: {no_note} | 已审核: {approved_note}")











            # 启用所有按钮





            enabled = self._enable_audit_buttons()





            self.log(f"[DEBUG] 已启用{enabled}个按钮", "info")











            self.log(f"✅ 审核数据加载完成 | 共 {total} 条 | 偏差>10%: {high_dev} 条", "success")











            # 恢复筛选和排序状态





            self._restore_filters()





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 100), lambda: self._on_filter_changed(None) if self.audit_data is not None else None)





            self._restore_sort_state()





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 300), lambda: self._show_precheck_report(self.audit_data))





            # BOM 过期提醒（功能待实现，暂注释）





            # self.root.after(self.config.get('analysis.cleanup_delay_ms', 500), self._check_and_remind_bom)





            # 恢复审核记录





            self.audit_presenter.load_audit_data(self.audit_data)











            # 断点续审提示





            state = self._load_resume_state()





            if state:





                self.resume_btn.configure(state="normal")





                saved_row = state.get('selected_row', None)





                if saved_row is not None:





                    self.log(f"📌 检测到上次审核进度：第 {saved_row} 行", "info")





                    tip = tk.Toplevel(self.root)





                    tip.wm_overrideredirect(True)





                    tip.geometry(f"280x28+{self.root.winfo_rootx()+self.root.winfo_width()-290}+{self.root.winfo_rooty()+self.root.winfo_height()-60}")





                    tk.Label(tip, text=f"💡 上次审核到第 {saved_row} 行，点击「恢复进度」继续",





                            font=("Microsoft YaHei", 9), bg="#1a1a2e", fg="white",





                            padx=8, pady=4).pack()





                    tip.after(4000, tip.destroy)











            # 隐藏进度条





            if hasattr(self, 'progress_bar'):





                self.progress_bar.stop()





                self.progress_bar.pack_forget()





            if hasattr(self, 'set_status'):





                self.set_status(f"加载完成，共 {total} 行")





        except Exception as e:





            if hasattr(self, 'progress_bar'):





                self.progress_bar.stop()





                self.progress_bar.pack_forget()





            raise











    def _on_load_error(self, error):





        """异步加载失败回调"""





        if hasattr(self, 'progress_bar'):





            self.progress_bar.stop()





            self.progress_bar.pack_forget()





        if hasattr(self, 'set_status'):





            self.set_status("加载失败")





        messagebox.showerror("加载错误", str(error))





        try:





            from core.logger import get_logger





            get_logger().error(f"数据加载异步失败: {error}")





        except Exception:





            pass

















    def _filter_by_stat(self, filter_key):





        """根据顶部统计卡片点击，筛选审核表格（委托Presenter）"""





        if self.audit_data is None or len(self.audit_data) == 0:





            return











        # 委托 Presenter 执行纯业务筛选逻辑





        filtered = self.audit_presenter.filter_audit_data({'stat': filter_key})











        # 刷新审核表格（View层）





        self._refresh_audit_tree(filtered)





        self._update_audit_stats(filtered)











        # 更新筛选提示文字





        labels = {'total': '全部', 'big_dev': '偏差>10%',





                  'no_note': '需补备注', 'approved': '已审核'}





        self.status_filter_label.config(





            text="筛选：{} | 共 {} 条".format(labels.get(filter_key, ''), len(filtered))





        )





    def _s01_start_inventory_check(self, data: pd.DataFrame) -> None:





        """启动库存流程检查（异步），线程创建失败时释放锁"""





        if self._is_s01_processing:





            messagebox.showwarning("提示", "已有库存检查任务进行中")





            return





        if data is None or data.empty:





            messagebox.showwarning("警告", "无数据可检查")





            return











        self._is_s01_processing = True





        try:





            self._s01_disable_ui()





            self.progress_bar.configure(mode='determinate', maximum=100)





            self.progress_bar['value'] = 0





            self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)





            self.set_status("正在执行库存检查...")











            data_copy = data.copy(deep=True)





            self._s01_cancel_flag = threading.Event()











            self._s01_thread = threading.Thread(





                target=self._s01_inventory_worker,





                args=(data_copy, self._s01_cancel_flag)





            )





            self._s01_thread.daemon = True





            self._s01_thread.start()





        except Exception as e:





            self._s01_cleanup()





            messagebox.showerror("错误", f"任务启动失败: {e}")











    def _s01_inventory_worker(self, df, cancel_flag):





        """异步任务：纯数据处理，使用 itertuples，每 50 行检查取消并回调进度"""





        total = len(df)





        status_col = None





        for col in ['库存状态', 'inventory_status']:





            if col in df.columns:





                status_col = col





                break





        if status_col is None:





            df['库存状态'] = ''





            status_col = '库存状态'











        try:





            for idx, row in enumerate(df.itertuples(index=False)):





                if cancel_flag.is_set():





                    self._s01_clean_temp_files()





                    raise InterruptedError("操作已取消")





                row_dict = row._asdict()





                # 业务逻辑待补充





                if (idx + 1) % 50 == 0 or idx + 1 == total:





                    self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), self._s01_progress_callback, idx + 1, total)





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), self._s01_on_success, df)





        except InterruptedError as e:





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), self._s01_on_error, e)





        except Exception as e:





            self.root.after(self.config.get('analysis.cleanup_delay_ms', 0), self._s01_on_error, e)











    def _s01_progress_callback(self, current: int, total: int) -> None:





        """进度回调"""





        percent = int(current / total * 100) if total else 0





        self.progress_bar['value'] = percent





        self.set_status(f"库存检查中: {current}/{total} ({percent}%)")











    def _s01_on_success(self, result_df: pd.DataFrame) -> None:





        """成功回调：调用高亮版 _s01_populate_table"""





        self.audit_data = result_df





        self._s01_populate_table(result_df)





        self._s01_cleanup()
















    def _s01_on_error(self, error: Exception) -> None:





        """错误/取消回调"""





        if isinstance(error, InterruptedError):





            self.set_status("操作已取消")





            messagebox.showwarning("已���消", str(error))





        else:





            self.set_status("操作失败")





            messagebox.showerror("错误", f"库存检查失败: {error}")





        self._s01_cleanup()











    def _s01_cleanup(self) -> None:





        """统一清理"""





        self._is_s01_processing = False





        self._s01_cancel_flag = None





        self._s01_thread = None





        self._s01_enable_ui()





        self.progress_bar['value'] = 0





        self.progress_bar.pack_forget()





        self.set_status("就绪")





        self._s01_clean_temp_files()











    def _s01_cancel_inventory_check(self) -> None:





        if self._s01_cancel_flag:





            self._s01_cancel_flag.set()











    def _s01_disable_ui(self) -> None:





        """禁用相关按钮"""





        pass











    def _s01_enable_ui(self) -> None:





        """恢复按钮"""





        pass











    # ── S01 异常高亮方法 ─────────────────────────────────────────────────





    def _evaluate_condition(self, row: dict, condition_str: str) -> bool:





        """安全评估条件表达式（仅用于 S01 高亮）"""





        dangerous = ['__', 'import', 'exec', 'eval', 'compile', 'open', 'file']





        if any(d in condition_str for d in dangerous):





            return False





        allowed = {k: v for k, v in row.items() if isinstance(v, (int, float, str, bool))}





        try:





            return bool(eval(condition_str, {"__builtins__": {}}, allowed))





        except Exception:





            return False











    def _s01_setup_treeview_tags(self, tree):





        """为 Treeview 配置高亮 tag（仅首次）"""





        cache_key = f"_s01_tags_configured_{id(tree)}"





        if getattr(self, cache_key, False):





            return





        config = getattr(self, 's01_display_config', {})





        for rule in config.get('rules', []):





            tag = rule.get('tag')





            color = rule.get('color')





            if tag and color:





                try:





                    tree.tag_configure(tag, background=color)





                except Exception:





                    pass





        setattr(self, cache_key, True)











    def _s01_populate_table(self, df):





        """将 DataFrame 填充到 audit_tree，并根据 s01_display_config 应用高亮"""





        tree = getattr(self, 'audit_tree', None)





        if tree is None:





            self._refresh_audit_tree(df)





            return











        self._s01_setup_treeview_tags(tree)





        config = getattr(self, 's01_display_config', {})





        rules = config.get('rules', [])





        default_color = config.get('default_color', '#FFFFFF')





        try:





            tree.tag_configure('s01_normal', background=default_color)





        except Exception:





            pass











        # 清空旧数据





        for item in tree.get_children():





            tree.delete(item)











        cols = list(tree['columns']) if tree['columns'] else (list(df.columns) if not df.empty else [])











        for row_tuple in df.itertuples():





            row_dict = row_tuple._asdict()





            row_dict.pop('Index', None)





            tag = 's01_normal'





            for rule in rules:





                condition = rule.get('condition', '')





                if condition and self._evaluate_condition(row_dict, condition):





                    tag = rule.get('tag', 's01_normal')





                    break





            values = [row_dict.get(c, '') for c in cols]





            tree.insert('', 'end', values=values, tags=(tag,))

















    # ---------- View 接口方法（供 AuditPresenter 调用）----------
