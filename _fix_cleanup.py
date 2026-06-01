# -*- coding: utf-8 -*-
import re

content = open(r'E:\zpp011_dev\模块化脚本\gui\event_handlers\analysis_events.py', 'r', encoding='utf-8').read()

# Find the problematic section and replace it
old_section = '''            # 自动 AI 审核 + 自动结案
            if not getattr(self, '_auto_processed', False):
                self.root.after(500, self._auto_audit_and_close)
        
        
        # ── 加载成功后清理临时 Excel 文件 ──
        if hasattr(self, '_analysis_output_path') and self._analysis_output_path:
            try:
                if os.path.exists(self._analysis_output_path):
                    os.remove(self._analysis_output_path)
                    self.log(f"\U0001f5d1 已清理临时文件: {os.path.basename(self._analysis_output_path)}", "info")
                    self._analysis_output_path = None
            except Exception as e:
                self.log(f"清理临时文件失败: {e}", "warn")
        except Exception as e:
            if hasattr(self, 'progress_bar'):
                self.progress_bar.stop()
                self.progress_bar.pack_forget()
            raise
        except Exception as e:
            if hasattr(self, 'progress_bar'):
                self.progress_bar.stop()
                self.progress_bar.pack_forget()
            raise'''

new_section = '''            # 自动 AI 审核 + 自动结案
            if not getattr(self, '_auto_processed', False):
                self.root.after(500, self._auto_audit_and_close)
        except Exception as e:
            if hasattr(self, 'progress_bar'):
                self.progress_bar.stop()
                self.progress_bar.pack_forget()
            raise
        
        # --- 加载成功后清理临时 Excel 文件 ---
        if hasattr(self, '_analysis_output_path') and self._analysis_output_path:
            try:
                if os.path.exists(self._analysis_output_path):
                    os.remove(self._analysis_output_path)
                    self.log("[INFO] 已清理临时文件: " + os.path.basename(self._analysis_output_path), "info")
                    self._analysis_output_path = None
            except Exception as e:
                self.log("清理临时文件失败: " + str(e), "warn")'''

if old_section in content:
    content = content.replace(old_section, new_section)
    open(r'E:\zpp011_dev\模块化脚本\gui\event_handlers\analysis_events.py', 'w', encoding='utf-8').write(content)
    print('Fixed OK')
else:
    print('Section not found')