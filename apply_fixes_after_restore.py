# -*- coding: utf-8 -*-
"""从Git恢复后重新应用必要修复"""
import os

print("=== 重新应用修复 ===")

# ============================================================
# 修复1: gui/events.py - _load_data_worker 添加列名清理
# ============================================================
fp1 = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(fp1, 'r', encoding='utf-8') as f:
    c1 = f.read()

# 1a: 添加列名清理
old_load = """        dev_df = pd.read_excel(latest_file, sheet_name='完整偏差明细')
        if dev_df.empty:
            raise ValueError("偏差明细工作表为空")

        # 4. 解析偏差率"""

new_load = """        dev_df = pd.read_excel(latest_file, sheet_name='完整偏差明细')
        if dev_df.empty:
            raise ValueError("偏差明细工作表为空")

        # 列名清理（去除空格）
        dev_df.columns = [str(col).strip().replace(' ', '') for col in dev_df.columns]

        # 4. 解析偏差率"""

if old_load in c1:
    c1 = c1.replace(old_load, new_load)
    print('1a. OK: Added column cleaning')
else:
    print('1a. SKIP')

# 1b: 添加日期列映射
old_date = """        # 生成唯一ID
        audit_df['_uid'] = (
            audit_df['订单日期'].astype(str).str[:10] + '_' +
            audit_df['流程订单'].astype(str) + '_' +
            audit_df['组件物料号'].astype(str)
        )"""

new_date = """        # 日期列映射
        if '订单开始日期' in audit_df.columns and '订单日期' not in audit_df.columns:
            audit_df['订单日期'] = audit_df['订单开始日期'].astype(str).str[:10]
        elif '订单日期' not in audit_df.columns:
            audit_df['订单日期'] = ''

        # 生成唯一ID
        audit_df['_uid'] = (
            audit_df['订单日期'].astype(str).str[:10] + '_' +
            audit_df['流程订单'].astype(str) + '_' +
            audit_df['组件物料号'].astype(str)
        )"""

if old_date in c1:
    c1 = c1.replace(old_date, new_date)
    print('1b. OK: Added date column mapping')
else:
    print('1b. SKIP')

# 1c: PPT worker 增强
old_ppt = """        def worker():
            try:
                import ppt_generator
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log)
                self.root.after(0, lambda: self._on_ppt_done(output_path))
            except Exception as e:
                self.root.after(0, lambda: self._on_ppt_error(str(e)))"""

new_ppt = """        def worker():
            try:
                import ppt_generator
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                self.log(f"[PPT] 开始生成: {output_path}", "info")
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log)
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    self.log(f"[PPT] 文件已生成，大小: {file_size} 字节", "info")
                    self.root.after(0, lambda: self._on_ppt_done(output_path))
                else:
                    raise RuntimeError(f"PPT 文件未生成: {output_path}")
            except ImportError as e:
                self.root.after(0, lambda e=e: self._on_ppt_error(f"缺少 python-pptx: {e}"))
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                self.log(f"[PPT] 失败详情: {err}", "error")
                self.root.after(0, lambda e=e: self._on_ppt_error(f"生成失败: {e}"))"""

if old_ppt in c1:
    c1 = c1.replace(old_ppt, new_ppt)
    print('1c. OK: Enhanced PPT worker')
else:
    print('1c. SKIP')

with open(fp1, 'w', encoding='utf-8') as f:
    f.write(c1)

# ============================================================
# 修复2: ppt_generator.py - 列名清理
# ============================================================
fp2 = r'E:\zpp011_dev\模块化脚本\ppt_generator.py'
with open(fp2, 'r', encoding='utf-8') as f:
    c2 = f.read()

old_safe = """        def safe_read(name, default_cols=None):
            if name in sheets:
                return pd.read_excel(excel_path, sheet_name=name)
            for s in sheets:
                if name in s:
                    return pd.read_excel(excel_path, sheet_name=s)
            _log(f"  [PPT] 未找到 Sheet「{name}」，将跳过相关内容")
            return pd.DataFrame(columns=default_cols or [])"""

new_safe = """        def safe_read(name, default_cols=None):
            if name in sheets:
                df = pd.read_excel(excel_path, sheet_name=name)
            else:
                for s in sheets:
                    if name in s:
                        df = pd.read_excel(excel_path, sheet_name=s)
                        break
                else:
                    _log(f"  [PPT] 未找到 Sheet「{name}」，将跳过相关内容")
                    return pd.DataFrame(columns=default_cols or [])
            df.columns = [str(col).strip().replace(' ', '') for col in df.columns]
            return df"""

if old_safe in c2:
    c2 = c2.replace(old_safe, new_safe)
    print('2a. OK: Added column cleaning in ppt_generator')
else:
    print('2a. SKIP')

with open(fp2, 'w', encoding='utf-8') as f:
    f.write(c2)

print('\\nDone!')
