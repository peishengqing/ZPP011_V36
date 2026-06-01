# -*- coding: utf-8 -*-
# Fix the syntax error in analysis_events.py

content = open(r'E:\zpp011_dev\模块化脚本\gui\event_handlers\analysis_events.py', 'r', encoding='utf-8').read()

# Target: find and replace the broken section
old_pattern = '''            # 自动 AI 审核 + 自动结案
            if not getattr(self, '_auto_processed', False):
                self.root.after(500, self._auto_audit_and_close)

        # ── 加载成功后清理临时 Excel 文件 ──
        if hasattr(self, '_analysis_output_path') and self._analysis_output_path:
            try:
                if os.path.exists(self._analysis_output_path):
                    os.remove(self._analysis_output_path)
                    self.log(
                        f"🗑️ 已清理临时文件: {os.path.basename(self._analysis_output_path)}", "info")
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
            raise

    def _on_load_error(self, error):'''

new_pattern = '''            # 自动 AI 审核 + 自动结案
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
                    self.log("已清理临时文件: " + os.path.basename(self._analysis_output_path), "info")
                    self._analysis_output_path = None
            except Exception as e:
                self.log("清理临时文件失败: " + str(e), "warn")

    def _on_load_error(self, error):'''

if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)
    open(r'E:\zpp011_dev\模块化脚本\gui\event_handlers\analysis_events.py', 'w', encoding='utf-8').write(content)
    print('Fixed OK')
else:
    # Try to find approximate location and replace
    import re
    # Match any try block followed by multiple excepts
    pattern = r'(# 自动 AI 审核[^\n]+\n[^\n]+self\._auto_audit_and_close\(\))\n\n(        # ── 加载成功后清理临时 Excel 文件 ──\n        if hasattr.*?self\.log\(f"清理临时文件失败.*?)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        print('Found by regex')
    else:
        print('Not found')