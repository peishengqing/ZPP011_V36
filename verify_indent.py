# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'E:\zpp011_dev\模块化脚本\gui\app.py', 'r', encoding='utf-8') as f:
    app = f.read()
with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'r', encoding='utf-8') as f:
    ev = f.read()
with open(r'E:\zpp011_dev\模块化脚本\gui\ui_builder.py', 'r', encoding='utf-8') as f:
    ui = f.read()

print("=== 方法缩进精细分析 ===")

# app.py: find class boundary, check methods inside class
lines_app = app.split('\n')
class_start = None
for i, l in enumerate(lines_app):
    if 'class ZPP011Beautiful' in l:
        class_start = i
        break
print(f"app.py class starts at line {class_start+1}")

# Get all 'def ' lines AFTER class start but before standalone module functions
app_defs = []
for i, l in enumerate(lines_app):
    stripped = l.strip()
    if stripped.startswith('def ') and i >= class_start:
        ind = len(l) - len(l.lstrip())
        app_defs.append((i+1, stripped[:50], ind))

# Check for indent != 4 (but excluding standalone functions at bottom)
broken_app = [(ln, name, ind) for ln, name, ind in app_defs 
               if ind != 4 and not name.startswith('def run_app')]
print(f"app.py broken methods: {broken_app}")

# events.py: find class boundary
lines_ev = ev.split('\n')
class_start_ev = None
for i, l in enumerate(lines_ev):
    if 'class EventsMixIn' in l:
        class_start_ev = i
        break
print(f"events.py class starts at line {class_start_ev+1}")

ev_defs = [(i+1, l.strip()[:50], len(l)-len(l.lstrip())) 
            for i, l in enumerate(lines_ev)
            if l.strip().startswith('def ') and i >= class_start_ev]
broken_ev = [(ln, name, ind) for ln, name, ind in ev_defs
             if ind != 4 and not name.startswith('def run_app')]
print(f"events.py broken methods: {broken_ev}")

print()
print("=== 模块级函数（非类方法，应在 indent=0）===")
app_standalone = [(ln, name) for ln, name, ind in app_defs if ind == 0]
ev_standalone = [(ln, name) for ln, name, ind in ev_defs if ind == 0]
print(f"app.py standalone: {app_standalone}")
print(f"events.py standalone: {ev_standalone}")