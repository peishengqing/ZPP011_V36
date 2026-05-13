import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os, json

path = r'E:\zpp011_dev\模块化脚本\gui\events.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find a good place to add the methods - right before _do_resume_state
# First, let's see where _do_resume_state is defined
target = '    def _do_resume_state(self):'
idx = content.find(target)
if idx == -1:
    print('Target not found!')
    sys.exit(1)

# Add both methods before _do_resume_state
new_methods = '''    def _get_resume_state_path(self):
        """获取断点状态文件路径"""
        app_dir = os.path.join(os.path.expanduser('~'), '.zpp011_audit')
        return os.path.join(app_dir, 'resume_state.json')

    def _load_resume_state(self):
        """加载断点状态"""
        path = self._get_resume_state_path()
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _save_resume_state(self):
        """保存断点状态"""
        app_dir = os.path.join(os.path.expanduser('~'), '.zpp011_audit')
        os.makedirs(app_dir, exist_ok=True)
        path = self._get_resume_state_path()
        
        state = {}
        # 保存选择的行
        if hasattr(self, 'current_row_idx'):
            state['selected_row'] = self.current_row_idx
        # 保存搜索文字
        if hasattr(self, 'search_var'):
            state['search_text'] = self.search_var.get()
        # 保存筛选条件
        if hasattr(self, 'filter_widgets'):
            state['filter_values'] = {}
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存断点失败：{e}", "warn")


'''

# Insert before _do_resume_state
content = content[:idx] + new_methods + content[idx:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('FIXED: Added _load_resume_state and _save_resume_state methods')