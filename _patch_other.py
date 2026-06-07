import ast, sys, os, subprocess

base = r'E:\zpp011_dev\模块化脚本'

safe_func = '''

def _safe_for_gbk(text):
    if not text: return text
    result = []
    for c in text:
        try:
            c.encode('gbk')
            result.append(c)
        except UnicodeEncodeError:
            pass
    return ''.join(result)

'''

for fname in ['gui/audit_logging.py', 'gui/window_manager.py']:
    fpath = os.path.join(base, fname.replace('/', os.sep))
    
    r = subprocess.run(['git', '-C', base, 'show', 'HEAD:gui/event_handlers/analysis_events.py'],
                      capture_output=True)
    orig_r = subprocess.run(['git', '-C', base, 'show', 'HEAD:' + fname],
                          capture_output=True)
    
    if orig_r.returncode != 0:
        sys.stdout.write('%s: not in git or error\n' % fname)
        continue
    
    try:
        text = orig_r.stdout.decode('utf-8')
    except:
        sys.stdout.write('%s: decode error\n' % fname)
        continue
    
    # Check if already has _safe_for_gbk
    if 'def _safe_for_gbk' in text:
        sys.stdout.write('%s: already has _safe_for_gbk\n' % fname)
        continue
    
    # Check for messagebox calls
    has_mb = 'messagebox.' in text
    sys.stdout.write('%s: has messagebox=%s\n' % (fname, has_mb))
    
    if not has_mb:
        continue
    
    # Add _safe_for_gbk function after 'import sys' line
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        sys.stdout.write('%s: SYNTAX ERROR (original) line %d: %s\n' % (fname, e.lineno, e.msg))
        continue
    
    # Find insert point
    lines = text.split('\n')
    insert_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == 'import sys' or line.strip() == 'import sys\r':
            insert_idx = i + 1
            break
    
    if insert_idx < 0:
        sys.stdout.write('%s: could not find import sys line\n' % fname)
        continue
    
    new_lines = lines[:insert_idx] + ['', safe_func.strip()] + lines[insert_idx:]
    text = '\n'.join(new_lines)
    
    # Apply AST-based replacements
    class MBVisitor(ast.NodeVisitor):
        def __init__(self):
            self.replacements = []
        
        def visit_Call(self, node):
            if (isinstance(node.func, ast.Attribute) and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'messagebox' and
                node.func.attr in ('showerror', 'showwarning', 'showinfo', 'askyesno', 'askokcancel')):
                if len(node.args) >= 2:
                    title_src = ast.unparse(node.args[0])
                    body_src = ast.unparse(node.args[1])
                    new_call = 'messagebox.%s(_safe_for_gbk(%s), _safe_for_gbk(%s))' % (
                        node.func.attr, title_src, body_src)
                    self.replacements.append((node.lineno, node.col_offset, node.end_col_offset, new_call))
            self.generic_visit(node)
    
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        sys.stdout.write('%s: SYNTAX ERROR after insert line %d: %s\n' % (fname, e.lineno, e.msg))
        continue
    
    visitor = MBVisitor()
    visitor.visit(tree)
    sys.stdout.write('%s: found %d messagebox calls\n' % (fname, len(visitor.replacements)))
    
    replacements = sorted(visitor.replacements, key=lambda x: (x[0], x[1]), reverse=True)
    lines = text.split('\n')
    for lineno, start_col, end_col, new_call in replacements:
        line_idx = lineno - 1
        old = lines[line_idx]
        lines[line_idx] = old[:start_col] + new_call + old[end_col:]
    
    result = '\n'.join(lines)
    
    # Verify
    try:
        ast.parse(result)
        sys.stdout.write('%s: Syntax OK - writing\n' % fname)
        with open(fpath, 'w', encoding='utf-8', newline='') as f:
            f.write(result)
    except SyntaxError as e:
        sys.stdout.write('%s: SYNTAX ERROR in result line %d col %d\n' % (fname, e.lineno, e.offset))
        lines_err = result.split('\n')
        sys.stdout.write('Line: %r\n' % lines_err[e.lineno-1])
