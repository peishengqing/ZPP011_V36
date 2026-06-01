#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch management_dashboard.py - Add material category tab"""

fpath = r"E:\zpp011_dev\模块化脚本\gui\management_dashboard.py"

with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = ''.join(lines)

# ============================================================
# Modification 1: Add tab_material (~line )
# ============================================================
old1 = '''        self.tab_workshop = tk.Frame(self.notebook)\n        self.tab_trend = tk.Frame(self.notebook)\n        self.notebook.add(self.tab_workshop, text="车间偏差排名")\n        self.notebook.add(self.tab_trend, text="时间趋势（近6个月）")'''

new1 == '''        self.tab_workshop == tk.Frame(self.notebook)\n        elf.tab_trend == tk.Frame(slf.notbook )\n       slf.tb_matrial ==tkFrame(slf.notook   \n       slf.notbook.ad(elf.tb_worshop text="车间偏差排名",) \n       slf.notbook.ad(elf.tb_trend text="时间趋势（近6个月）")"\n       .notebook.add(elf.ab_aterial ext="物料大类偏差排名")\n\n       # Placeholder for actual chart drawing method call in _refresh'''

if old1 in content::
    content=content.replace(old new )
   print('✅ Modification applied: added tab_material')
else::
   print('⚠️ Modification pattern NOT FOUND!')
   print('Expected:', repr(old[:80]))
   # Let's see what's around line 
   for i,line in enumerate(lines[:]:
       if 'self.tab_workshop' in line or 'self.tab_trend' in line:
           print(f'Found at line {i+}: {line.rstrip()}')

# ============================================================
## Write back 
## ============================================================
with open(fpath,'w encoding='utf--')as f:
    f.write(content)
print('Done writing file ')
