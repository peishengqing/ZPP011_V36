# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'E:\zpp011_dev\模块化脚本\gui\app.py', 'r', encoding='utf-8') as f:
    app = f.read()
with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'r', encoding='utf-8') as f:
    ev = f.read()
with open(r'E:\zpp011_dev\模块化脚本\gui\ui_builder.py', 'r', encoding='utf-8') as f:
    ui = f.read()

print("=== 嵌套函数分析（合法 helper functions，不属于类方法）===")

# These nested functions are INSIDE other method bodies, not class methods
# indent=8: function defined inside a class method (OK)
# indent=12/20: deeply nested (OK for inner lambdas/callbacks)

# Only real class methods start with indent=4 (inside class body)

lines_app = app.split('\n')
lines_ev = ev.split('\n')

# Find the class method boundary: app.py
for i, l in enumerate(lines_app):
    if 'class ZPP011Beautiful' in l:
        class_start = i
        break

# app.py class methods (indent=4, after class def)
app_class_methods = [(i+1, l.strip()[:60]) for i, l in enumerate(lines_app) 
                      if l.strip().startswith('def ') and len(l)-len(l.lstrip())==4 and i > class_start]
print(f"app.py class methods (indent=4): {len(app_class_methods)}")
for ln, name in app_class_methods:
    print(f"  {ln}: {name}")

print()
# events.py class methods
for i, l in enumerate(lines_ev):
    if 'class EventsMixIn' in l:
        class_start_ev = i
        break

ev_class_methods = [(i+1, l.strip()[:60]) for i, l in enumerate(lines_ev)
                     if l.strip().startswith('def ') and len(l)-len(l.lstrip())==4 and i > class_start_ev]
print(f"events.py class methods (indent=4): {len(ev_class_methods)}")
for ln, name in ev_class_methods:
    print(f"  {ln}: {name}")