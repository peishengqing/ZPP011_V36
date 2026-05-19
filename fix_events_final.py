# -*- coding: utf-8 -*-
"""修复 events.py - 基于v36.39.0版本"""
import os

fp = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加列名清理
old_load = """        dev_df = pd.read_excel(latest_file, sheet_name='完整偏差明细')
        if dev_df.empty:
            raise ValueError("偏差明细工作表为空")"""

new_load = """        dev_df = pd.read_excel(latest_file, sheet_name='完整偏差明细')
        if dev_df.empty:
            raise ValueError("偏差明细工作表为空")
        # 列名清理（去除空格）
        dev_df.columns = [str(col).strip().replace(' ', '') for col in dev_df.columns]"""

if old_load in content:
    content = content.replace(old_load, new_load)
    print('1. OK: Added column cleaning')
else:
    print('1. SKIP')

# 2. 添加日期列映射
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

if old_date in content:
    content = content.replace(old_date, new_date)
    print('2. OK: Added date mapping')
else:
    print('2. SKIP')

# 3. PPT worker 增强
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
                import os
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                ppt_generator.run_ppt_generation(excel_path, output_path, log_cb=self.log)
                if os.path.exists(output_path):
                    self.root.after(0, lambda: self._on_ppt_done(output_path))
                else:
                    raise RuntimeError(f"PPT文件未生成: {output_path}")
            except ImportError as e:
                self.root.after(0, lambda e=e: self._on_ppt_error(f"缺少依赖: {e}"))
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                self.root.after(0, lambda e=e, err=err: self._on_ppt_error(f"生成失败: {e}"))"""

if old_ppt in content:
    content = content.replace(old_ppt, new_ppt)
    print('3. OK: Enhanced PPT worker')
else:
    print('3. SKIP')

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
